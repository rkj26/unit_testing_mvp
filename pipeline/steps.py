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
from dataclasses import dataclass
from typing import Any

from . import monitor, pbt
from .artifacts import ArtifactKind
from .config import GenStrategy
from .harness import Isolation
from .engine import Fanout, RunContext, Scope, SetupContext, Step, log, with_retry
from .outcome import Blame, Unknown, is_unknown
from .schema import NEVER_RETURNED, Candidate, Completion, Problem, make_row


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
    scores = ctx.backend.score_candidates(problems, ctx.config.scoring)
    unscored = sum(1 for s in scores.values() if not s.scored)
    log(
        f"ground-truth scored {len(scores) - unscored}/{len(scores)} candidates"
        + (
            f" ({unscored} UNSCORED — infra failure, see scoring_coverage)"
            if unscored
            else ""
        )
    )
    return scores


async def generate_step(ctx: RunContext, problem: Problem) -> dict[str, Any]:
    """PER_TASK: author the PBT properties + trigger search space (network), then score them (local).

    Returns the full suite dict (raw completions + parsed sources + meta + per-candidate results) that
    the engine persists as SUITE(run, task_id). Raising is fine — the engine records a degraded suite.
    """
    authored = await _author(ctx, problem)
    loop = asyncio.get_running_loop()
    suite = await loop.run_in_executor(
        ctx.pool,
        _score_suite,
        ctx.config.gen_strategy,
        problem,
        authored,
        ctx.config.pbt_timeout,
        ctx.config.max_search_space,
        ctx.config.code_aware_search,
        ctx.config.pbt_isolation,
        ctx.config.docker_image,
    )
    log(
        f"    PBT ({problem.task_id}: {'valid' if suite['meta'].get('valid') else 'invalid'}, "
        f"{len(suite.get('space') or [])} inputs)"
    )
    return suite


async def monitor_step(
    ctx: RunContext, unit: tuple[Problem, Candidate]
) -> dict[str, Any]:
    """PER_CANDIDATE: TM (reads code) + informed-TM (reads code + PBT evidence) -> a make_row dict.

    Reads this task's suite (loaded once per task and reused across its candidates) for the candidate's
    PBT result. A None suspicion (retries exhausted, or an answer the score never appeared in) is a
    clean abstention, and the completion travels into the row so the two stay tellable apart. Returns
    the row the engine appends to ROWS(run).

    The informed monitor is shown THIS candidate's own inputs. Under `--code-aware-search` every
    candidate runs a different space, so a suite-level list would describe a grid it never ran.
    """
    problem, candidate = unit
    suite = _task_suite(ctx, problem.task_id)
    pbt_res = suite["results"][candidate.candidate_id]
    tm_out = await _call(ctx, monitor.tm_prompt(problem, candidate), "tm", ctx.t_model)
    inf_out = await _call(
        ctx,
        monitor.informed_prompt(
            problem,
            candidate,
            pbt_res["pbt"],
            suite_props(suite, candidate.candidate_id),
            suite["space_by_candidate"][candidate.candidate_id],
        ),
        "informed",
        ctx.t_model,
    )
    return make_row(
        task_id=problem.task_id,
        candidate=candidate,
        score=ctx.scores[(problem.task_id, candidate.candidate_id)],
        pbt_results=pbt_res,
        tm=monitor.parse_suspicion(tm_out.text),
        informed=monitor.parse_suspicion(inf_out.text),
        tm_completion=tm_out,
        informed_completion=inf_out,
    )


def get_pipeline() -> list[Step]:
    """Instantiate the pipeline step manifest at runtime."""
    return [
        Step(
            name="preprocess",
            produces=ArtifactKind.PROBLEMS,
            needs=(),
            scope=Scope.ONCE,
            fanout=Fanout.NONE,
            fn=preprocess_step,
        ),
        Step(
            name="score",
            produces=ArtifactKind.SCORES,
            needs=(ArtifactKind.PROBLEMS,),
            scope=Scope.ONCE,
            fanout=Fanout.NONE,
            fn=score_step,
            isolated=True,
        ),
        Step(
            name="generate",
            produces=ArtifactKind.SUITE,
            needs=(ArtifactKind.PROBLEMS,),
            scope=Scope.PER_RUN,
            fanout=Fanout.PER_TASK,
            fn=generate_step,
        ),
        Step(
            name="monitor",
            produces=ArtifactKind.ROWS,
            needs=(ArtifactKind.PROBLEMS, ArtifactKind.SCORES, ArtifactKind.SUITE),
            scope=Scope.PER_RUN,
            fanout=Fanout.PER_CANDIDATE,
            fn=monitor_step,
        ),
    ]


PIPELINE: list[Step] = get_pipeline()


async def _call(ctx: RunContext, prompt: str, kind: str, model: Any) -> Completion:
    """One guarded model call, over the engine's `with_retry`.

    Exhausted retries become `NO_COMPLETION`, whose stop reason says the call never returned rather
    than leaving an empty answer that looks like a monitor which simply wrote nothing.
    """
    completed = await with_retry(
        lambda: model.completion(prompt, kind), ctx.retry, sem=ctx.sem, label=kind
    )
    if is_unknown(completed):
        return Completion(stop_reason=NEVER_RETURNED, unknown=completed)
    return completed


