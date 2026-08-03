"""Ground-truth scoring in an ISOLATED subprocess.

control_arena scores via inspect's ``eval()``, which leaves global asyncio state that wedges the
trusted-model calls we make later in the same process. So the orchestrator runs this step as its own
short-lived process: read problems.json, score, write scores.json, exit — taking the poisoned async
state down with it.

Usage:  python -m pipeline.scoring_worker <run_dir> <domain>
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: python -m pipeline.scoring_worker <run_dir> <domain>", file=sys.stderr)
        return 2
    run_dir = Path(sys.argv[1])
    domain = sys.argv[2]

    from dotenv import load_dotenv

    load_dotenv()
    # control_arena's local sandbox shells out to python3; keep it on this venv (mirrors run.py).
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ["PATH"] = os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", "")

    from pipeline import state
    from pipeline.backends import get_backend

    problems = state.load_problems(run_dir)
    if not problems:
        print(f"scoring_worker: no problems.json under {run_dir}", file=sys.stderr)
        return 3

    scores = get_backend(domain).score_candidates(problems)
    state.save_scores(run_dir, scores)
    print(f"scoring_worker: wrote scores.json for {len(scores)} candidates", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
