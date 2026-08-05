"""The declarative pipeline engine — the only orchestration layer.

`run(config, backend, pool, pipeline, metrics)` is the single entrypoint. The whole pipeline is one
ordered list of `Step` objects; the engine drives it off their declared fields — nothing about a
particular step is hardcoded here:
  - `Step.scope`  splits the list into ONCE steps (preprocess, score) and PER_RUN steps.
  - `Step.needs`  is validated at startup (every need is produced by an earlier step) and enforced at
    run time (the run-global inputs must exist before a step runs).
  - `Step.fanout` selects a `FanoutSpec` from `FANOUTS` that knows how to enumerate the step's units,
    detect already-done units (resume), persist a unit's result, and degrade a failed unit.
  - `Step.produces` is the artifact each step writes; its presence is the resume/skip marker.
Adding or reordering a step is a list edit; the engine does not change.

Each run executes inside an isolation boundary (in-process / subprocess / Docker per `config.exec_mode`).

Failure handling is centralized — there is no ad-hoc try/except in the step or metric code. The sites:
  1. `with_retry`            — model-call timeout + retry (the only place a model call is guarded).
  2. `_guard`                — per fan-out unit; turns an exception into a degraded artifact / abstention.
  3. `run_isolated`          — subprocess/Docker wall-clock timeout + whole-process-tree kill.
  4. `_execute_run_isolated` — the run-retry boundary: catches a run's timeout (to kill+resume) or crash
     (to log a full traceback + retry) so one bad run never aborts the whole loop. Distinct from 1-3 by
     design; every other function stays straight-line.

Public surface (top): the step-graph types + `Step`/`FanoutSpec`, `RetryPolicy`, `SetupContext`/
`RunContext`, `with_retry`, `run_isolated`, `run`, `execute_run`, `execute_once`. Helpers are below.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from . import metrics as metrics_mod
from . import model as model_mod
from . import pbt, report
from . import artifacts
from .artifacts import ArtifactKind, ArtifactStore
from .config import Config, ExecMode, Stage
from .schema import Backend, Problem

if TYPE_CHECKING:
    from .metrics_objs import Metric

HEARTBEAT_SECONDS = 10
SCORE_STAGE_MIN_SECONDS = 1800
ABSTAIN = object()


class Scope(str, Enum):
    """When a step runs: ONCE per pipeline, or PER_RUN (repeated `config.runs` times)."""

    ONCE = "once"
    PER_RUN = "per_run"


class Fanout(str, Enum):
    """A step's map granularity: one call, one per task, or one per candidate."""

    NONE = "none"
    PER_TASK = "per_task"
    PER_CANDIDATE = "per_candidate"


@dataclass(frozen=True)
class Step:
    """A declarative pipeline step: what it produces/needs, when + how it runs, and the fn that does it.

    A PER_RUN fn is async `(ctx: RunContext, unit) -> artifact_value` (unit is a `Problem` for PER_TASK,
    a `(Problem, Candidate)` pair for PER_CANDIDATE, or None for NONE). A ONCE fn is sync
    `(ctx: SetupContext) -> artifact_value`. `isolated=True` (ONCE only) runs the step in its own
    subprocess — used for ground-truth scoring, which must never share a process with async model calls.
    """

    name: str
    produces: ArtifactKind
    needs: tuple[ArtifactKind, ...]
    scope: Scope
    fanout: Fanout
    fn: Callable[..., Any]
    isolated: bool = False