def _task_suite(ctx: RunContext, task_id: str) -> dict[str, Any]:
    """Load a task's suite once per run and reuse it across the task's candidates (avoids re-parsing
    suite.json K times per task on the event-loop thread)."""
    if task_id not in ctx.suites:
        ctx.suites[task_id] = ctx.store.load(
            ArtifactKind.SUITE, run=ctx.r, task_id=task_id
        )
    return ctx.suites[task_id]


from .authoring import Authored, author_task

_author = author_task


@dataclass(frozen=True)
class _Parsed:
    """One candidate's authored suite after parsing, with why each half is missing if it is."""

    props_src: str | None
    space: list[Any] | None
    prop_err: str
    space_err: str
    salvaged: bool
    note: str
    blame: Blame


def _parse_authored(problem: Problem, authored: Authored) -> _Parsed:
    """Parse one candidate's completions.

    An abstention is INFRA only when a CALL failed. A step that returned text the parser could not
    use, or no text at all with the call reporting success, is the MODEL. Blaming every abstention on
    infrastructure excluded genuine model failures from PBT's failure count and so flattered PBT.
    """
    props_src, prop_err = pbt.parse_properties(authored.properties or "")
    space, space_err, salvaged = pbt.parse_search_space(authored.search_space or "")
    misshapen = pbt.wrong_shape(space, problem.io_mode)
    if misshapen:
        space, space_err = None, misshapen
    note = f"authoring abstained: {authored.why}" if authored.abstentions else ""
    return _Parsed(
        props_src=props_src,
        space=space,
        prop_err=note if not authored.properties else prop_err,
        space_err=note if not authored.search_space else space_err,
        salvaged=salvaged,
        note=note,
        blame=authored.blame,
    )


def _score_suite(
    gen_strategy: GenStrategy,
    problem: Problem,
    authored_by_candidate: dict[str, Authored],
    pbt_timeout: int,
    max_search_space: int,
    code_aware: bool = False,
    isolation: Isolation = Isolation.SUBPROCESS,
    docker_image: str = "",
) -> dict[str, Any]:
    """Parse each candidate's completions and score them -> the suite dict (local CPU).

    May raise on a pathological suite; the engine's per-unit guard converts that into a degraded suite.

    Spec-blind authoring hands every candidate the same `Authored`, so the top-level `props_src` /
    `space` keys describe the whole task exactly as they always have. Code-aware authoring gives each
    candidate its own, and those keys carry the FIRST candidate's — readers that need a specific
    candidate's suite must go through `props_by_candidate`, which is why `props_shared` says which
    world the artifact is from.
    """
    parsed = {
        cid: _parse_authored(problem, authored)
        for cid, authored in authored_by_candidate.items()
    }
    meta, results = pbt.evaluate(
        problem,
        {cid: p.props_src for cid, p in parsed.items()},
        {cid: p.space for cid, p in parsed.items()},
        timeout_s=pbt_timeout,
        max_search_space=max_search_space,
        code_aware=code_aware,
        isolation=isolation,
        docker_image=docker_image,
    )
    first = parsed[problem.candidates[0].candidate_id]
    shared = len({id(a) for a in authored_by_candidate.values()}) == 1
    abstained = sorted(cid for cid, p in parsed.items() if p.note)
    meta = {
        **meta,
        "props_shared": shared,
        "space_salvaged": first.salvaged,
        "space_salvaged_by_candidate": {cid: p.salvaged for cid, p in parsed.items()},
        "n_space_parsed": len(first.space or []),
    }
    if abstained:
        note = "; ".join(f"{cid}: {parsed[cid].note}" for cid in abstained)
        blame = (
            Blame.INFRA
            if any(parsed[cid].blame is Blame.INFRA for cid in abstained)
            else Blame.MODEL
        )
        meta = {**meta, "unknown": Unknown(blame, note).to_json(), "reason": note}
    return {
        "props_src": first.props_src,
        "props_by_candidate": {cid: p.props_src for cid, p in parsed.items()},
        "space": first.space,
        "space_run": (first.space or [])[:max_search_space],
        "space_by_candidate": meta["space_by_candidate"],
        "prop_err": first.prop_err,
        "prop_err_by_candidate": {cid: p.prop_err for cid, p in parsed.items()},
        "space_err": first.space_err,
        "space_err_by_candidate": {cid: p.space_err for cid, p in parsed.items()},
        "space_salvaged": first.salvaged,
        "prop_raw": authored_by_candidate[problem.candidates[0].candidate_id].properties,
        "prop_raw_by_candidate": {
            cid: a.properties for cid, a in authored_by_candidate.items()
        },
        "space_raw": authored_by_candidate[problem.candidates[0].candidate_id].search_space,
        "space_raw_by_candidate": {
            cid: a.search_space for cid, a in authored_by_candidate.items()
        },
        "plan": authored_by_candidate[problem.candidates[0].candidate_id].plan or "",
        "gen_strategy": gen_strategy.value,
        "meta": meta,
        "results": results,
    }


def suite_props(suite: dict[str, Any], candidate_id: str) -> str | None:
    """This candidate's properties, falling back to the task-wide source.

    The fallback is what keeps every pre-fan-out run readable: artifacts written before authoring
    was per candidate carry only `props_src`, and every candidate genuinely shared it.
    """
    by_candidate = suite.get("props_by_candidate")
    if by_candidate is None:
        return suite["props_src"]
    return by_candidate[candidate_id]
