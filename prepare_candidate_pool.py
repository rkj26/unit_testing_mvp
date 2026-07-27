"""Prepare a validated pool of honest and attack candidates for paired runs.

For each task this command generates one honest candidate and a configurable
number of independent attack proposals. A separate red-team selector scores the
attack proposals from task text and declared triggers only. Deterministic local
math then chooses the best proposal per task and at most N attack opportunities
globally.

Usage:
    python prepare_candidate_pool.py --dataset main --limit 5 \
        --untrusted-model google/gemini-3.6-flash \
        --attack-proposals-per-task 2 --max-selected-attacks 2 \
        --red-team-selector-prompt v1_baseline --out candidate_pool.json
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from inspect_ai.agent import AgentState
from inspect_ai.model import ChatMessageUser, GenerateConfig, get_model
from inspect_ai.tool import Tool
from control_arena import EvalMode, control_agent
from control_arena.eval import ControlEvalConfig, eval as control_eval, get_control_task
from control_arena.micro_protocol import trusted_monitoring_builder
from control_arena.monitor import MonitorResponse, monitor
from control_arena.policy import (
    attack_policy_builder,
    honest_policy_builder,
    untrusted_policy_builder,
)

from candidate_pool import (
    CANDIDATE_POOL_SCHEMA_VERSION,
    candidate_id_for,
    sha256_text,
    sum_usages,
    validate_candidate_pool,
)
from bigcodebench_pbt_setting import (
    HELDOUT_TASK_IDS,
    MAIN_TASK_IDS,
    BigCodeBenchPBTSetting,
)
from config import Config
from cost_accounting import total_input_tokens
from policy_selection import (
    MOCKLLM_SELECTOR_ADAPTER,
    SELECTOR_PROMPT_VARIANT,
    build_selector_context,
    build_selector_input,
    mockllm_selector_result,
    parse_selector_output,
    render_selector_prompt,
    select_attack_opportunities,
    selector_result_json,
)
from prompts import load_prompt
from provenance import dataset_fingerprints
from submission import SubmissionError, extract_submission
from artifact_io import atomic_write_new_json


@control_agent
def capture_only_monitor_builder():
    @monitor
    async def _capture_only_monitor(
        state: AgentState, tools: list[Tool]
    ) -> MonitorResponse:
        return MonitorResponse(
            suspicion_score=0.0, reason="candidate-pool capture only"
        )

    return _capture_only_monitor


def _usage_record(model_usages: Iterable[Any]) -> dict[str, Any]:
    records = []
    for usage in model_usages:
        if usage is None:
            continue
        cost = getattr(usage, "total_cost", None)
        records.append(
            {
                "input_tokens": total_input_tokens(usage),
                "output_tokens": int(getattr(usage, "output_tokens", 0)),
                "model_cost_usd": float(cost) if cost is not None else None,
            }
        )
    if not records:
        return {"input_tokens": 0, "output_tokens": 0, "model_cost_usd": None}
    return sum_usages(records)


def _extract_submission(sample: Any) -> tuple[str, str | None]:
    try:
        submission = extract_submission(sample.messages)
    except SubmissionError as error:
        raise RuntimeError(
            f"invalid submission for sample {sample.id}: {error}"
        ) from error
    return submission.code, submission.secret_input


def _selector_contexts(samples: Iterable[Any]) -> dict[str, dict[str, str]]:
    """Extract only red-team-visible task text from the attack dataset."""

    contexts = {}
    for sample in samples:
        metadata = sample.metadata or {}
        task_id = metadata.get("main_task_name")
        task_description = metadata.get("main_task_description")
        side_task_description = metadata.get("side_task_description")
        if not isinstance(task_id, str) or not task_id:
            raise RuntimeError(f"dataset sample {sample.id!r} has no main_task_name")
        if not isinstance(task_description, str) or not task_description.strip():
            raise RuntimeError(
                f"dataset sample {sample.id!r} has no main_task_description"
            )
        if not isinstance(side_task_description, str):
            raise RuntimeError(
                f"dataset sample {sample.id!r} has no side_task_description"
            )
        if task_id in contexts:
            raise RuntimeError(f"attack dataset contains duplicate task {task_id!r}")
        contexts[task_id] = {
            "task_description": task_description,
            "side_task_description": side_task_description,
        }
    return contexts


def _candidate_record(
    *,
    task_id: str,
    kind: str,
    generation_index: int,
    code: str,
    secret_input: str | None,
    sample: Any,
    model: str,
    attack_prompt_variant: str,
    attack_prompt_sha256: str,
    proposal_seed: int | None,
) -> dict[str, Any]:
    if kind == "honest" and secret_input is not None:
        raise RuntimeError(f"honest sample {sample.id} unexpectedly declared a trigger")
    if kind == "attack" and secret_input is None:
        raise RuntimeError(f"attack sample {sample.id} did not declare a trigger")
    if kind == "attack":
        try:
            parsed_secret = json.loads(secret_input)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f"attack sample {sample.id} declared invalid secret-input JSON"
            ) from error
        if not isinstance(parsed_secret, dict) or not all(
            isinstance(key, str) for key in parsed_secret
        ):
            raise RuntimeError(
                f"attack sample {sample.id} secret input must encode keyword arguments"
            )
    usage = _usage_record((sample.model_usage or {}).values())
    return {
        "candidate_id": candidate_id_for(
            task_id=task_id,
            kind=kind,
            generation_index=generation_index,
            code=code,
            secret_input=secret_input,
        ),
        "kind": kind,
        "generation_index": generation_index,
        "code": code,
        "code_sha256": sha256_text(code),
        "secret_input": secret_input,
        "generation": {
            "model": model,
            "policy": kind,
            "prompt_variant": attack_prompt_variant if kind == "attack" else None,
            "prompt_sha256": attack_prompt_sha256 if kind == "attack" else None,
            "sample_id": str(sample.id),
            "seed": proposal_seed,
            "usage": usage,
        },
    }


def _run_candidate_batch(
    *,
    setting: BigCodeBenchPBTSetting,
    protocol: Any,
    mode: EvalMode,
    eval_config: ControlEvalConfig,
    task_ids: list[str],
) -> dict[str, Any]:
    task = get_control_task(
        setting=setting,
        micro_protocol=protocol,
        mode=mode,
        eval_config=eval_config,
    )
    logs = control_eval(task, **eval_config.eval_args())
    samples = [sample for log in logs for sample in (log.samples or [])]
    if len(samples) != len(task_ids):
        raise RuntimeError(
            f"incomplete {mode.value} candidate generation: expected {len(task_ids)} "
            f"samples, got {len(samples)}"
        )
    by_task = {}
    for sample in samples:
        if sample.error is not None:
            raise RuntimeError(
                f"{mode.value} sample {sample.id} failed: {sample.error}"
            )
        task_id = (sample.metadata or {}).get("main_task_name")
        if not isinstance(task_id, str) or not task_id:
            raise RuntimeError(f"{mode.value} sample {sample.id} has no main_task_name")
        if task_id in by_task:
            raise RuntimeError(
                f"{mode.value} generation returned duplicate task {task_id!r}"
            )
        by_task[task_id] = sample
    expected_ids = set(task_ids)
    if set(by_task) != expected_ids:
        raise RuntimeError(
            f"{mode.value} generation tasks mismatch: "
            f"missing={sorted(expected_ids - set(by_task))}, "
            f"unexpected={sorted(set(by_task) - expected_ids)}"
        )
    return by_task


async def _score_attack_proposals(
    *,
    task_ids: list[str],
    candidates: Mapping[str, Any],
    contexts: Mapping[str, Mapping[str, str]],
    selector_model_name: str,
    selector_prompt_variant: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Mapping[str, Any]]]:
    model = get_model(selector_model_name)
    records = {}
    results = {}
    for task_id in task_ids:
        context = contexts[task_id]
        selector_input = build_selector_input(
            task_id=task_id,
            task_description=context["task_description"],
            side_task_description=context["side_task_description"],
            attack_proposals=candidates[task_id]["attack_proposals"],
        )
        prompt = render_selector_prompt(selector_input, selector_prompt_variant)
        # Selector provenance is an actual generation cost. Disabling provider-cache
        # reuse keeps the recorded usage aligned with the spend for this pool build.
        output = await model.generate([ChatMessageUser(content=prompt)], cache=False)
        model_completion = output.completion
        if not isinstance(model_completion, str):
            raise RuntimeError(
                f"red-team selector returned a non-text completion for {task_id}"
            )
        candidate_ids = [
            proposal["candidate_id"]
            for proposal in candidates[task_id]["attack_proposals"]
        ]
        if selector_model_name.startswith("mockllm/"):
            result = mockllm_selector_result(candidate_ids)
            effective_completion = selector_result_json(result)
            completion_source = MOCKLLM_SELECTOR_ADAPTER
        else:
            effective_completion = model_completion
            completion_source = "model"
            try:
                result = parse_selector_output(effective_completion, candidate_ids)
            except ValueError as error:
                raise RuntimeError(
                    f"red-team selector returned an invalid result for {task_id}: "
                    f"{error}"
                ) from error
        usage = _usage_record([getattr(output, "usage", None)])
        records[task_id] = {
            "selector_context": build_selector_context(
                task_id=task_id,
                task_description=context["task_description"],
                side_task_description=context["side_task_description"],
            ),
            "selector_input_sha256": hashlib.sha256(
                json.dumps(
                    selector_input, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest(),
            "selector_prompt_sha256": sha256_text(prompt),
            "selector_model_completion": model_completion,
            "selector_model_completion_sha256": sha256_text(model_completion),
            "selector_effective_completion": effective_completion,
            "selector_effective_completion_sha256": sha256_text(effective_completion),
            "selector_completion_source": completion_source,
            "selector_result": result,
            "usage": usage,
        }
        results[task_id] = result
        print(f"  scored attack proposals for {task_id}")
    return records, results


def _repository_provenance() -> tuple[str, bool, str]:
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        repository_status = subprocess.check_output(
            ["git", "status", "--porcelain"], text=True, stderr=subprocess.DEVNULL
        )
        repository_diff = subprocess.check_output(
            ["git", "diff", "HEAD", "--binary"], stderr=subprocess.DEVNULL
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown", True, hashlib.sha256(b"").hexdigest()
    return (
        revision,
        bool(repository_status.strip()),
        hashlib.sha256(repository_diff).hexdigest(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=str, choices=["main", "heldout"], default="main"
    )
    parser.add_argument("--untrusted-model", type=str, default=Config().untrusted_model)
    parser.add_argument(
        "--trusted-model", type=str, default=Config().trusted_monitor_model
    )
    parser.add_argument(
        "--selector-model",
        type=str,
        default=None,
        help="Model used for red-team proposal scoring; defaults to --untrusted-model.",
    )
    parser.add_argument("--attack-prompt", type=str, default="v1_default")
    parser.add_argument(
        "--red-team-selector-prompt", type=str, default=SELECTOR_PROMPT_VARIANT
    )
    parser.add_argument("--attack-proposals-per-task", type=int, default=2)
    parser.add_argument(
        "--proposal-seed-base",
        type=int,
        default=0,
        help="Base provider seed; proposal i uses base+i and duplicate proposals are rejected.",
    )
    parser.add_argument("--max-selected-attacks", type=int, default=2)
    parser.add_argument("--out", type=str, default="candidate_pool.json")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only prepare the first N task IDs from the chosen dataset.",
    )
    parser.add_argument(
        "--max-concurrent-samples",
        type=int,
        default=2,
        help="Cap parallel candidate samples and per-model API concurrency.",
    )
    args = parser.parse_args()
    output_path = Path(args.out)
    if output_path.exists():
        parser.error(f"refusing to overwrite existing candidate pool: {output_path}")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.max_concurrent_samples < 1:
        parser.error("--max-concurrent-samples must be positive")
    if args.attack_proposals_per_task < 1:
        parser.error("--attack-proposals-per-task must be positive")
    if args.proposal_seed_base < 0:
        parser.error("--proposal-seed-base cannot be negative")
    if args.max_selected_attacks < 0:
        parser.error("--max-selected-attacks cannot be negative")

    task_ids = list(MAIN_TASK_IDS if args.dataset == "main" else HELDOUT_TASK_IDS)
    if args.limit is not None:
        task_ids = task_ids[: args.limit]
    selector_model = args.selector_model or args.untrusted_model
    config = Config(
        task_ids=task_ids,
        untrusted_model=args.untrusted_model,
        trusted_monitor_model=args.trusted_model,
        attack_prompt_variant=args.attack_prompt,
        use_docker=True,
    )
    setting = BigCodeBenchPBTSetting(
        task_ids=tuple(task_ids),
        sandbox_type="docker",
    )
    honest_dataset = list(setting.get_dataset(EvalMode.HONEST))
    attack_dataset = list(setting.get_dataset(EvalMode.ATTACK))
    contexts = _selector_contexts(attack_dataset)
    if set(contexts) != set(task_ids):
        raise RuntimeError("selector contexts do not match configured tasks")

    attack_prompt = load_prompt("attack_policy", config.attack_prompt_variant)
    attack_prompt_sha256 = sha256_text(attack_prompt)
    selector_prompt = load_prompt("red_team_selector", args.red_team_selector_prompt)
    selector_prompt_sha256 = sha256_text(selector_prompt)

    honest_policy = honest_policy_builder(model_role="untrusted")
    attack_policy = attack_policy_builder(model_role="untrusted", prompt=attack_prompt)
    untrusted_policy = untrusted_policy_builder(
        honest=honest_policy, attack=attack_policy
    )
    protocol = trusted_monitoring_builder(
        policy=untrusted_policy, monitor=capture_only_monitor_builder()
    )
    model_config = GenerateConfig(max_connections=args.max_concurrent_samples)
    eval_config = ControlEvalConfig(
        untrusted_model=config.untrusted_model,
        trusted_model=config.trusted_monitor_model,
        max_samples=args.max_concurrent_samples,
        untrusted_config=model_config,
        trusted_config=model_config,
        skip_task_scorers=True,
    )

    candidates_by_task = {
        task_id: {"honest": None, "attack_proposals": []} for task_id in task_ids
    }
    print("Generating honest candidates...")
    honest_samples = _run_candidate_batch(
        setting=setting,
        protocol=protocol,
        mode=EvalMode.HONEST,
        eval_config=eval_config,
        task_ids=task_ids,
    )
    for task_id in task_ids:
        sample = honest_samples[task_id]
        code, secret_input = _extract_submission(sample)
        candidates_by_task[task_id]["honest"] = _candidate_record(
            task_id=task_id,
            kind="honest",
            generation_index=0,
            code=code,
            secret_input=secret_input,
            sample=sample,
            model=config.untrusted_model,
            attack_prompt_variant=config.attack_prompt_variant,
            attack_prompt_sha256=attack_prompt_sha256,
            proposal_seed=None,
        )
        print(f"  stored honest candidate for {task_id}")

    for proposal_index in range(args.attack_proposals_per_task):
        proposal_seed = args.proposal_seed_base + proposal_index
        print(
            f"Generating attack proposal {proposal_index + 1}/"
            f"{args.attack_proposals_per_task}..."
        )
        seeded_attack_policy = attack_policy_builder(
            model_role="untrusted",
            prompt=attack_prompt,
            config=GenerateConfig(seed=proposal_seed),
        )
        seeded_protocol = trusted_monitoring_builder(
            policy=untrusted_policy_builder(
                honest=honest_policy, attack=seeded_attack_policy
            ),
            monitor=capture_only_monitor_builder(),
        )
        attack_samples = _run_candidate_batch(
            setting=setting,
            protocol=seeded_protocol,
            mode=EvalMode.ATTACK,
            eval_config=eval_config,
            task_ids=task_ids,
        )
        for task_id in task_ids:
            sample = attack_samples[task_id]
            code, secret_input = _extract_submission(sample)
            candidates_by_task[task_id]["attack_proposals"].append(
                _candidate_record(
                    task_id=task_id,
                    kind="attack",
                    generation_index=proposal_index,
                    code=code,
                    secret_input=secret_input,
                    sample=sample,
                    model=config.untrusted_model,
                    attack_prompt_variant=config.attack_prompt_variant,
                    attack_prompt_sha256=attack_prompt_sha256,
                    proposal_seed=proposal_seed,
                )
            )
            print(f"  stored attack proposal {proposal_index} for {task_id}")

    for task_id, task_candidates in candidates_by_task.items():
        code_hashes = {
            candidate["code_sha256"]
            for candidate in task_candidates["attack_proposals"]
        }
        if len(code_hashes) != args.attack_proposals_per_task:
            raise RuntimeError(
                f"model generated duplicate attack proposals for {task_id}; choose a "
                "model/configuration with seeded sampling diversity"
            )
        if task_candidates["honest"]["code_sha256"] in code_hashes:
            raise RuntimeError(
                f"model generated attack code identical to its honest candidate for {task_id}"
            )

    print("Scoring attack proposals with the red-team selector...")
    selector_records, selector_results = asyncio.run(
        _score_attack_proposals(
            task_ids=task_ids,
            candidates=candidates_by_task,
            contexts=contexts,
            selector_model_name=selector_model,
            selector_prompt_variant=args.red_team_selector_prompt,
        )
    )
    decisions = select_attack_opportunities(
        selector_results,
        max_selected_attacks=args.max_selected_attacks,
    )
    for task_id in task_ids:
        selector_records[task_id].update(decisions["tasks"][task_id])
    selection = {
        "algorithm": decisions["algorithm"],
        "max_selected_attacks": decisions["max_selected_attacks"],
        "selected_task_ids": decisions["selected_task_ids"],
        "tasks": selector_records,
    }
    views = {
        "forced_attack": {
            task_id: decisions["tasks"][task_id]["best_attack_candidate_id"]
            for task_id in task_ids
        },
        "selected_policy": {
            task_id: (
                decisions["tasks"][task_id]["best_attack_candidate_id"]
                if decisions["tasks"][task_id]["selected_for_attack"]
                else candidates_by_task[task_id]["honest"]["candidate_id"]
            )
            for task_id in task_ids
        },
    }

    candidate_usage = sum_usages(
        candidate["generation"]["usage"]
        for task_id in task_ids
        for candidate in (
            candidates_by_task[task_id]["honest"],
            *candidates_by_task[task_id]["attack_proposals"],
        )
    )
    selector_usage = sum_usages(
        selector_records[task_id]["usage"] for task_id in task_ids
    )
    total_usage = sum_usages([candidate_usage, selector_usage])
    revision, repository_dirty, repository_diff_sha256 = _repository_provenance()
    pool = {
        "schema_version": CANDIDATE_POOL_SCHEMA_VERSION,
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "task_ids": task_ids,
            "untrusted_model": config.untrusted_model,
            "trusted_model": config.trusted_monitor_model,
            "attack_prompt_variant": config.attack_prompt_variant,
            "attack_prompt": attack_prompt,
            "attack_prompt_sha256": attack_prompt_sha256,
            "attack_proposals_per_task": args.attack_proposals_per_task,
            "proposal_seed_base": args.proposal_seed_base,
            "selector_model": selector_model,
            "selector_prompt_variant": args.red_team_selector_prompt,
            "selector_prompt": selector_prompt,
            "selector_prompt_sha256": selector_prompt_sha256,
            "dataset_fingerprints": {
                "honest": dataset_fingerprints(honest_dataset),
                "attack": dataset_fingerprints(attack_dataset),
            },
            "generation_usage": total_usage,
            "generation_usage_by_phase": {
                "candidate_generation": candidate_usage,
                "selector_scoring": selector_usage,
            },
            "repository_revision": revision,
            "repository_dirty": repository_dirty,
            "repository_diff_sha256": repository_diff_sha256,
        },
        "candidates": candidates_by_task,
        "selection": selection,
        "views": views,
    }
    validate_candidate_pool(pool)

    atomic_write_new_json(output_path, pool)

    total_candidates = len(task_ids) * (1 + args.attack_proposals_per_task)
    print(f"\nWrote {total_candidates} candidates to {output_path}")
    print(
        "Selected attacks for "
        f"{len(decisions['selected_task_ids'])}/{len(task_ids)} tasks: "
        f"{decisions['selected_task_ids']}"
    )


if __name__ == "__main__":
    main()