@dataclass(frozen=True)
class FanoutSpec:
    """How one `Fanout` granularity enumerates units, resumes, persists, and degrades a failed unit.

    This table (see `FANOUTS`) is what makes `_run_step` a single generic code path instead of a
    per-granularity if/elif: the engine only ever calls these callables.

        units       every unit this step must process
        done_keys   keys of units already persisted, for resume
        key         unit -> its resume key
        label       unit -> a short id for logs
        persist     (ctx, step, unit, value) -> write it
        on_fail     (ctx, step, unit, error) -> replacement value, or ABSTAIN to record nothing
    """

    units: Callable[["RunContext", Step], list[Any]]
    done_keys: Callable[["RunContext", Step], set]
    key: Callable[[Any], Any]
    label: Callable[[Any], str]
    persist: Callable[["RunContext", Step, Any, Any], None]
    on_fail: Callable[["RunContext", Step, Any, Exception], Any]


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded retry+timeout policy for a model call (used only by `with_retry`)."""

    attempts: int
    timeout_s: float
    backoff_base_s: float = 0.5

    @classmethod
    def from_config(cls, config: Config) -> "RetryPolicy":
        """Derive the policy from a Config (1 + call_retries attempts, call_timeout hard cap)."""
        return cls(attempts=1 + config.call_retries, timeout_s=float(config.timeouts.outer_call))


@dataclass
class SetupContext:
    """Everything a ONCE step fn needs (preprocess/score run in the parent, before any per-run loop)."""

    config: Config
    store: ArtifactStore
    backend: Backend
    pool: dict[str, Any]


@dataclass
class RunContext:
    """Everything a PER_RUN step fn needs, assembled once per run by `execute_run`.

    Step fns read what they need off this object (config, models, the artifact store, the shared
    semaphore/thread-pool, a per-run suite cache) instead of the engine threading a bespoke inputs dict
    — keeping fn signatures uniform as `(ctx, unit)`.
    """

    config: Config
    store: ArtifactStore
    r: int
    problems: list[Problem]
    scores: dict[tuple[str, str], Any]
    t_model: model_mod.TrustedModel
    u_model: model_mod.TrustedModel
    retry: RetryPolicy
    sem: asyncio.Semaphore
    pool: ThreadPoolExecutor
    suites: dict[str, Any] = field(default_factory=dict)


async def with_retry(
    make_coro: Callable[[], Awaitable[str]], policy: RetryPolicy, *, sem: asyncio.Semaphore, label: str,
) -> str | None:
    """Run a model call under a hard per-attempt timeout, retrying with backoff; the ONLY call guard.

    Acquires `sem` per attempt (so a stalled attempt frees its slot for others) and backs off OUTSIDE
    the slot. Returns the completion string, or None once attempts are exhausted (callers read None as an
    abstention). This is the single place model-call timeout+retry logic exists.
    """
    for attempt in range(policy.attempts):
        async with sem:
            try:
                return await asyncio.wait_for(make_coro(), timeout=policy.timeout_s)
            except Exception as error:
                log(f"  [warn] {label} attempt {attempt + 1}/{policy.attempts}: "
                    f"{type(error).__name__}: {str(error)[:120]}")
        if attempt < policy.attempts - 1:
            await asyncio.sleep(min(2 ** attempt, 8) * policy.backoff_base_s)
    return None


def run_isolated(cmd: list[str], *, timeout_s: int, exec_mode: ExecMode, docker_image: str | None,
                 run_dir: Path, log_path: Path | None = None) -> int:
    """Run a worker command under a wall-clock timeout; the ONLY subprocess/Docker guard.

    Returns the child exit code. On overrun it kills the whole PROCESS TREE — not just the child's group
    — because the pbt harness starts its own session, so a group-kill alone would orphan it and its
    candidate subprocess (which then grind the CPU uncapped). For ExecMode.DOCKER the command is wrapped
    in `docker run --name <unique>` and a timeout `docker kill`s that container (SIGKILLing the host
    `docker run` CLI would leave the container running). When `log_path` is set (progress mode) the
    child's stdout/stderr are appended there instead of inherited, keeping the terminal free.
    """
    container = _container_name(run_dir) if exec_mode is ExecMode.DOCKER else None
    full = _docker_wrap(cmd, docker_image, run_dir, container) if container else cmd
    out = open(log_path, "a", encoding="utf-8") if log_path is not None else None
    try:
        proc = subprocess.Popen(full, cwd=str(_repo_root()), start_new_session=True,
                                stdout=out, stderr=(subprocess.STDOUT if out is not None else None))
        try:
            return proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            if container is not None:
                _docker_kill(container)
            _kill_tree(proc.pid)
            raise
    finally:
        if out is not None:
            out.close()


def run(config: Config, backend: Backend, pool: dict[str, Any], pipeline: list[Step],
        metrics: list["Metric"]) -> tuple[Path, dict[str, Any] | None]:
    """Execute the whole pipeline (parent process): ONCE setup, per-run loop, aggregate, report.

    Validates the step graph, runs the ONCE steps (checkpointed), then executes the per-run steps inside
    their isolation boundary (resumable, retried on timeout), and finally aggregates + writes the report.
    Returns (run_dir, aggregate-or-None). Never runs a model call itself, so the parent can't hang.
    """
    _validate_pipeline(pipeline)
    run_dir = Path("runs") / config.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    store = ArtifactStore(run_dir)
    status = store.status()
    _write_run_manifest(run_dir, config)

    global _LOG_FILE
    _LOG_FILE = run_dir / "pipeline.log" if config.progress else None
    try:
        outcome = _execute_with_optional_dashboard(config, backend, pool, store, status, pipeline, metrics)
        return _finalize(config, store, status, outcome)
    finally:
        _LOG_FILE = None


def execute_run(config: Config, r: int, pipeline: list[Step], metrics: list["Metric"],
                run_dir: Path) -> None:
    """Execute the PER_RUN steps for run `r`, then compute + persist its metrics (the run-done marker).

    Called inside the isolation boundary — directly by the engine for INPROCESS (parent's run_dir), or by
    `pipeline.worker` in a subprocess/Docker (argv run_dir). Loads problems + scores, runs each PER_RUN
    step fanned out per its granularity (resumable per unit), and writes RUN_METRICS last.
    """
    store = ArtifactStore(run_dir)
    problems = store.load(ArtifactKind.PROBLEMS)
    scores = store.load(ArtifactKind.SCORES)
    if problems is None or scores is None:
        raise SystemExit("execute_run: problems.json / scores.json missing (run the score stage first)")
    per_run_steps = [s for s in pipeline if s.scope is Scope.PER_RUN]
    asyncio.run(_execute_run_async(config, r, per_run_steps, metrics, store, problems, scores))


def execute_once(config: Config, run_dir: Path, step_name: str, pipeline: list[Step],
                 backend: Backend, pool: dict[str, Any]) -> None:
    """Execute a single ONCE step inside the isolation boundary (called by `pipeline.worker`).

    Used for the isolated ground-truth `score` step: control_eval must run in its own process, so the
    engine spawns a worker that calls this. Persists the step's produced artifact.
    """
    store = ArtifactStore(run_dir)
    step = next(s for s in pipeline if s.name == step_name and s.scope is Scope.ONCE)
    _require_inputs(store, step)
    value = step.fn(SetupContext(config, store, backend, pool))
    store.put(step.produces, value)
    log(f"worker: {step_name} produced {step.produces.value}")


def _degraded_suite(problem: Problem, step: Step, error: Exception) -> dict[str, Any]:
    """The degraded SUITE a PER_TASK failure records so one task's crash never sinks the run."""
    meta, results = pbt.degraded(problem, f"{step.name} crashed: {type(error).__name__}: {error}")
    return {"props_src": None, "space": None, "meta": meta, "results": results}


FANOUTS: dict[Fanout, FanoutSpec] = {
    Fanout.PER_TASK: FanoutSpec(
        units=lambda ctx, step: list(ctx.problems),
        done_keys=lambda ctx, step: {p.task_id for p in ctx.problems
                                     if ctx.store.has(step.produces, run=ctx.r, task_id=p.task_id)},
        key=lambda p: p.task_id,
        label=lambda p: p.task_id,
        persist=lambda ctx, step, p, v: ctx.store.put(step.produces, v, run=ctx.r, task_id=p.task_id),
        on_fail=lambda ctx, step, p, e: _degraded_suite(p, step, e),
    ),
    Fanout.PER_CANDIDATE: FanoutSpec(
        units=lambda ctx, step: [(p, c) for p in ctx.problems for c in p.candidates],
        done_keys=lambda ctx, step: {(row["task_id"], row["candidate_id"])
                                     for row in ctx.store.load(step.produces, run=ctx.r)},
        key=lambda u: (u[0].task_id, u[1].candidate_id),
        label=lambda u: f"{u[0].task_id}/{u[1].candidate_id}",
        persist=lambda ctx, step, u, v: ctx.store.append(step.produces, v, run=ctx.r),
        on_fail=lambda ctx, step, u, e: ABSTAIN,
    ),
    Fanout.NONE: FanoutSpec(
        units=lambda ctx, step: [None],
        done_keys=lambda ctx, step: {None} if ctx.store.has(step.produces, run=ctx.r) else set(),
        key=lambda u: None,
        label=lambda u: "-",
        persist=lambda ctx, step, u, v: ctx.store.put(step.produces, v, run=ctx.r),
        on_fail=lambda ctx, step, u, e: ABSTAIN,
    ),
}


_LOG_FILE: Path | None = None


def log(msg: str) -> None:
    """Emit a UTC-timestamped progress line — to the log file in progress mode, else to stdout."""
    line = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}"
    if _LOG_FILE is not None:
        with _LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    else:
        print(line, flush=True)


