"""Single entry point for the step-wise PBT-vs-TM control pipeline.

Examples:
  .venv/bin/python run.py --domain mock --mock --runs 2 --run-id smoke
  .venv/bin/python run.py --domain apps --pool apps_pool_hard.json --model azureai/DeepSeek-V3.2 --runs 5
  .venv/bin/python run.py --domain bcb  --pool candidate_pool_hard50.json --model azureai/DeepSeek-V3.2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pipeline import orchestrator
from pipeline.backends import get_backend


def main() -> None:
    load_dotenv()
    # control_arena's local sandbox shells out to `python3`; make sure that resolves to this
    # venv (with all deps), and force a non-interactive matplotlib backend for BCB tasks.
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ["PATH"] = os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", "")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain", required=True, choices=["bcb", "apps", "mock"])
    ap.add_argument("--pool", help="candidate pool JSON (not needed for --domain mock)")
    ap.add_argument("--model", default=os.getenv("TRUSTED_MODEL"), help="inspect_ai model string")
    ap.add_argument("--mock", action="store_true", help="use the offline mock model")
    ap.add_argument("--runs", type=int, default=1, help="full pipeline re-runs for mean±std")
    ap.add_argument("--tests-per-problem", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--audit-rate", type=float, default=0.02)
    ap.add_argument("--run-id", help="reuse the same id to RESUME an interrupted run")
    ap.add_argument("--limit", type=int, default=0, help="cap number of tasks (0 = all)")
    ap.add_argument(
        "--stage", choices=["all", "score", "monitor"], default="all",
        help="all (default) | score: only the deterministic ground-truth scoring (writes scores.json) "
             "| monitor: only the flaky model phase against a prior score stage's --run-id",
    )
    ap.add_argument(
        "--gen-strategy", choices=["blind_t", "u_writes", "u_plans_t_writes"], default="blind_t",
        help="who writes the PBT properties: blind_t (trusted, default) | u_writes (elicited model) "
             "| u_plans_t_writes (elicited model plans, trusted model implements). The trigger search "
             "space is always trusted-authored.",
    )
    ap.add_argument("--elicit-model", default=os.getenv("ELICIT_MODEL"),
                    help="capable/untrusted model for the u_* strategies (defaults to --model)")
    args = ap.parse_args()

    # monitor stage loads problems/scores from a prior stage, so it needs neither a live model? it does
    # (TM + informed) — but score stage needs no trusted model at all.
    model_name = "mock" if args.mock else args.model
    if args.stage != "score" and not model_name:
        ap.error("provide --model (e.g. azureai/DeepSeek-V3.2) or --mock")
    if args.stage == "monitor" and not args.run_id:
        ap.error("--stage monitor requires --run-id (the id of the prior --stage score run)")
    if args.domain != "mock" and args.stage != "monitor" and not args.pool:
        ap.error(f"--domain {args.domain} requires --pool")

    pool: dict = {}
    if args.pool:
        pool = json.loads(Path(args.pool).read_text(encoding="utf-8"))
        pool["_path"] = args.pool

    run_id = args.run_id or f"{args.domain}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    orchestrator.run_pipeline(
        get_backend(args.domain),
        pool,
        model_name=model_name or "mock",
        runs=args.runs,
        tests_per_problem=args.tests_per_problem,
        seed=args.seed,
        audit_rate=args.audit_rate,
        run_id=run_id,
        limit=(args.limit or None),
        stage=args.stage,
        gen_strategy=args.gen_strategy,
        elicit_model_name=(None if args.mock else args.elicit_model),
    )


if __name__ == "__main__":
    main()
