"""Execute ONE run-index in an isolated subprocess.

The parent (orchestrator._run_all) spawns this per run under a wall-clock timeout. A fresh process per
run is what makes the pipeline robust: httpx connection pools, abandoned daemon threads, and inspect's
asyncio state cannot accumulate across runs and wedge a later one (the failure mode when all runs
shared a single long-lived process — run 0 was clean, run 1 hung with the hard call-timeout never
firing). All per-run output is still checkpointed to disk (suite.json / rows.jsonl / metrics.json), so
a killed-and-resumed run continues from partial progress, and the parent reloads via
state.load_run_complete once this child exits 0.

Usage:  python -m pipeline.run_worker <run_dir> <r>
Everything else (model, elicit-model, gen-strategy, seed, tests, audit) is read from <run_dir>/run.json,
which the orchestrator writes before the run loop.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from . import metrics as metrics_mod
from . import model as model_mod
from . import state
from .orchestrator import _heartbeat, _one_run, log


def main() -> None:
    run_dir = Path(sys.argv[1])
    r = int(sys.argv[2])

    cfg = state.read_json(run_dir / "run.json") or {}
    model_name = cfg["model"]
    elicit_model_name = cfg.get("elicit_model") or None
    gen_strategy = cfg.get("gen_strategy", "blind_t")
    runs = int(cfg.get("runs", 1))
    seed = int(cfg.get("seed", 0))
    tests_per_problem = int(cfg.get("tests_per_problem", 5))
    audit_rate = float(cfg.get("audit_rate", 0.02))

    problems = state.load_problems(run_dir)
    scores = state.load_scores(run_dir)
    if problems is None or scores is None:
        raise SystemExit("run_worker: problems.json / scores.json missing (run the score stage first)")

    status = state.Status(run_dir)
    temperature = 0.0 if runs == 1 else 0.7  # >0 so K re-runs actually differ
    t_model = model_mod.resolve(model_name, temperature=temperature, seed=seed + r)
    u_model = (model_mod.resolve(elicit_model_name, temperature=temperature, seed=seed + r)
               if elicit_model_name else t_model)
    log(f"run {r}: worker start (strategy={gen_strategy}, temp={temperature}, seed={seed + r})")

    async def _go() -> None:
        beat = asyncio.create_task(_heartbeat(status))
        try:
            rows, validity, soundness, selected = await _one_run(
                problems, scores, t_model, u_model, gen_strategy,
                tests_per_problem, run_dir, r, status)
        finally:
            beat.cancel()
        m = metrics_mod.compute_run_metrics(
            rows, selected, seed=seed + r, suite_validity=validity,
            suite_soundness=soundness, audit_rate=audit_rate)
        state.save_run_complete(run_dir, r, rows, m)  # metrics.json presence == "run done"
        log(f"run {r}: worker complete + checkpointed")

    asyncio.run(_go())


if __name__ == "__main__":
    main()
