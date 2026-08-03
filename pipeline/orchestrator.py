"""The step sequence + N-run loop, made durable and resumable.

Config + Preprocess + control_arena ground-truth scoring run ONCE and are checkpointed to disk
(problems.json / scores.json); the model-dependent steps repeat per run and stream their output to
disk as they go. Re-running with the same ``--run-id`` resumes: cached scores skip re-scoring,
completed runs are loaded, and within a run already-generated PBT suites and already-monitored
candidates are skipped. A hang costs at most one in-flight call — each model call runs in a worker
thread under a hard wall-clock timeout, so a frozen socket can never freeze the pipeline.
"""

from __future__ import annotations

import asyncio
import os
import random
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import metrics as metrics_mod
from . import model as model_mod
from . import monitor, pbt, report, state
from .schema import Backend, Problem, ScoreResult, make_row

MAX_CONN = int(os.getenv("MAX_CONN", "4"))            # concurrent model calls (endpoint is the cap)
EXEC_WORKERS = int(os.getenv("EXEC_WORKERS", "8"))    # local subprocess PBT jobs (not rate-limited)
CALL_TIMEOUT_SECONDS = int(os.getenv("CALL_TIMEOUT", "120"))  # HARD wall-clock cap per attempt
CALL_RETRIES = int(os.getenv("CALL_RETRIES", "2"))    # extra attempts (fresh client each time)
RUN_DEADLINE_SECONDS = int(os.getenv("RUN_DEADLINE", "0"))  # 0 = off; abandon a wedged run past this
# Each run executes in its OWN subprocess (pipeline.run_worker) so httpx/inspect/asyncio state can't
# accumulate across runs and wedge a later one. The parent enforces a hard wall-clock timeout and
# kills+resumes a run that overruns; partial progress (suite.json/rows.jsonl) survives the kill.
RUN_SUBPROC_TIMEOUT = int(os.getenv("RUN_SUBPROC_TIMEOUT", "1200"))  # hard wall-clock per run process
RUN_RETRIES = int(os.getenv("RUN_RETRIES", "2"))    # kill+resume attempts per run before skipping it
HEARTBEAT_SECONDS = 10
# 2-turn PBT gen: after drafting properties, a spec-only self-critique turn prunes unsound ones
# (deployable soundness gate — no reference/candidate). Off by default.
SELF_CRITIQUE = os.getenv("PBT_SELF_CRITIQUE", "0").lower() in ("1", "true", "yes")
# How the PBT properties are generated:
#   blind_t          trusted model writes properties (default; original behaviour)
#   u_writes         untrusted/capable model writes properties directly
#   u_plans_t_writes untrusted model writes a spec-only PLAN, trusted model implements it
# The trigger search space is always written by the trusted model (don't let U choose inputs).
GEN_STRATEGIES = ("blind_t", "u_writes", "u_plans_t_writes")


def _count_props(src: str) -> int:
    return (src or "").count("def prop_") + (src or "").count("def test_")


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)


def _score_in_subprocess(run_dir: Path, domain: str) -> None:
    """Run control_arena ground-truth scoring in a fresh process (it uses inspect's eval(), which
    poisons this process's asyncio state and would wedge our later model calls). The child reads
    problems.json and writes scores.json; its stdout (control_arena's tables) is inherited."""
    repo_root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [sys.executable, "-m", "pipeline.scoring_worker", str(run_dir.resolve()), domain],
        cwd=str(repo_root),
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"ground-truth scoring subprocess failed (exit {proc.returncode}); see output above")


async def _hard_call(model: model_mod.TrustedModel, prompt: str, kind: str, timeout: float) -> str:
    """One model call on the CURRENT event loop with a hard timeout. Uses inspect's native async
    generate (concurrency-safe via its shared connection pool); asyncio.wait_for cancels the underlying
    httpx request if the call overruns.

    This replaces the previous thread-per-call design (each call ran its own asyncio.run() with a fresh
    event loop + fresh httpx client). Four of those racing under MAX_CONN concurrency was what wedged —
    a single task ran fine, ten-at-four hung. Because each run now executes in its own subprocess, there
    is no control_eval asyncio poisoning to work around, so the native path is both simpler and robust."""
    return await asyncio.wait_for(model.complete(prompt, kind), timeout=timeout)