def _validate_pipeline(pipeline: list[Step]) -> None:
    """Startup check: every step's `needs` is produced by an EARLIER step (declarative ordering)."""
    produced: set[ArtifactKind] = set()
    for step in pipeline:
        missing = [n for n in step.needs if n not in produced]
        if missing:
            raise ValueError(f"step '{step.name}' needs {[m.value for m in missing]} "
                             f"but no earlier step produces them")
        produced.add(step.produces)


def _execute_with_optional_dashboard(config: Config, backend: Backend, pool: dict[str, Any],
                                     store: ArtifactStore, status: "Any", pipeline: list[Step],
                                     metrics: list["Metric"]) -> tuple[list[Problem], list | None, list]:
    """Run ONCE setup + the per-run loop, under the live dashboard when `config.progress` is set."""
    if not config.progress:
        return _execute(config, backend, pool, store, status, pipeline, metrics)
    from .progress import ProgressReporter

    label = f"{config.run_id} · {config.domain.value} · {config.trusted.name}"
    with ProgressReporter(store.run_dir, runs=config.runs, label=label):
        return _execute(config, backend, pool, store, status, pipeline, metrics)


def _execute(config: Config, backend: Backend, pool: dict[str, Any], store: ArtifactStore,
             status: "Any", pipeline: list[Step], metrics: list["Metric"]
             ) -> tuple[list[Problem], list | None, list]:
    """ONCE setup + per-run loop. Returns (problems, per_run_metrics, rows_by_run); per_run_metrics is
    None for a score-only stage (signals _finalize to stop before aggregation)."""
    once_steps = [s for s in pipeline if s.scope is Scope.ONCE]
    problems = _run_once_steps(config, backend, pool, store, status, once_steps)
    if config.stage is Stage.SCORE:
        status.set(phase="done_score")
        log(f"stage=score complete. Resume the model phase with --stage monitor --run-id {config.run_id}")
        return problems, None, []
    per_run_metrics, rows_by_run = _run_loop(config, pipeline, metrics, store, status)
    return problems, per_run_metrics, rows_by_run


