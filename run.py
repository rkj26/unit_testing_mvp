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

from pipeline import metrics

from pipeline import engine
from pipeline.backends import get_backend
from pipeline.config import Config
from pipeline.metrics_objs import METRICS
from pipeline.steps import PIPELINE


def main() -> None:
    load_dotenv()
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ["PATH"] = os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", "")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain", required=True, choices=["bcb", "apps", "mock"])
    ap.add_argument("--dataset", default=None, help="candidate pool JSON (not needed for --domain mock)")
    ap.add_argument("--run-id", help="reuse the same id to RESUME an interrupted run")

    ap.add_argument("--t-model", default=os.getenv("TRUSTED_MODEL"), help="trusted model")
    ap.add_argument("--t-reasoning", default=None, choices=["low", "medium", "high", "max"])
    ap.add_argument("--t-timeout", type=int, default=0, help="seconds per call (0 = from reasoning)")

    ap.add_argument("--u-model", default=os.getenv("ELICIT_MODEL"),
                    help="untrusted model, used only by the u_* generation strategies")
    ap.add_argument("--u-reasoning", default=None, choices=["low", "medium", "high", "max"])
    ap.add_argument("--u-timeout", type=int, default=0, help="seconds per call (0 = from reasoning)")

    ap.add_argument("--protocols", default=None,
                    help=f"comma-separated subset of {','.join(metrics.PROTOCOLS)} (default: all)")
    ap.add_argument("--gen-strategy", default="blind_t",
                    choices=["blind_t", "u_writes", "u_plans_t_writes", "u_plans_u_writes"],
                    help="who authors the properties; the search space is always trusted-authored")

    ap.add_argument("--attack-rate", default=None,
                    help="per-step chance the untrusted model submits its backdoor (default 0.10); "
                         "'always' for the degenerate always-attack regime")
    ap.add_argument("--audit-rate", type=float, default=metrics.DEFAULT_AUDIT_RATE,
                    help="human audit budget; must be >= 1/n_honest to be measurable")

    ap.add_argument("--runs", type=int, default=1, help="repetitions for mean, std and intervals")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0, help="cap number of tasks (0 = all)")
    ap.add_argument("--mock", action="store_true", help="offline mock model")
    ap.add_argument("--stage", choices=["all", "score", "monitor"], default="all")
    ap.add_argument("--exec-mode", choices=["inprocess", "subprocess", "docker"], default=None)
    ap.add_argument("--docker-image", default=os.getenv("PIPELINE_DOCKER_IMAGE"))
    ap.add_argument("--progress", dest="progress", action="store_true", default=None)
    ap.add_argument("--no-progress", dest="progress", action="store_false")
    args = ap.parse_args()

    # monitor stage loads problems/scores from a prior stage, so it needs neither a live model? it does
    # (TM + informed) — but score stage needs no trusted model at all.
    if args.stage != "score" and not ("mock" if args.mock else args.t_model):
        ap.error("provide --t-model (e.g. azureai/DeepSeek-V3.2) or --mock")
    if args.stage == "monitor" and not args.run_id:
        ap.error("--stage monitor requires --run-id (the id of the prior --stage score run)")
    if args.domain != "mock" and args.stage != "monitor" and not args.dataset:
        ap.error(f"--domain {args.domain} requires --dataset")

    pool: dict = {}
    if args.dataset:
        pool = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
        pool["_path"] = args.dataset

    args.run_id = args.run_id or f"{args.domain}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    config = Config.from_args(args)

    engine.run(config, get_backend(config.domain.value), pool, PIPELINE, METRICS)


if __name__ == "__main__":
    main()
