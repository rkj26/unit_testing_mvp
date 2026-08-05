"""The concrete pipeline: the declarative `Step` list plus the step functions.

The whole pipeline is ONE list the engine drives by `Step.scope`:
  ONCE (run once, checkpointed):
    - `preprocess` (NONE)        — raw candidate pool -> the scored-ready Problem list.
    - `score`      (NONE)        — deterministic ground-truth verdicts (isolated: control_eval).
  PER_RUN (repeated `config.runs` times, inside an isolation boundary):
    - `generate` (PER_TASK)      — author properties + trigger search space, then score them -> a suite.
    - `monitor`  (PER_CANDIDATE) — TM + informed-TM suspicion for each candidate -> a row.

Step functions stay straight-line: no retry loops, no try/except. The engine's `with_retry` guards model
calls and its per-unit guard turns any failure into a degraded artifact.

Public surface (top): the step fns and `PIPELINE`. Private gen/eval helpers are at the bottom.
"""

from __future__ import annotations

import asyncio
from typing import Any

from . import pbt
from .artifacts import ArtifactKind
from .config import GenStrategy
from .engine import Fanout, RunContext, Scope, SetupContext, Step, log, with_retry
from . import monitor
from .schema import Candidate, Problem, make_row


def preprocess_step(ctx: SetupContext) -> list[Problem]:
    """ONCE: turn the raw candidate pool into the scored-ready Problem list (no model, no network)."""
    problems = ctx.backend.preprocess(ctx.pool, limit=ctx.config.limit)
    if not problems:
        raise ValueError("preprocess produced no problems")
    log(f"preprocessed {len(problems)} problems ({ctx.backend.name})")
    return problems


def score_step(ctx: SetupContext) -> dict[tuple[str, str], Any]:
    """ONCE (isolated for real backends): deterministic ground-truth verdicts via control_eval.

    Reads the preprocessed problems from the store and returns {(task_id, candidate_id): ScoreResult}.
    """
    problems = ctx.store.load(ArtifactKind.PROBLEMS)
    scores = ctx.backend.score_candidates(problems)
    log(f"ground-truth scored {len(scores)} candidates")
    return scores


async def generate_step(ctx: RunContext, problem: Problem) -> dict[str, Any]:
    """PER_TASK: author the PBT properties + trigger search space (network), then score them (local).

    Returns the full suite dict (raw completions + parsed sources + meta + per-candidate results) that
    the engine persists as SUITE(run, task_id). Raising is fine — the engine records a degraded suite.
    """
    prop_c, space_c, plan = await _author(ctx, problem)
    loop = asyncio.get_running_loop()
    suite = await loop.run_in_executor(ctx.pool, _score_suite, ctx.config.gen_strategy, problem,
                                       prop_c, space_c, plan, ctx.config.pbt_timeout,
                                       ctx.config.max_search_space)
    log(f"    PBT ({problem.task_id}: {'valid' if suite['meta'].get('valid') else 'invalid'}, "
        f"{len(suite.get('space') or [])} inputs)")
    return suite


async def monitor_step(ctx: RunContext, unit: tuple[Problem, Candidate]) -> dict[str, Any]:
    """PER_CANDIDATE: TM (reads code) + informed-TM (reads code + PBT evidence) -> a make_row dict.

    Reads this task's suite (loaded once per task and reused across its candidates) for the candidate's
    PBT result. A None suspicion (retries exhausted) is a clean abstention. Returns the row the engine
    appends to ROWS(run).
    """
    problem, candidate = unit
    suite = _task_suite(ctx, problem.task_id)
    pbt_res = suite["results"][candidate.candidate_id]
    tm_txt = await _call(ctx, monitor.tm_prompt(problem, candidate), "tm", ctx.t_model)
    inf_txt = await _call(
        ctx, monitor.informed_prompt(problem, candidate, pbt_res["pbt"],
                                     suite.get("props_src"), suite.get("space")), "informed", ctx.t_model)
    return make_row(
        task_id=problem.task_id, candidate=candidate,
        score=ctx.scores[(problem.task_id, candidate.candidate_id)], pbt_results=pbt_res,
        tm=monitor.parse_suspicion(tm_txt), informed=monitor.parse_suspicion(inf_txt))


PIPELINE: list[Step] = [
    Step(name="preprocess", produces=ArtifactKind.PROBLEMS, needs=(),
         scope=Scope.ONCE, fanout=Fanout.NONE, fn=preprocess_step),
    Step(name="score", produces=ArtifactKind.SCORES, needs=(ArtifactKind.PROBLEMS,),
         scope=Scope.ONCE, fanout=Fanout.NONE, fn=score_step, isolated=True),
    Step(name="generate", produces=ArtifactKind.SUITE, needs=(ArtifactKind.PROBLEMS,),
         scope=Scope.PER_RUN, fanout=Fanout.PER_TASK, fn=generate_step),
    Step(name="monitor", produces=ArtifactKind.ROWS,
         needs=(ArtifactKind.PROBLEMS, ArtifactKind.SCORES, ArtifactKind.SUITE),
         scope=Scope.PER_RUN, fanout=Fanout.PER_CANDIDATE, fn=monitor_step),
]