def _run_once_steps(config: Config, backend: Backend, pool: dict[str, Any], store: ArtifactStore,
                    status: "Any", once_steps: list[Step]) -> list[Problem]:
    """Run each ONCE step (resume-skip if produced); `isolated` steps run in a subprocess for real
    backends (mock has no control_eval so it runs inline). Returns the problem list."""
    setup = SetupContext(config, store, backend, pool)
    for step in once_steps:
        if store.has(step.produces):
            log(f"resumed {step.name} from checkpoint")
            continue
        _require_inputs(store, step)
        status.set(phase=step.name)
        if step.isolated and backend.name != "mock":
            log(f"{step.name}: isolated subprocess (control_eval)...")
            _run_once_isolated(config, store.run_dir, step.name)
        else:
            store.put(step.produces, step.fn(setup))
        if not store.has(step.produces):
            raise RuntimeError(f"{step.name} produced no {step.produces.value} (see output above)")
    problems = store.load(ArtifactKind.PROBLEMS)
    scores = store.load(ArtifactKind.SCORES)
    if problems and scores:
        _record_backdoor_count(problems, scores)
    return problems or []


def _run_loop(config: Config, pipeline: list[Step], metrics: list["Metric"], store: ArtifactStore,
              status: "Any") -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]]]:
    """Loop over runs, executing each in its isolation boundary; skip completed, retry on timeout.

    Returns (per_run_metrics, rows_by_run) for the runs that completed.
    """
    per_run_metrics: list[dict[str, Any]] = []
    rows_by_run: list[list[dict[str, Any]]] = []
    for r in range(config.runs):
        if store.has(ArtifactKind.RUN_METRICS, run=r):
            rows, m = store.load(ArtifactKind.RUN_METRICS, run=r)
            if rows is not None and m is not None:
                log(f"run {r}: already complete — loaded from checkpoint")
                per_run_metrics.append(m)
                rows_by_run.append(rows)
                continue
        if _execute_run_isolated(config, r, pipeline, metrics, store, status):
            rows, m = store.load(ArtifactKind.RUN_METRICS, run=r)
            per_run_metrics.append(m)
            rows_by_run.append(rows)
    return per_run_metrics, rows_by_run