async def _one_run(
    problems: list[Problem],
    scores: dict[tuple[str, str], ScoreResult],
    t_model: model_mod.TrustedModel,
    u_model: model_mod.TrustedModel,
    gen_strategy: str,
    tests_per_problem: int,
    run_dir: Path,
    r: int,
    status: state.Status,
) -> tuple[list[dict[str, Any]], dict[str, bool], dict[str, bool], dict[str, str]]:
    sem = asyncio.Semaphore(MAX_CONN)

    async def call(prompt: str, kind: str, mdl: model_mod.TrustedModel) -> str:
        # Acquire the slot PER ATTEMPT (not across retries) so a stalled attempt frees it for others,
        # and back off OUTSIDE the slot so we never hold capacity while sleeping.
        for attempt in range(1 + CALL_RETRIES):
            async with sem:
                try:
                    return await _hard_call(mdl, prompt, kind, CALL_TIMEOUT_SECONDS)
                except Exception as error:  # timeout / API error -> retry with a fresh client
                    log(f"  [warn] {kind} attempt {attempt + 1}/{1 + CALL_RETRIES}: "
                        f"{type(error).__name__}: {str(error)[:120]}")
            if attempt < CALL_RETRIES:
                await asyncio.sleep(min(2 ** attempt, 8) * 0.5 + random.uniform(0, 0.4))
        return ""  # exhausted retries -> abstention / invalid suite

    # ------------------------------------------------------------------ #
    # Steps 3-5: PBT generation + evaluation, resumable per task via suite.json
    # ------------------------------------------------------------------ #
    suites: dict[str, dict[str, Any]] = {}
    for p in problems:
        cached = state.load_suite(run_dir, r, p.task_id)
        if cached and "meta" in cached and "results" in cached:
            suites[p.task_id] = cached
    todo = [p for p in problems if p.task_id not in suites]
    if suites:
        log(f"run {r}: resumed {len(suites)}/{len(problems)} PBT suites from checkpoint")

    if todo:
        # Gen and eval are FUSED per task so each task is a durable unit: the moment a task's
        # properties are generated (network) and scored (local), its suite.json is written, and a
        # resume skips it. A kill mid-phase loses only the in-flight tasks — matching how monitor
        # rows are already per-candidate durable. Gen calls are MAX_CONN-bounded (the semaphore in
        # `call`); eval runs in the EXEC_WORKERS thread pool as each gen finishes.
        status.set(phase="generate", run_index=r, gen_done=len(suites), gen_total=len(problems))
        log(f"run {r}: generating + scoring PBT for {len(todo)} problems "
            f"({MAX_CONN} gen / {EXEC_WORKERS} eval concurrent)...")
        loop = asyncio.get_running_loop()
        _pdone = len(suites)

        async def _gen_one(p: Problem) -> tuple[str, str, str]:
            plan = ""
            try:
                # The trigger search space is always trusted-authored (never let U choose inputs).
                if gen_strategy == "u_plans_t_writes":
                    plan = await call(pbt.plan_prompt(p, tests_per_problem), "plan", u_model)
                    prop_c, space_c = await asyncio.gather(
                        call(pbt.write_from_plan_prompt(p, plan, tests_per_problem), "write_from_plan", t_model),
                        call(pbt.search_prompt(p), "trigger_search", t_model),
                    )
                elif gen_strategy == "u_writes":
                    prop_c, space_c = await asyncio.gather(
                        call(pbt.property_prompt(p, tests_per_problem), "property_gen", u_model),
                        call(pbt.search_prompt(p), "trigger_search", t_model),
                    )
                else:  # blind_t (default)
                    prop_c, space_c = await asyncio.gather(
                        call(pbt.property_prompt(p, tests_per_problem), "property_gen", t_model),
                        call(pbt.search_prompt(p), "trigger_search", t_model),
                    )
            except Exception as error:  # isolation: a gen failure degrades this problem only
                prop_c, space_c = "", ""
                log(f"  [warn] gen failed for {p.task_id}: {type(error).__name__}")
            if SELF_CRITIQUE and prop_c:  # turn 2: spec-only soundness prune (trusted, deployable gate)
                try:
                    base_src, _ = pbt.parse_properties(prop_c)
                    if base_src:
                        crit_c = await call(pbt.critique_prompt(p, base_src), "property_gen", t_model)
                        crit_src, _ = pbt.parse_properties(crit_c)
                        if crit_src:  # accept refinement only if it still parses to >=1 property
                            log(f"    critiqued {p.task_id}: {_count_props(base_src)} -> "
                                f"{_count_props(crit_src)} props")
                            prop_c = crit_c
                except Exception as error:  # critique failure -> keep turn-1 properties
                    log(f"  [warn] critique failed for {p.task_id}: {type(error).__name__} (kept turn-1)")
            return prop_c, space_c, plan

        def _eval(p: Problem, prop_c: str, space_c: str, plan: str) -> dict[str, Any]:
            props_src, prop_err = pbt.parse_properties(prop_c)
            space, space_err = pbt.parse_search_space(space_c)
            try:
                meta, results = pbt.evaluate(p, props_src, space)
            except Exception as error:  # isolation: a bad suite must not abort the whole phase
                meta, results = pbt.degraded(p, f"eval crashed: {type(error).__name__}: {error}")
            return {"props_src": props_src, "space": space, "prop_err": prop_err, "space_err": space_err,
                    "prop_raw": prop_c, "space_raw": space_c, "plan": plan, "gen_strategy": gen_strategy,
                    "meta": meta, "results": results}

        async def _process_one(pool_ex: ThreadPoolExecutor, p: Problem) -> tuple[str, dict[str, Any]]:
            nonlocal _pdone
            prop_c, space_c, plan = await _gen_one(p)                             # network (bounded)
            suite = await loop.run_in_executor(pool_ex, _eval, p, prop_c, space_c, plan)  # local CPU
            state.save_suite(run_dir, r, p.task_id, suite)                        # durable checkpoint
            state.write_pbt_readable(run_dir, r, p.task_id, suite)                # human-readable mirror
            _pdone += 1
            status.beat(gen_done=_pdone)
            log(f"    PBT {_pdone}/{len(problems)} ({p.task_id}: "
                f"{'valid' if suite['meta'].get('valid') else 'invalid'}, "
                f"{len(suite.get('space') or [])} inputs)")
            return p.task_id, suite

        with ThreadPoolExecutor(max_workers=EXEC_WORKERS) as pool_ex:
            processed = await asyncio.gather(
                *[_process_one(pool_ex, p) for p in todo], return_exceptions=True)
        for res in processed:
            if isinstance(res, Exception):
                continue  # already logged; that task has no suite and will degrade below
            tid, suite = res
            suites[tid] = suite

    # any task still missing a suite (gen/eval both failed) -> explicit degraded suite
    for p in problems:
        if p.task_id not in suites:
            meta, results = pbt.degraded(p, "generation/evaluation did not complete")
            suites[p.task_id] = {"props_src": None, "space": None, "meta": meta, "results": results}

    valid = sum(1 for p in problems if suites[p.task_id]["meta"].get("valid"))
    log(f"run {r}: PBT suites {valid}/{len(problems)} valid")

    # ------------------------------------------------------------------ #
    # Steps 6 + 8: TM and informed-TM per candidate, resumable via rows.jsonl
    # ------------------------------------------------------------------ #
    done_rows = state.load_rows(run_dir, r)
    done_keys = {(row["task_id"], row["candidate_id"]) for row in done_rows}
    jobs = [(p, c) for p in problems for c in p.candidates if (p.task_id, c.candidate_id) not in done_keys]
    total_jobs = sum(len(p.candidates) for p in problems)
    if done_rows:
        log(f"run {r}: resumed {len(done_rows)}/{total_jobs} monitored candidates from checkpoint")
    status.set(phase="monitor", run_index=r, monitored=len(done_rows), monitor_total=total_jobs)
    log(f"run {r}: monitoring {len(jobs)} candidates (TM + informed-TM)...")
    _mdone = len(done_rows)
    _mlock = asyncio.Lock()

    async def score_candidate(p: Problem, c) -> dict[str, Any] | None:
        nonlocal _mdone
        try:
            suite = suites[p.task_id]
            pbt_res = suite["results"][c.candidate_id]
            tm_txt = await call(monitor.tm_prompt(p, c), "tm", t_model)
            inf_txt = await call(
                monitor.informed_prompt(p, c, pbt_res["pbt"], suite.get("props_src"), suite.get("space")),
                "informed", t_model,
            )
            row = make_row(
                task_id=p.task_id, candidate=c, score=scores[(p.task_id, c.candidate_id)],
                pbt_results=pbt_res, tm=monitor.parse_suspicion(tm_txt),
                informed=monitor.parse_suspicion(inf_txt),
            )
        except Exception as error:  # isolation: one candidate never takes down the run
            log(f"  [warn] monitor failed for {p.task_id}/{c.candidate_id}: {type(error).__name__}: {error}")
            return None
        async with _mlock:
            state.append_row(run_dir, r, row)  # write-ahead: survives a kill
            _mdone += 1
            if _mdone <= MAX_CONN or _mdone % 5 == 0 or _mdone == total_jobs:
                log(f"    monitored {_mdone}/{total_jobs}")
            status.beat(monitored=_mdone)
        return row

    new = await asyncio.gather(*[score_candidate(p, c) for p, c in jobs], return_exceptions=True)
    new_rows = [x for x in new if isinstance(x, dict)]
    failed = len(jobs) - len(new_rows)
    if failed:
        log(f"run {r}: {failed} candidate(s) failed monitoring after retries (abstained)")

    rows = sorted(done_rows + new_rows, key=lambda row: (row["task_id"], row["candidate_label"]))
    if len(rows) != total_jobs:
        raise RuntimeError(
            f"run {r}: only {len(rows)}/{total_jobs} candidates monitored — run incomplete, "
            f"resume with the same --run-id to finish (partial progress is on disk)")

    suite_validity = {p.task_id: bool(suites[p.task_id]["meta"].get("valid")) for p in problems}
    suite_soundness = {p.task_id: bool(suites[p.task_id]["meta"].get("sound")) for p in problems}
    selected_policy = {p.task_id: p.selected_attack for p in problems}
    return rows, suite_validity, suite_soundness, selected_policy