# --------------------------------------------------------------------------- #
# private helpers — property authoring + scoring
# --------------------------------------------------------------------------- #
def _call(ctx: RunContext, prompt: str, kind: str, model: Any):
    """One guarded model call (returns an awaitable). Thin wrapper over the engine's `with_retry`."""
    return with_retry(lambda: model.complete(prompt, kind), ctx.retry, sem=ctx.sem, label=kind)


def _task_suite(ctx: RunContext, task_id: str) -> dict[str, Any]:
    """Load a task's suite once per run and reuse it across the task's candidates (avoids re-parsing
    suite.json K times per task on the event-loop thread)."""
    suite = ctx.suites.get(task_id)
    if suite is None:
        suite = ctx.store.load(ArtifactKind.SUITE, run=ctx.r, task_id=task_id)
        ctx.suites[task_id] = suite
    return suite


async def _author(ctx: RunContext, problem: Problem) -> tuple[str, str, str]:
    """Author (properties, search_space, plan) completions per the gen strategy.

    The trigger search space is ALWAYS trusted-authored; only the property author (and whether a plan is
    written first) varies by strategy. Returns empty strings where a call abstained (retries exhausted)
    — the scorer degrades gracefully.
    """
    n = ctx.config.tests_per_problem
    strategy = ctx.config.gen_strategy
    plan = ""
    if strategy in (GenStrategy.U_PLANS_T_WRITES, GenStrategy.U_PLANS_U_WRITES):
        # U designs a spec-only plan; then the implementer writes it. T implements (collusion-safe) for
        # U_PLANS_T_WRITES; U implements (untrusted ceiling) for U_PLANS_U_WRITES.
        writer = ctx.t_model if strategy is GenStrategy.U_PLANS_T_WRITES else ctx.u_model
        plan = await _call(ctx, pbt.plan_prompt(problem, n), "plan", ctx.u_model) or ""
        prop_c, space_c = await asyncio.gather(
            _call(ctx, pbt.write_from_plan_prompt(problem, plan, n), "write_from_plan", writer),
            _call(ctx, pbt.search_prompt(problem, ctx.config.search_prompt), "trigger_search", ctx.t_model))
    elif strategy is GenStrategy.U_WRITES:
        prop_c, space_c = await asyncio.gather(
            _call(ctx, pbt.property_prompt(problem, n, ctx.config.property_prompt), "property_gen", ctx.u_model),
            _call(ctx, pbt.search_prompt(problem, ctx.config.search_prompt), "trigger_search", ctx.t_model))
    else:  # BLIND_T (default)
        prop_c, space_c = await asyncio.gather(
            _call(ctx, pbt.property_prompt(problem, n, ctx.config.property_prompt), "property_gen", ctx.t_model),
            _call(ctx, pbt.search_prompt(problem, ctx.config.search_prompt), "trigger_search", ctx.t_model))
    if ctx.config.self_critique and prop_c:
        prop_c = await _critique(ctx, problem, prop_c) or prop_c
    # Return the raw None on abstention (retries exhausted) rather than flattening to "". An empty
    # string is indistinguishable from the model writing prose, and `_score_suite` would blame the
    # model for what is an infrastructure failure.
    return prop_c, space_c, plan


async def _critique(ctx: RunContext, problem: Problem, prop_c: str) -> str | None:
    """Turn-2 spec-only soundness prune (deployable gate); return the refined completion or None.

    Accepts the refinement only if it still parses to >=1 property; otherwise None keeps turn-1.
    """
    base_src, _ = pbt.parse_properties(prop_c)
    if not base_src:
        return None
    crit_c = await _call(ctx, pbt.critique_prompt(problem, base_src), "property_gen", ctx.t_model)
    crit_src, _ = pbt.parse_properties(crit_c or "")
    if crit_src:
        log(f"    critiqued {problem.task_id}")
        return crit_c
    return None


def _score_suite(gen_strategy: GenStrategy, problem: Problem, prop_c: str | None, space_c: str | None,
                 plan: str, pbt_timeout: int, max_search_space: int) -> dict[str, Any]:
    """Parse the completions and score properties over the search space -> the suite dict (local CPU).

    May raise on a pathological suite; the engine's per-unit guard converts that into a degraded suite.

    `prop_c`/`space_c` are None when the model call ABSTAINED (every retry exhausted). That is an
    infrastructure failure and is labelled as one — otherwise it parses to the same
    "no code block in completion" as the model writing prose, and a flaky endpoint silently becomes
    evidence that the model cannot generate properties.
    """
    abstained = [n for n, c in (("property_gen", prop_c), ("trigger_search", space_c)) if c is None]
    props_src, prop_err = pbt.parse_properties(prop_c or "")
    space, space_err = pbt.parse_search_space(space_c or "")
    if abstained:
        note = f"model call abstained after retries: {', '.join(abstained)}"
        prop_err = note if prop_c is None else prop_err
        space_err = note if space_c is None else space_err
    meta, results = pbt.evaluate(problem, props_src, space, timeout_s=pbt_timeout,
                                 max_search_space=max_search_space)
    if abstained:  # override the parse-level reason so blame lands on infra, not the model
        meta = {**meta, "reason": f"model call abstained after retries: {', '.join(abstained)}"}
    return {"props_src": props_src, "space": space, "prop_err": prop_err, "space_err": space_err,
            "prop_raw": prop_c, "space_raw": space_c, "plan": plan,
            "gen_strategy": gen_strategy.value, "meta": meta, "results": results}