def _execute_run_isolated(config: Config, r: int, pipeline: list[Step], metrics: list["Metric"],
                          store: ArtifactStore, status: "Any") -> bool:
    """Run one run-index in its isolation boundary with kill+resume retries; True if it completed.

    The run-retry boundary (failure site #4): INPROCESS calls `execute_run` directly; SUBPROCESS/DOCKER
    spawn `pipeline.worker` via `run_isolated`. A timeout is killed and resumed; an in-process crash logs
    a full traceback and retries so one bad run never aborts the whole loop.
    """
    for attempt in range(1 + config.run_retries):
        log(f"--- run {r + 1}/{config.runs} ({config.exec_mode.value}, "
            f"attempt {attempt + 1}/{1 + config.run_retries}) ---")
        status.set(phase="run_active", run_index=r, attempt=attempt + 1)
        try:
            if config.exec_mode is ExecMode.INPROCESS:
                execute_run(config, r, pipeline, metrics, store.run_dir)
                rc = 0
            else:
                cmd = [sys.executable, "-m", "pipeline.worker", str(store.run_dir.resolve()), "run", str(r)]
                rc = run_isolated(cmd, timeout_s=config.timeouts.run, exec_mode=config.exec_mode,
                                  docker_image=config.docker_image, run_dir=store.run_dir,
                                  log_path=(store.run_dir / "pipeline.log") if config.progress else None)
        except subprocess.TimeoutExpired:
            log(f"run {r}: exceeded {config.timeouts.run}s — killed; resuming from checkpoint")
            continue
        except Exception:
            log(f"run {r}: crashed:\n{traceback.format_exc()}")
            rc = 1
        if rc == 0 and store.has(ArtifactKind.RUN_METRICS, run=r):
            return True
        log(f"run {r}: exit={rc}, done={store.has(ArtifactKind.RUN_METRICS, run=r)} — "
            f"{'retrying' if attempt < config.run_retries else 'giving up'}")
    status.set(phase="run_incomplete", run_index=r)
    log(f"run {r}: incomplete after {1 + config.run_retries} attempt(s); resume with the same --run-id")
    return False


def _run_once_isolated(config: Config, run_dir: Path, step_name: str) -> None:
    """Run one ONCE step in a plain subprocess (never Docker — control_arena has its own sandbox)."""
    cmd = [sys.executable, "-m", "pipeline.worker", str(run_dir.resolve()), "once", step_name]
    rc = run_isolated(cmd, timeout_s=max(config.timeouts.run, SCORE_STAGE_MIN_SECONDS), exec_mode=ExecMode.SUBPROCESS,
                      docker_image=None, run_dir=run_dir,
                      log_path=(run_dir / "pipeline.log") if config.progress else None)
    if rc != 0:
        raise RuntimeError(f"{step_name} subprocess failed (exit {rc}); see output above")


