"""Generic isolated worker — runs one unit of the pipeline in a fresh process.

Spawned by the engine's `run_isolated` (subprocess or Docker). One entrypoint covers both isolated
units, selected by the second argument:
  python -m pipeline.worker <run_dir> once <step_name>  -> run one ONCE step (e.g. control_eval scoring)
  python -m pipeline.worker <run_dir> run  <r>          -> run all PER_RUN steps for run index r

It rebuilds the `Config` from `run.json` (the single source of truth), reloads the backend + pool from
that config, and reads/writes everything through the artifact store — so a fresh process shares no
in-memory state with the parent (the whole point of isolation).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from .artifacts import read_json
from .backends import get_backend
from .config import Config
from .engine import execute_once, execute_run
from .steps import PIPELINE


def main() -> None:
    """Dispatch to a ONCE step or the per-run executor based on argv (`<run_dir> once|run <arg>`)."""
    load_dotenv()
    run_dir = Path(sys.argv[1])
    mode = sys.argv[2]
    arg = sys.argv[3]
    config = Config.from_json(read_json(run_dir / "run.json"))
    if mode == "once":
        backend = get_backend(config.domain.value)
        execute_once(config, run_dir, arg, PIPELINE, backend, _load_pool(config))
    elif mode == "run":
        execute_run(config, int(arg), PIPELINE, run_dir)
    else:
        raise SystemExit(f"worker: unknown mode {mode!r} (expected 'once' or 'run')")


def _load_pool(config: Config) -> dict:
    """Reload the candidate pool a ONCE step may need, from the path recorded in run.json."""
    if not config.dataset:
        return {}
    pool = json.loads(Path(config.dataset).read_text(encoding="utf-8"))
    pool["_path"] = config.dataset
    return pool


if __name__ == "__main__":
    main()
