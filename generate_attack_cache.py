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
import json

from control_arena import EvalMode
from control_arena.eval import ControlEvalConfig, get_control_task, eval as control_eval
from control_arena.micro_protocol import trusted_monitoring_builder
from control_arena.monitor import basic_monitor_builder
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
    parser.add_argument("--docker", action="store_true")
    parser.add_argument("--out", type=str, default="attack_cache.json")
    args = parser.parse_args()

    task_ids = MAIN_TASK_IDS if args.dataset == "main" else HELDOUT_TASK_IDS
    config = Config(
        task_ids=task_ids,
        untrusted_model=args.untrusted_model,
        trusted_monitor_model=args.trusted_model,
        attack_prompt_variant=args.attack_prompt,
        use_docker=args.docker,
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
    # Cheapest real protocol shape that still exercises the actual policy prompts -
    # we only keep the policy's own submission, the monitor here is scaffolding.
    proto = trusted_monitoring_builder(
        policy=untrusted_pol, monitor=basic_monitor_builder(model_role="trusted")
    )
    eval_cfg = ControlEvalConfig(
        untrusted_model=config.untrusted_model, trusted_model=config.trusted_monitor_model
    )

    cache: dict[str, dict[str, dict]] = {"honest": {}, "attack": {}}
    for mode, mode_key in [(EvalMode.HONEST, "honest"), (EvalMode.ATTACK, "attack")]:
        print(f"Generating {mode_key} submissions...")
        task = get_control_task(
            setting=setting, micro_protocol=proto, mode=mode, eval_config=eval_cfg
        )
        logs = control_eval(task)
        if not logs or not logs[0].samples:
            print(f"  WARNING: no samples returned for {mode_key} mode")
            continue

        for s in logs[0].samples:
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
                print(f"  WARNING: no submission captured for sample {s.id}")
                continue
            entry = {"code": code}
            if secret_input is not None:
                entry["secret_input"] = secret_input
            cache[mode_key][main_task_name] = entry
            print(f"  cached {mode_key}/{main_task_name}")

    with open(args.out, "w") as f:
        json.dump(cache, f, indent=2)

    total = sum(len(v) for v in cache.values())
    print(f"\nWrote {total} cached submissions to {args.out}")


if __name__ == "__main__":
    main()