def _finalize(config: Config, store: ArtifactStore, status: "Any",
              outcome: tuple[list[Problem], list | None, list]) -> tuple[Path, dict[str, Any] | None]:
    """Aggregate metrics + write the report (after the dashboard has closed). Returns (run_dir, agg|None)."""
    run_dir = store.run_dir
    problems, per_run_metrics, rows_by_run = outcome
    if per_run_metrics is None:
        return run_dir, None
    if not per_run_metrics:
        status.set(phase="no_completed_runs")
        log("no runs completed (all abandoned/incomplete). Resume with the same --run-id to finish.")
        return run_dir, None

    agg = metrics_mod.aggregate_runs(per_run_metrics)
    manifest = {**config.to_json(), "n_tasks": len(problems)}
    report.compile_results(run_dir, config=manifest, run_metrics=per_run_metrics, agg=agg,
                           rows_by_run=rows_by_run)
    status.set(phase="done", completed_runs=len(per_run_metrics), requested_runs=config.runs)
    log(f"wrote {run_dir}  ({len(per_run_metrics)}/{config.runs} runs)")
    return run_dir, agg


def _require_inputs(store: ArtifactStore, step: Step) -> None:
    """Enforce a step's declared `needs` at run time (the run-global artifacts must already exist).

    Per-coordinate inputs (e.g. a per-task SUITE) are guaranteed by step ordering within a run, which
    `_validate_pipeline` checks at startup; here we assert the whole-run inputs a step assumes present.
    """
    for need in step.needs:
        if need in (ArtifactKind.PROBLEMS, ArtifactKind.SCORES) and not store.has(need):
            raise RuntimeError(f"step '{step.name}' needs {need.value}, which is missing")


async def _execute_run_async(config: Config, r: int, per_run_steps: list[Step], metrics: list["Metric"],
                             store: ArtifactStore, problems: list[Problem],
                             scores: dict[tuple[str, str], Any]) -> None:
    """Async body of one run: build the context, run each step fanned out, check completeness, persist."""
    status = store.status()
    t_model, u_model = _resolve_models(config, r)
    log(f"run {r}: worker start (strategy={config.gen_strategy.value}, seed={config.seed + r})")
    beat = asyncio.create_task(_heartbeat(status))
    ctx: RunContext | None = None
    try:
        with ThreadPoolExecutor(max_workers=config.exec_workers) as pool:
            ctx = RunContext(config, store, r, problems, scores, t_model, u_model,
                             RetryPolicy.from_config(config), asyncio.Semaphore(config.max_conn), pool)
            for step in per_run_steps:
                await _run_step(ctx, step)
    finally:
        beat.cancel()

    short = _incomplete_steps(ctx, per_run_steps)
    if short:
        detail = ", ".join(f"{name} {done}/{total}" for name, done, total in short)
        raise RuntimeError(f"run {r}: incomplete ({detail}) — resume to finish")
    rows = store.load(ArtifactKind.ROWS, run=r)
    m = _run_metrics(config, r, problems, store, rows, metrics)
    store.put(ArtifactKind.RUN_METRICS, (sorted(rows, key=_row_sort_key), m), run=r)
    log(f"run {r}: worker complete + checkpointed")


