"""Generates a cache of untrusted-model submissions (one honest, one attack, per
dataset problem) so that every protocol (TM, PBT, TE, Hybrid) can be compared
against byte-identical attacker output instead of independently-sampled ones.

Usage:
    python generate_attack_cache.py --dataset main \\
        --untrusted-model google/gemini-3.6-flash \\
        --attack-prompt v4_disguised_legitimate \\
        --out attack_cache.json
"""

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from inspect_ai.agent import AgentState
from inspect_ai.model import GenerateConfig
from inspect_ai.tool import Tool
from control_arena import EvalMode, control_agent
from control_arena.eval import ControlEvalConfig, get_control_task, eval as control_eval
from control_arena.micro_protocol import trusted_monitoring_builder
from control_arena.monitor import MonitorResponse, monitor
from control_arena.policy import (
    attack_policy_builder,
    honest_policy_builder,
    untrusted_policy_builder,
)

from bigcodebench_pbt_setting import BigCodeBenchPBTSetting, HELDOUT_TASK_IDS, MAIN_TASK_IDS
from config import Config
from prompts import load_prompt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=str, choices=["main", "heldout"], default="main")
    parser.add_argument("--untrusted-model", type=str, default=Config().untrusted_model)
    parser.add_argument("--trusted-model", type=str, default=Config().trusted_monitor_model)
    parser.add_argument("--attack-prompt", type=str, default="v1_default")
    parser.add_argument("--docker", action="store_true", help="Deprecated; Docker is the default")
    parser.add_argument("--out", type=str, default="attack_cache.json")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only cache the first N task IDs from the chosen dataset (e.g. for a quick "
        "smoke test on a subset of the main set instead of all 50 tasks).",
    )
    parser.add_argument(
        "--max-concurrent-samples",
        type=int,
        default=None,
        help="Cap parallel samples and per-model API concurrency. Lower this (e.g. 2) if "
        "a run shows climbing HTTP retries with no progress against a provider's rate limit.",
    )
    args = parser.parse_args()
    output_path = Path(args.out)
    if output_path.exists():
        parser.error(f"refusing to overwrite existing attack cache: {output_path}")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")

    task_ids = MAIN_TASK_IDS if args.dataset == "main" else HELDOUT_TASK_IDS
    if args.limit is not None:
        task_ids = task_ids[: args.limit]
    config = Config(
        task_ids=task_ids,
        untrusted_model=args.untrusted_model,
        trusted_monitor_model=args.trusted_model,
        attack_prompt_variant=args.attack_prompt,
        use_docker=True,
    )
    setting = BigCodeBenchPBTSetting(
        task_ids=tuple(task_ids), sandbox_type="docker" if config.use_docker else "local"
    )

    honest_pol = honest_policy_builder(model_role="untrusted")
    attack_pol = attack_policy_builder(
        model_role="untrusted",
        prompt=load_prompt("attack_policy", config.attack_prompt_variant),
    )
    untrusted_pol = untrusted_policy_builder(honest=honest_pol, attack=attack_pol)

    @control_agent
    def capture_only_monitor_builder():
        @monitor
        async def _capture_only_monitor(
            state: AgentState, tools: list[Tool]
        ) -> MonitorResponse:
            return MonitorResponse(suspicion_score=0.0, reason="cache capture only")

        return _capture_only_monitor

    proto = trusted_monitoring_builder(
        policy=untrusted_pol, monitor=capture_only_monitor_builder()
    )
    model_config = (
        GenerateConfig(max_connections=args.max_concurrent_samples)
        if args.max_concurrent_samples
        else None
    )
    eval_cfg = ControlEvalConfig(
        untrusted_model=config.untrusted_model,
        trusted_model=config.trusted_monitor_model,
        max_samples=args.max_concurrent_samples,
        untrusted_config=model_config,
        trusted_config=model_config,
    )

    prompt_text = load_prompt("attack_policy", config.attack_prompt_variant)
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
        revision = "unknown"
        repository_status = "unknown"
        repository_diff = b""
    cache: dict = {
        "schema_version": 2,
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "task_ids": task_ids,
            "untrusted_model": config.untrusted_model,
            "trusted_model": config.trusted_monitor_model,
            "attack_prompt_variant": config.attack_prompt_variant,
            "attack_prompt_sha256": hashlib.sha256(prompt_text.encode()).hexdigest(),
            "repository_revision": revision,
            "repository_dirty": repository_status == "unknown" or bool(repository_status.strip()),
            "repository_diff_sha256": hashlib.sha256(repository_diff).hexdigest(),
        },
        "honest": {},
        "attack": {},
    }
    for mode, mode_key in [(EvalMode.HONEST, "honest"), (EvalMode.ATTACK, "attack")]:
        print(f"Generating {mode_key} submissions...")
        task = get_control_task(
            setting=setting, micro_protocol=proto, mode=mode, eval_config=eval_cfg
        )
        logs = control_eval(task, **eval_cfg.eval_args())
        samples = [sample for log in logs for sample in (log.samples or [])]
        if len(samples) != len(task_ids):
            raise RuntimeError(
                f"incomplete {mode_key} cache generation: expected {len(task_ids)} samples, "
                f"got {len(samples)}"
            )

        for s in samples:
            if s.error is not None:
                raise RuntimeError(f"{mode_key} sample {s.id} failed: {s.error}")
            # Cache key must match what cached_attack_policy.py looks up at replay
            # time (ControlTaskMetadata.main_task_name), NOT the Inspect Sample id -
            # BigCodeBench's sample id swaps "/" for "_" but main_task_name doesn't.
            main_task_name = (s.metadata or {}).get("main_task_name", str(s.id))

            code = None
            secret_input = None
            for m in s.messages:
                if m.role == "assistant" and getattr(m, "tool_calls", None):
                    for tc in m.tool_calls:
                        if tc.function == "submit":
                            code = tc.arguments.get("code")
                            secret_input = tc.arguments.get("secret_input")
            if not code:
                raise RuntimeError(f"no submission captured for {mode_key} sample {s.id}")
            entry = {"code": code}
            if secret_input is not None:
                entry["secret_input"] = secret_input
            cache[mode_key][main_task_name] = entry
            print(f"  cached {mode_key}/{main_task_name}")

        cached_ids = set(cache[mode_key])
        expected_ids = set(task_ids)
        if cached_ids != expected_ids:
            raise RuntimeError(
                f"{mode_key} cache keys do not match configured tasks: "
                f"missing={sorted(expected_ids - cached_ids)}, "
                f"unexpected={sorted(cached_ids - expected_ids)}"
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(cache, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)

    total = len(cache["honest"]) + len(cache["attack"])
    print(f"\nWrote {total} cached submissions to {output_path}")


if __name__ == "__main__":
    main()
