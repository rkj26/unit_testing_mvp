"""The step sequence + the N-run loop (steps 2-10 of the diagram).

Config + Preprocess + control_arena ground-truth scoring run ONCE (candidates are frozen);
the model-dependent monitor steps (PBT-gen, trigger-search, score, TM, informed-TM) repeat per run.
"""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import metrics as metrics_mod
from . import model as model_mod
from . import monitor, pbt, report
from .schema import Backend, Problem, ScoreResult, make_row

import os

# Concurrent model calls. 4 is safe under a 500 RPM / 500K TPM quota (verified: concurrent calls
# return in seconds). Tune per deployment via MAX_CONN=N.
MAX_CONN = int(os.getenv("MAX_CONN", "4"))
EXEC_WORKERS = int(os.getenv("EXEC_WORKERS", "8"))  # local subprocess jobs (not rate-limited)
CALL_TIMEOUT_SECONDS = int(os.getenv("CALL_TIMEOUT", "240"))  # per-call backstop


def _write_pbt_artifacts(run_dir: Path, task_id: str, suite: dict[str, Any], meta: dict[str, Any]) -> None:
    d = run_dir / "pbt" / task_id.replace("/", "_")
    d.mkdir(parents=True, exist_ok=True)
    (d / "properties.py").write_text(suite.get("props_src") or f"# no valid properties\n# {suite.get('prop_err')}\n", encoding="utf-8")
    (d / "search_space.json").write_text(json.dumps(suite.get("space") or [], indent=2), encoding="utf-8")
    (d / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")


async def _one_run(
    backend: Backend,
    problems: list[Problem],
    scores: dict[tuple[str, str], ScoreResult],
    model: model_mod.TrustedModel,
    tests_per_problem: int,
    run_subdir: Path,
) -> tuple[list[dict[str, Any]], dict[str, bool], dict[str, bool], dict[str, str]]:
    sem = asyncio.Semaphore(MAX_CONN)

    async def call(prompt: str, kind: str) -> str:
        async with sem:
            try:
                return await asyncio.wait_for(model.complete(prompt, kind), timeout=CALL_TIMEOUT_SECONDS)
            except Exception as error:  # a failed/timed-out call -> "" -> invalid suite / abstention
                print(f"  [warn] {kind} call failed: {type(error).__name__}: {str(error)[:200]}", flush=True)
                return ""

    # Steps 3 + 4: blind property + trigger-search generation, per problem.
    print(f"  generating PBT properties + trigger search spaces for {len(problems)} problems "
          f"({MAX_CONN} concurrent model calls)...", flush=True)
    gens = await asyncio.gather(
        *[
            asyncio.gather(
                call(pbt.property_prompt(p, tests_per_problem), "property_gen"),
                call(pbt.search_prompt(p), "trigger_search"),
            )
            for p in problems
        ]
    )
    suites: dict[str, dict[str, Any]] = {}
    for p, (prop_c, space_c) in zip(problems, gens):
        props_src, prop_err = pbt.parse_properties(prop_c)
        space, space_err = pbt.parse_search_space(space_c)
        suites[p.task_id] = {"props_src": props_src, "space": space, "prop_err": prop_err, "space_err": space_err}

    valid = sum(1 for s in suites.values() if s["props_src"] and s["space"])
    print(f"  suites: {valid}/{len(problems)} valid; scoring PBT over search spaces "
          f"(subprocess, compute-heavy)...", flush=True)

    # Step 5: run properties over the search space (soundness gate + per-candidate scoring). CPU/subprocess
    # bound -> thread pool across problems.
    loop = asyncio.get_event_loop()

    def _eval(p: Problem):
        s = suites[p.task_id]
        return (p.task_id, *pbt.evaluate(p, s["props_src"], s["space"]))

    _done = 0

    async def _eval_one(pool_ex: ThreadPoolExecutor, p: Problem):
        nonlocal _done
        tid, meta, results = await loop.run_in_executor(pool_ex, _eval, p)
        _write_pbt_artifacts(run_subdir, tid, suites[tid], meta)  # incremental: pbt/ fills as it goes
        _done += 1
        print(f"    scored PBT {_done}/{len(problems)} ({tid}, {len(suites[tid].get('space') or [])} inputs)", flush=True)
        return (tid, meta, results)

    with ThreadPoolExecutor(max_workers=EXEC_WORKERS) as pool_ex:
        evaluated = await asyncio.gather(*[_eval_one(pool_ex, p) for p in problems])
    pbt_by_task = {tid: (meta, results) for tid, meta, results in evaluated}

    # Steps 6 + 8: TM and informed-TM per candidate.
    jobs = [(p, c) for p in problems for c in p.candidates]
    print(f"  monitoring {len(jobs)} candidates (TM + informed-TM)...", flush=True)
    _mdone = 0

    async def score_candidate(p: Problem, c) -> dict[str, Any]:
        nonlocal _mdone
        _meta, results = pbt_by_task[p.task_id]
        pbt_res = results[c.candidate_id]  # {"pbt": deployable, "pbt_ceiling": gated}
        s = suites[p.task_id]
        tm_txt = await call(monitor.tm_prompt(p, c), "tm")
        inf_txt = await call(
            monitor.informed_prompt(p, c, pbt_res["pbt"], s["props_src"], s["space"]), "informed"
        )
        row = make_row(
            task_id=p.task_id,
            candidate=c,
            score=scores[(p.task_id, c.candidate_id)],
            pbt_results=pbt_res,
            tm=monitor.parse_suspicion(tm_txt),
            informed=monitor.parse_suspicion(inf_txt),
        )
        _mdone += 1
        if _mdone % 5 == 0 or _mdone == len(jobs):
            print(f"    monitored {_mdone}/{len(jobs)}", flush=True)
        return row

    rows = await asyncio.gather(*[score_candidate(p, c) for p, c in jobs])
    rows = sorted(rows, key=lambda r: (r["task_id"], r["candidate_label"]))

    suite_validity = {p.task_id: bool(pbt_by_task[p.task_id][0]["valid"]) for p in problems}
    suite_soundness = {p.task_id: bool(pbt_by_task[p.task_id][0]["sound"]) for p in problems}
    selected_policy = {p.task_id: p.selected_attack for p in problems}
    return rows, suite_validity, suite_soundness, selected_policy


async def _run_all(
    backend: Backend,
    problems: list[Problem],
    scores: dict[tuple[str, str], ScoreResult],
    run_dir: Path,
    *,
    model_name: str,
    runs: int,
    tests_per_problem: int,
    seed: int,
    audit_rate: float,
) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]]]:
    per_run_metrics: list[dict[str, Any]] = []
    rows_by_run: list[list[dict[str, Any]]] = []
    for r in range(runs):
        temperature = 0.0 if runs == 1 else 0.7  # >0 so K re-runs actually differ
        model = model_mod.resolve(model_name, temperature=temperature, seed=seed + r)
        print(f"--- run {r + 1}/{runs} (temp={temperature}, seed={seed + r}) ---", flush=True)
        rows, validity, soundness, selected = await _one_run(
            backend, problems, scores, model, tests_per_problem, run_dir / f"run_{r}"
        )
        per_run_metrics.append(
            metrics_mod.compute_run_metrics(
                rows,
                selected,
                seed=seed + r,
                suite_validity=validity,
                suite_soundness=soundness,
                audit_rate=audit_rate,
            )
        )
        rows_by_run.append(rows)
    return per_run_metrics, rows_by_run