async def _run_step(ctx: RunContext, step: Step) -> None:
    """Execute one PER_RUN step generically: enforce inputs, fan out per its `FanoutSpec`, persist units.

    The fan-out granularity (which units, how to resume, how to persist, how to degrade) comes entirely
    from `FANOUTS[step.fanout]` — this function has no per-granularity branches.
    """
    _require_inputs(ctx.store, step)
    spec = FANOUTS[step.fanout]
    units = spec.units(ctx, step)
    done = spec.done_keys(ctx, step)
    todo = [u for u in units if spec.key(u) not in done]
    if done:
        log(f"run {ctx.r}: resumed {len(units) - len(todo)}/{len(units)} {step.name}")
    ctx.store.status().set(phase=step.name, run_index=ctx.r, done=len(units) - len(todo), total=len(units))
    log(f"run {ctx.r}: {step.name} for {len(todo)} units "
        f"({ctx.config.max_conn} gen / {ctx.config.exec_workers} eval concurrent)...")
    results = await asyncio.gather(*[_guard(ctx, step, spec, u) for u in todo], return_exceptions=True)
    for res in results:
        if isinstance(res, Exception):
            log(f"  [warn] {step.name} persist error: {type(res).__name__}: {res}")


async def _guard(ctx: RunContext, step: Step, spec: FanoutSpec, unit: Any) -> None:
    """Run one fan-out unit; on failure degrade it (or abstain) and continue — the per-unit boundary.

    This is why the step fns carry no try/except of their own: the one failure path for a unit lives
    here. A degraded value is persisted (e.g. a degraded suite); an `ABSTAIN` records nothing, leaving
    the run short of completeness so it resumes.
    """
    try:
        value = await asyncio.wait_for(step.fn(ctx, unit), timeout=ctx.config.timeouts.unit)
    except Exception as error:
        log(f"  [warn] {step.name} failed for {spec.label(unit)}: {type(error).__name__}: {error}")
        value = spec.on_fail(ctx, step, unit, error)
        if value is ABSTAIN:
            return
    spec.persist(ctx, step, unit, value)
    ctx.store.status().beat()


def _incomplete_steps(ctx: RunContext | None, per_run_steps: list[Step]) -> list[tuple[str, int, int]]:
    """Per-step completeness: (name, done, total) for any PER_RUN step short of all its units.

    Generic replacement for the old hardcoded row count: every step is complete iff every one of its
    fan-out units persisted its artifact (a PER_TASK crash degrades but still persists; a PER_CANDIDATE
    abstention does not, so it shows up here and triggers a resume).
    """
    if ctx is None:
        return [(s.name, 0, 0) for s in per_run_steps]
    short: list[tuple[str, int, int]] = []
    for step in per_run_steps:
        spec = FANOUTS[step.fanout]
        total = len(spec.units(ctx, step))
        done = len(spec.done_keys(ctx, step))
        if done < total:
            short.append((step.name, done, total))
    return short


def _run_metrics(config: Config, r: int, problems: list[Problem], store: ArtifactStore,
                 rows: list[dict[str, Any]], metrics: list["Metric"]) -> dict[str, Any]:
    """Compute this run's metrics by merging every metric object's fragment over the run's artifacts."""
    suites = {p.task_id: store.load(ArtifactKind.SUITE, run=r, task_id=p.task_id) for p in problems}
    metas = {t: (s or {}).get("meta", {}) for t, s in suites.items()}
    suite_validity = {t: bool(m.get("valid")) for t, m in metas.items()}
    suite_soundness = {t: pbt.suite_all_props_sound(m) for t, m in metas.items()}
    suite_harness_failed = {t: pbt.suite_harness_failed(m) for t, m in metas.items()}
    selected_policy = {p.task_id: p.selected_attack for p in problems}
    merged: dict[str, Any] = {}
    for metric in metrics:
        merged.update(metric.compute(rows, selected_policy, suite_validity, suite_soundness,
                                     config=config, seed=config.seed + r,
                                     suite_harness_failed=suite_harness_failed))
    return merged


async def _heartbeat(status: "Any") -> None:
    """Refresh status.json every HEARTBEAT_SECONDS so a stalled run is observable."""
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        status.beat()


def _resolve_models(config: Config, r: int) -> tuple[model_mod.TrustedModel, model_mod.TrustedModel]:
    """Resolve the trusted (T) and untrusted (U) models for run `r`.

    Effort, token cap and per-call bound are resolved per model. T doubles as the monitor, so a
    single global effort would confound any elicitation contrast.
    """
    t_model = model_mod.resolve(config.trusted_runtime(r))
    u_model = (model_mod.resolve(config.untrusted_runtime(r))
               if config.uses_separate_untrusted else t_model)
    return t_model, u_model


