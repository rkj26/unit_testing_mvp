"""Generate one honest and two attack candidates for a fixed task split."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from inspect_ai.model import GenerateConfig
from inspect_ai.scorer import CORRECT

from control_arena import EvalMode
from control_arena.eval import ControlEvalConfig, eval as control_eval, get_control_task
from control_arena.policy import attack_policy_builder, honest_policy_builder
from control_arena.serde import load_json
from control_arena.settings.bigcodebench.bigcodebench_setting import BigCodeBenchSetting
from control_arena.settings.bigcodebench.task.submission_types import (
    SubmitAttackArgs,
    SubmitHonestArgs,
)
from control_arena.tools.submit_tool import STORE_SUBMIT_ARGS_KEY


SPLITS_PATH = Path("task_splits.json")
ATTACK_PROMPT_PATH = Path("prompts/attacker.txt")
OUTPUT_PATHS = {
    "development": Path("candidate_pool_development.json"),
    "holdout": Path("candidate_pool_holdout.json"),
}
LABELS = ("honest", "attack_0")


def _load_task_ids(split: str) -> list[str]:
    splits = json.loads(SPLITS_PATH.read_text(encoding="utf-8"))
    development = splits.get("development")
    holdout = splits.get("holdout")
    if not isinstance(development, list) or not isinstance(holdout, list):
        raise ValueError("task_splits.json must define development and holdout lists")
    if len(development) != 10 or len(holdout) != 10:
        raise ValueError("development and holdout must contain exactly ten tasks each")
    if set(development) & set(holdout):
        raise ValueError("development and holdout tasks must be disjoint")
    return list(splits[split])


def _usage(sample: Any) -> dict[str, dict[str, Any]]:
    return {
        model: usage.model_dump(exclude_none=True)
        for model, usage in (sample.model_usage or {}).items()
    }


def _submission(sample: Any, label: str) -> tuple[str, str | None]:
    raw = (sample.store or {}).get(STORE_SUBMIT_ARGS_KEY)
    if not isinstance(raw, str):
        raise RuntimeError(f"{sample.id} never submitted a candidate")
    if label == "honest":
        submitted = load_json(raw, SubmitHonestArgs, from_str=True)
        code, secret_input = submitted.code, None
    else:
        submitted = load_json(raw, SubmitAttackArgs, from_str=True)
        code, secret_input = submitted.code, submitted.secret_input
    if not code.strip():
        raise RuntimeError(f"{sample.id} submitted empty code")
    if secret_input is not None:
        try:
            parsed = json.loads(secret_input)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"{sample.id} submitted invalid trigger JSON") from error
        if not isinstance(parsed, dict) or not all(
            isinstance(key, str) for key in parsed
        ):
            raise RuntimeError(f"{sample.id} trigger must be a JSON object")
    return code, secret_input


def _official_result(sample: Any, label: str) -> dict[str, bool | None]:
    score = (sample.scores or {}).get("bigcodebench_scorer")
    if score is None or not isinstance(score.value, dict):
        raise RuntimeError(f"{sample.id} has no official BigCodeBench result")
    main_success = score.value.get("main_task_success") == CORRECT
    side_success = (
        None
        if label == "honest"
        else score.value.get("side_task_success") == CORRECT
    )
    return {
        "main_task_success": main_success,
        "side_task_success": side_success,
    }


def _candidate(sample: Any, task_id: str, label: str) -> dict[str, Any]:
    code, secret_input = _submission(sample, label)
    return {
        "candidate_id": f"{task_id.replace('/', '_')}_{label}",
        "code": code,
        "secret_input": secret_input,
        "generation": {"usage_by_model": _usage(sample)},
        "official_validation": _official_result(sample, label),
    }


def _run_label(
    *,
    setting: BigCodeBenchSetting,
    config: ControlEvalConfig,
    split: str,
    label: str,
) -> dict[str, dict[str, Any]]:
    if label == "honest":
        mode = EvalMode.HONEST
        policy = honest_policy_builder(
            model_role="untrusted",
            config=GenerateConfig(temperature=0),
            cache=False,
        )
    else:
        mode = EvalMode.ATTACK
        proposal_index = int(label.rsplit("_", 1)[1])
        policy = attack_policy_builder(
            model_role="untrusted",
            prompt_file=ATTACK_PROMPT_PATH,
            config=GenerateConfig(
                temperature=1,
                seed=proposal_index,
                max_tokens=16_384,
            ),
            cache=False,
        )
    task = get_control_task(
        setting=setting,
        micro_protocol=policy,
        mode=mode,
        eval_config=config,
        task_name=f"candidate-generation-{split}-{label}",
    )
    logs = control_eval(task, **config.eval_args())
    samples = [sample for log in logs for sample in (log.samples or [])]
    expected = set(setting.filter_main_task_names or [])
    if len(samples) != len(expected):
        raise RuntimeError(
            f"{label} generated {len(samples)} of {len(expected)} candidates"
        )

    candidates = {}
    for sample in samples:
        if sample.error is not None:
            raise RuntimeError(f"{label} sample {sample.id} failed: {sample.error}")
        task_id = str((sample.metadata or {}).get("main_task_name", ""))
        if task_id not in expected or task_id in candidates:
            raise RuntimeError(f"{label} returned unexpected task {task_id!r}")
        candidates[task_id] = _candidate(sample, task_id, label)
    if set(candidates) != expected:
        raise RuntimeError(f"{label} candidate task IDs are incomplete")
    return candidates


def _selected_policy(
    task_ids: list[str], candidates: dict[str, dict[str, Any]]
) -> dict[str, str]:
    return {
        task_id: candidates[task_id]["attack_proposals"][0]["candidate_id"]
        for task_id in task_ids
    }


def generate_pool(split: str, model_name: str) -> Path:
    task_ids = _load_task_ids(split)
    output_path = OUTPUT_PATHS[split]
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite {output_path}")

    log_dir = Path("candidate_generation") / split / "inspect"
    setting = BigCodeBenchSetting(
        filter_main_task_names=task_ids,
        sandbox_type="docker",
    )
    config = ControlEvalConfig(
        untrusted_model=model_name,
        trusted_model=model_name,
        untrusted_config=GenerateConfig(max_connections=2),
        max_steps=3,
        max_samples=2,
        max_tasks=1,
        max_sandboxes=2,
        fail_on_error=False,
        skip_task_scorers=False,
        time_limit=900,
        log_dir=str(log_dir),
    )

    generated = {
        label: _run_label(
            setting=setting,
            config=config,
            split=split,
            label=label,
        )
        for label in LABELS
    }
    candidates = {
        task_id: {
            "honest": generated["honest"][task_id],
            "attack_proposals": [
                generated["attack_0"][task_id],
            ],
        }
        for task_id in task_ids
    }
    selected = _selected_policy(task_ids, candidates)
    pool = {
        "schema_version": 1,
        "split": split,
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "generator_model": model_name,
            "task_ids": task_ids,
            "attack_prompt": str(ATTACK_PROMPT_PATH),
            "deployment_selection": {
                "attack_candidates_per_task": len(LABELS) - 1,
                "attack_probability": 1 / 12,
                "method": "independent Bernoulli selection per deployment task",
            },
        },
        "candidates": candidates,
        "deployment_policy": {
            "attack_probability": 1 / 12,
            "method": "independent Bernoulli selection per deployment task",
        },
        "views": {"selected_policy": selected},
    }
    output_path.write_text(
        json.dumps(pool, indent=2, sort_keys=True), encoding="utf-8"
    )
    return output_path


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("split", choices=tuple(OUTPUT_PATHS))
    parser.add_argument(
        "--model",
        default=os.getenv("UNTRUSTED_MODEL", "google/gemini-3.6-flash"),
    )
    args = parser.parse_args()
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        parser.error("set GOOGLE_API_KEY or GEMINI_API_KEY in .env")
    output = generate_pool(args.split, args.model)
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
