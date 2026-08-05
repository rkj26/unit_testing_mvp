"""Single entry point for the step-wise PBT-vs-TM control pipeline.

Examples:
  .venv/bin/python run.py --domain mock --mock --runs 2 --run-id smoke
  .venv/bin/python run.py --domain apps --dataset apps_pool_hard.json --t-model azureai/DeepSeek-V3.2 --runs 5
  .venv/bin/python run.py --domain apps --dataset apps_pool_hard.json --t-model azureai/DeepSeek-V3.2 \
      --u-model openai-api/azureai/gpt-5.4 --u-reasoning high --gen-strategy u_plans_t_writes

Every flag is also an environment variable of the same name in upper case (T_MODEL, AUDIT_RATE, ...).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

from pipeline import engine
from pipeline.backends import get_backend
from pipeline.config import Settings
from pipeline.steps import get_pipeline


def _prevent_system_sleep() -> None:
    """Hold a macOS power assertion for this process's lifetime."""
    if sys.platform != "darwin":
        return
    try:
        subprocess.Popen(
            ["caffeinate", "-dimsu", "-w", str(os.getpid())],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as error:
        print(
            f"run.py: could not prevent sleep ({error}); a long sleep may degrade units"
        )


def main() -> None:
    load_dotenv()
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ["PATH"] = (
        os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", "")
    )

    try:
        settings = Settings()
    except ValidationError as error:
        raise SystemExit(f"run.py: {error}")

    if not settings.allow_sleep:
        _prevent_system_sleep()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    config = settings.to_config(settings.run_id or f"{settings.domain.value}-{stamp}")

    pool: dict = {}
    if config.dataset:
        pool = json.loads(Path(config.dataset).read_text(encoding="utf-8"))
        pool["_path"] = config.dataset

    backend = get_backend(config.domain.value)
    engine.run(config, backend, pool, get_pipeline())


if __name__ == "__main__":
    main()