def _row_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    """Stable ordering for persisted rows (by task then candidate label)."""
    return (row["task_id"], row["candidate_label"])


def _record_backdoor_count(problems: list[Problem], scores: dict[tuple[str, str], Any]) -> None:
    """Log how many attacks are ground-truth successful backdoors (main + side both true)."""
    n = sum(1 for p in problems for c in p.attacks
            if scores[(p.task_id, c.candidate_id)].main_task_success
            and scores[(p.task_id, c.candidate_id)].side_task_success)
    log(f"successful backdoors (ground truth): {n}")


def _write_run_manifest(run_dir: Path, config: Config) -> None:
    """Persist the Config to run.json so isolated workers can rebuild it (and report can read it)."""
    artifacts.write_json(run_dir / "run.json", config.to_json())


def _docker_wrap(cmd: list[str], image: str | None, run_dir: Path, container: str) -> list[str]:
    """Wrap a worker command as `docker run --name <container>`, mounting the repo + forwarding creds.

    Docker requires absolute mount paths. The run directory normally lives under the repo, so mounting
    the repo exposes it too; a run_dir outside the repo is mounted separately. Only CREDENTIALS (and
    MPLBACKEND) come from the host env — every run knob is in run.json, which the worker reads, so a
    Docker run can never silently diverge from its manifest.
    """
    if not image:
        raise ValueError("--exec-mode docker requires --docker-image")
    repo = _repo_root()
    mounts = ["-v", f"{repo}:{repo}"]
    resolved = run_dir.resolve()
    if repo not in resolved.parents:
        mounts += ["-v", f"{resolved}:{resolved}"]
    env_flags: list[str] = []
    for key in ("AZUREAI_API_KEY", "AZUREAI_BASE_URL", "AZUREAI_ENDPOINT_URL", "AZURE_API_KEY",
                "AZURE_ENDPOINT_URL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "MPLBACKEND"):
        if os.getenv(key) is not None:
            env_flags += ["-e", key]
    container_cmd = ["python", *cmd[1:]]
    return (["docker", "run", "--rm", "--name", container, *mounts, "-w", str(repo), *env_flags, image]
            + container_cmd)


def _container_name(run_dir: Path) -> str:
    """A unique-per-invocation container name so a timeout can `docker kill` exactly this run's container."""
    return f"pbt-{run_dir.name}-{os.getpid()}-{int(time.time())}"


def _docker_kill(container: str) -> None:
    """Best-effort `docker kill` — SIGKILLing the host `docker run` CLI would orphan the container."""
    try:
        subprocess.run(["docker", "kill", container], capture_output=True, timeout=20)
    except Exception:
        pass


def _kill_tree(pid: int) -> None:
    """SIGKILL a process and ALL its descendants, incl. grandchildren in their own sessions.

    The pbt harness starts a new session, so a process-group kill alone misses it; we enumerate the full
    descendant set (one `ps` snapshot) and kill each, then sweep the worker's own group for good measure.
    """
    for victim in _descendants(pid) + [pid]:
        try:
            os.kill(victim, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _descendants(pid: int) -> list[int]:
    """All transitive child PIDs of `pid` from one `ps` snapshot (portable across macOS/Linux)."""
    try:
        snap = subprocess.run(["ps", "-Ao", "pid=,ppid="], capture_output=True, text=True,
                              timeout=5).stdout
    except Exception:
        return []
    kids: dict[int, list[int]] = {}
    for line in snap.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            kids.setdefault(int(parts[1]), []).append(int(parts[0]))
    found, stack = [], [pid]
    while stack:
        for kid in kids.get(stack.pop(), []):
            found.append(kid)
            stack.append(kid)
    return found


def _repo_root() -> Path:
    """Absolute path to the repository root (parent of the `pipeline` package)."""
    return Path(__file__).resolve().parent.parent
