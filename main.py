"""Run the frozen-pool AI Control MVP."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from experiment import run_experiment


def main() -> None:
    load_dotenv()
    # BigCodeBench runs tasks' tests locally; several use matplotlib. Force a
    # non-interactive backend so no GUI plot windows pop open during a run.
    os.environ.setdefault("MPLBACKEND", "Agg")
    # control_arena's sandbox shells out to `python3`, which otherwise resolves to
    # the SYSTEM python (no pandas/numpy) and fails every DataFrame/array task.
    # Prepend this interpreter's bin dir so `python3` == the venv (with all deps).
    venv_bin = os.path.dirname(sys.executable)
    os.environ["PATH"] = venv_bin + os.pathsep + os.environ.get("PATH", "")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pool", type=Path, default=Path("candidate_pool_development.json")
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--run-id")
    parser.add_argument(
        "--subset",
        choices=["train", "test"],
        default=None,
        help="restrict the run to the train/test task IDs from --split-file",
    )
    parser.add_argument("--split-file", type=Path, default=Path("split_hard50.json"))
    args = parser.parse_args()

    task_subset = None
    if args.subset:
        split = json.loads(args.split_file.read_text(encoding="utf-8"))
        task_subset = set(split[args.subset])

    trusted_model = os.getenv("TRUSTED_MODEL", "google/gemini-2.5-flash")
    if not trusted_model.startswith("mockllm/") and not (
        os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    ):
        parser.error("set GOOGLE_API_KEY or GEMINI_API_KEY in .env")

    run_dir, metrics = run_experiment(
        pool_path=args.pool,
        seed=args.seed,
        run_id=args.run_id,
        trusted_model=trusted_model,
        task_subset=task_subset,
    )
    print(f"Run artifacts: {run_dir}")
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