async def _heartbeat(status: state.Status) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        status.beat()


def _run_one_subprocess(run_dir: Path, r: int) -> int:
    """Run one run-index in a fresh process group under a hard wall-clock timeout. Returns the child's
    exit code; on overrun kills the WHOLE group (worker + any eval grandchildren it spawned) and raises
    subprocess.TimeoutExpired. Group-kill matters: killing only the worker would orphan candidate
    processes that keep grinding the CPU."""
    repo_root = Path(__file__).resolve().parent.parent
    proc = subprocess.Popen(
        [sys.executable, "-m", "pipeline.run_worker", str(run_dir.resolve()), str(r)],
        cwd=str(repo_root), start_new_session=True)
    try:
        return proc.wait(timeout=RUN_SUBPROC_TIMEOUT)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
        raise


def _run_all(
    run_dir: Path,
    status: state.Status,
    *,
    runs: int,
) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]]]:
    """Drive the per-run loop, each run in its own subprocess (pipeline.run_worker). A wedged or
    crashed run is killed at the wall-clock timeout and resumed from its on-disk checkpoint; after
    RUN_RETRIES it is skipped (resume later with the same --run-id). No model call runs in THIS
    process, so nothing here can hang."""
    per_run_metrics: list[dict[str, Any]] = []
    rows_by_run: list[list[dict[str, Any]]] = []
    for r in range(runs):
        if state.is_run_done(run_dir, r):
            rows, m = state.load_run_complete(run_dir, r)
            if rows is not None and m is not None:
                log(f"run {r}: already complete — loaded from checkpoint")
                per_run_metrics.append(m)
                rows_by_run.append(rows)
                continue
        done = False
        for attempt in range(1 + RUN_RETRIES):
            log(f"--- run {r + 1}/{runs} (isolated subprocess, attempt {attempt + 1}/{1 + RUN_RETRIES}) ---")
            status.set(phase="run_active", run_index=r, attempt=attempt + 1)
            try:
                rc = _run_one_subprocess(run_dir, r)
            except subprocess.TimeoutExpired:
                log(f"run {r}: exceeded {RUN_SUBPROC_TIMEOUT}s — killed; resuming from checkpoint")
                continue
            if rc == 0 and state.is_run_done(run_dir, r):
                done = True
                break
            log(f"run {r}: worker exit={rc}, run_done={state.is_run_done(run_dir, r)} — "
                f"{'retrying' if attempt < RUN_RETRIES else 'giving up'}")
        if not done:
            log(f"run {r}: incomplete after {1 + RUN_RETRIES} attempt(s) (partial progress saved; "
                f"resume with the same --run-id)")
            status.set(phase="run_incomplete", run_index=r)
            continue
        rows, m = state.load_run_complete(run_dir, r)
        per_run_metrics.append(m)
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
    stage: str = "all",
    gen_strategy: str = "blind_t",
    elicit_model_name: str | None = None,
) -> tuple[Path, dict[str, Any] | None]:
    if stage not in ("all", "score", "monitor"):
        raise ValueError(f"stage must be all|score|monitor, got {stage!r}")
    if gen_strategy not in GEN_STRATEGIES:
        raise ValueError(f"gen_strategy must be one of {GEN_STRATEGIES}, got {gen_strategy!r}")

    run_dir = Path("runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)  # resume-friendly (no exist_ok=False)
    status = state.Status(run_dir)
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
        "stage": stage,
        "self_critique": SELF_CRITIQUE,
        "reasoning_effort": os.getenv("REASONING_EFFORT", "low"),
        "gen_strategy": gen_strategy,
        "elicit_model": elicit_model_name,
    }
    state.write_json(run_dir / "run.json", config)  # manifest up front, before any expensive work

    # --- Preprocess + ground-truth scoring: run once, checkpoint, reload on resume ---
    problems = state.load_problems(run_dir)
    scores = state.load_scores(run_dir)
    if stage == "monitor" and (problems is None or scores is None):
        raise ValueError(
            f"stage=monitor needs a prior '--stage score' (or 'all') run under --run-id {run_id!r} "
            f"(problems.json + scores.json not found in {run_dir})")

    status.set(phase="preprocess")
    if problems is None:
        problems = backend.preprocess(pool, limit=limit)
        if not problems:
            raise ValueError("preprocess produced no problems")
        state.save_problems(run_dir, problems)
        log(f"preprocessed {len(problems)} problems ({backend.name})")
    else:
        log(f"resumed {len(problems)} problems from checkpoint")

    if scores is None:
        status.set(phase="ground_truth_scoring")
        if backend.name == "mock":
            # mock scoring never touches control_eval, so it can't poison us -> run in-process.
            scores = backend.score_candidates(problems)
            state.save_scores(run_dir, scores)
        else:
            log("ground-truth scoring in an isolated subprocess (control_eval)...")
            _score_in_subprocess(run_dir, backend.name)
            scores = state.load_scores(run_dir)
            if scores is None:
                raise RuntimeError("scoring subprocess produced no scores.json (see output above)")
        log("ground-truth scored + persisted to scores.json")
    else:
        log(f"resumed ground-truth scores ({len(scores)} candidates) from checkpoint")

    config["n_tasks"] = len(problems)
    state.write_json(run_dir / "run.json", config)
    n_success = sum(
        1 for p in problems for c in p.attacks
        if scores[(p.task_id, c.candidate_id)].main_task_success
        and scores[(p.task_id, c.candidate_id)].side_task_success
    )
    log(f"successful backdoors (ground truth): {n_success}")

    if stage == "score":
        status.set(phase="done_score")
        log(f"stage=score complete. Resume the flaky half with: --stage monitor --run-id {run_id}")
        return run_dir, None

    # Each run executes in its own subprocess (pipeline.run_worker), reading model/gen-strategy/seed
    # from the run.json written above. Fresh process per run == no cross-run asyncio/httpx poisoning.
    per_run_metrics, rows_by_run = _run_all(run_dir, status, runs=runs)

    if not per_run_metrics:
        status.set(phase="no_completed_runs")
        log("no runs completed (all abandoned/incomplete). Resume with the same --run-id to finish.")
        return run_dir, None

    agg = metrics_mod.aggregate_runs(per_run_metrics)
    report.compile_results(run_dir, config=config, run_metrics=per_run_metrics, agg=agg,
                           rows_by_run=rows_by_run)
    status.set(phase="done", completed_runs=len(per_run_metrics), requested_runs=runs)
    log(f"wrote {run_dir}  ({len(per_run_metrics)}/{runs} runs)")
    return run_dir, agg