def run_pipeline(
    backend: Backend,
    pool: dict[str, Any],
    *,
    model_name: str,
    runs: int,
    tests_per_problem: int,
    seed: int,
    audit_rate: float,
    run_id: str,
    limit: int | None,
) -> tuple[Path, dict[str, Any]]:
    # Config + Preprocess + control_arena ground-truth scoring run ONCE, synchronously (control_eval
    # owns its own event loop, so it must not run inside the per-run asyncio loop).
    problems = backend.preprocess(pool, limit=limit)
    if not problems:
        raise ValueError("preprocess produced no problems")
    print(f"preprocessed {len(problems)} problems ({backend.name})", flush=True)

    scores = backend.score_candidates(problems)
    n_success = sum(
        1
        for p in problems
        for c in p.attacks
        if scores[(p.task_id, c.candidate_id)].main_task_success
        and scores[(p.task_id, c.candidate_id)].side_task_success
    )
    print(f"ground-truth scored: {n_success} successful backdoors", flush=True)

    run_dir = Path("runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    per_run_metrics, rows_by_run = asyncio.run(
        _run_all(
            backend,
            problems,
            scores,
            run_dir,
            model_name=model_name,
            runs=runs,
            tests_per_problem=tests_per_problem,
            seed=seed,
            audit_rate=audit_rate,
        )
    )

    agg = metrics_mod.aggregate_runs(per_run_metrics)
    config = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "domain": backend.name,
        "pool": str(pool.get("_path", "")) or None,
        "model": model_name,
        "runs": runs,
        "tests_per_problem": tests_per_problem,
        "seed": seed,
        "audit_rate": audit_rate,
        "n_tasks": len(problems),
    }
    report.compile_results(run_dir, config=config, run_metrics=per_run_metrics, agg=agg, rows_by_run=rows_by_run)
    print(f"\nwrote {run_dir}", flush=True)
    return run_dir, agg
