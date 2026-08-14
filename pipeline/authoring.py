"""Declarative authoring pipelines for PBT generation strategies.

Replaces hardcoded branch logic with a declarative, composable step architecture
for authoring properties, plans, and trigger search spaces, including an interactive
critique refinement loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from . import pbt
from .config import GenStrategy
from .outcome import Blame, Unknown, is_unknown
from .schema import Problem

if TYPE_CHECKING:
    from .engine import RunContext

Failures = dict[str, Unknown]


@dataclass
class Authored:
    """The completions one task's authoring produced, with each abstention recorded by name.

    `abstentions` names the steps that produced no text. `failures` says which of those were a CALL
    that never returned, and why. The two are not the same set, and the difference is who is to
    blame: a step in `failures` is INFRA, a step that abstained without one is a model that answered
    with nothing. Collapsing both into INFRA excluded genuine model failures from PBT's failure
    count, which flattered PBT.
    """

    properties: str = ""
    search_space: str = ""
    plan: str = ""
    plan_required: bool = False
    failures: Failures = field(default_factory=dict)

    @property
    def abstentions(self) -> list[str]:
        missing = []
        if self.plan_required and not self.plan:
            missing.append("plan")
        if not self.properties:
            missing.append("property_gen")
        if not self.search_space:
            missing.append("trigger_search")
        return missing

    @property
    def blame(self) -> Blame:
        return Blame.INFRA if self.failures else Blame.MODEL

    @property
    def why(self) -> str:
        """Every abstention by name, then every call failure by reason.

        Keyed separately because the names differ: the plan strategies get their properties from
        `write_from_plan`, so a failure there is what makes `property_gen` abstain.
        """
        named = ", ".join(self.abstentions)
        reasons = "; ".join(f.reason for f in self.failures.values())
        return f"{named} ({reasons})" if reasons else named


async def _call(
    ctx: RunContext, prompt: str, kind: str, model: Any, failures: Failures
) -> str:
    """One authoring call. A call that never returned records why, under its step's name."""
    from .engine import with_retry

    res = await with_retry(
        lambda: model.complete(prompt, kind), ctx.retry, sem=ctx.sem, label=kind
    )
    if is_unknown(res):
        failures[kind] = res
        return ""
    return res or ""


class RefinementLoop:
    """Interactive critique & refinement loop for generated properties.

    Evaluates property code syntax and spec-only critique feedback over 1 or more turns,
    refining property completions before freezing the task suite.

    A critique call that never returns is not an abstention — the draft properties stand and the
    suite is authored — so its failure is discarded rather than counted against the task.
    """

    def __init__(self, max_turns: int = 1) -> None:
        self.max_turns = max_turns

    async def refine(self, ctx: RunContext, problem: Problem, prop_c: str) -> str:
        from .engine import log

        if not (ctx.config.self_critique and prop_c):
            return prop_c

        discarded: Failures = {}
        current = prop_c
        for turn in range(self.max_turns):
            base_src, error = pbt.parse_properties(current)
            if not base_src:
                break
            crit_c = await _call(
                ctx,
                pbt.critique_prompt(problem, base_src),
                "property_gen",
                ctx.t_model,
                discarded,
            )
            crit_src, _ = pbt.parse_properties(crit_c)
            if crit_src:
                log(f"    critiqued {problem.task_id} (turn {turn + 1})")
                current = crit_c
            else:
                break
        return current


async def _maybe_critique(ctx: RunContext, problem: Problem, prop_c: str) -> str:
    return await RefinementLoop(max_turns=1).refine(ctx, problem, prop_c)


class StrategyPipeline:
    """Declarative authoring strategy executor."""

    def __init__(
        self,
        name: GenStrategy,
        author_fn: Callable[[RunContext, Problem, str], Coroutine[Any, Any, Authored]],
    ) -> None:
        self.name = name
        self.author_fn = author_fn

    async def execute(self, ctx: RunContext, problem: Problem, code: str) -> Authored:
        return await self.author_fn(ctx, problem, code)


async def _author_prompt_pair(
    ctx: RunContext, problem: Problem, writer: Any, code: str
) -> Authored:
    """The two concurrent authoring calls: properties from `writer`, trigger inputs from T.

    `code` is the submission being audited, empty on the spec-blind path. The trigger search is
    always trusted-authored, whichever model writes the properties.
    """
    n = ctx.config.tests_per_problem
    failures: Failures = {}
    search = _call(
        ctx,
        pbt.search_prompt(problem, ctx.config.search_prompt, code),
        "trigger_search",
        ctx.t_model,
        failures,
    )
    prop_c, space_c = await asyncio.gather(
        _call(
            ctx,
            pbt.property_prompt(problem, n, ctx.config.property_prompt, code),
            "property_gen",
            writer,
            failures,
        ),
        search,
    )
    return Authored(
        properties=await _maybe_critique(ctx, problem, prop_c),
        search_space=space_c,
        failures=failures,
    )


async def _author_blind_t(ctx: RunContext, problem: Problem, code: str) -> Authored:
    return await _author_prompt_pair(ctx, problem, ctx.t_model, code)


async def _author_u_writes(ctx: RunContext, problem: Problem, code: str) -> Authored:
    return await _author_prompt_pair(ctx, problem, ctx.u_model, code)


async def _author_plan_writes(
    ctx: RunContext, problem: Problem, code: str, writer_is_trusted: bool
) -> Authored:
    from .engine import log

    n = ctx.config.tests_per_problem
    failures: Failures = {}
    search = _call(
        ctx,
        pbt.search_prompt(problem, ctx.config.search_prompt, code),
        "trigger_search",
        ctx.t_model,
        failures,
    )
    writer = ctx.t_model if writer_is_trusted else ctx.u_model
    plan = await _call(ctx, pbt.plan_prompt(problem, n), "plan", ctx.u_model, failures)
    if not plan:
        log(
            f"    plan abstained ({problem.task_id}) — not writing properties from an empty plan"
        )
        return Authored(
            properties="",
            search_space=await search,
            plan="",
            plan_required=True,
            failures=failures,
        )
    prop_c, space_c = await asyncio.gather(
        _call(
            ctx,
            pbt.write_from_plan_prompt(problem, plan, n),
            "write_from_plan",
            writer,
            failures,
        ),
        search,
    )
    return Authored(
        properties=await _maybe_critique(ctx, problem, prop_c),
        search_space=space_c,
        plan=plan,
        plan_required=True,
        failures=failures,
    )


_STRATEGY_FUNCS: dict[
    GenStrategy, Callable[[RunContext, Problem, str], Coroutine[Any, Any, Authored]]
] = {
    GenStrategy.BLIND_T: _author_blind_t,
    GenStrategy.U_WRITES: _author_u_writes,
    GenStrategy.U_PLANS_T_WRITES: lambda ctx, p, code: _author_plan_writes(
        ctx, p, code, writer_is_trusted=True
    ),
    GenStrategy.U_PLANS_U_WRITES: lambda ctx, p, code: _author_plan_writes(
        ctx, p, code, writer_is_trusted=False
    ),
}


async def author_task(ctx: RunContext, problem: Problem) -> dict[str, Authored]:
    """One `Authored` per candidate.

    Spec-blind authoring runs ONCE and every candidate is handed the same result — the same calls,
    in the same order, as before this fan-out existed. Code-aware authoring runs once per candidate,
    concurrently, because the prompt embeds that candidate's submission.
    """
    author_fn = _STRATEGY_FUNCS[ctx.config.gen_strategy]
    strategy = StrategyPipeline(ctx.config.gen_strategy, author_fn)
    if not pbt.reads_candidate_code(
        ctx.config.property_prompt, ctx.config.search_prompt
    ):
        shared = await strategy.execute(ctx, problem, "")
        return {c.candidate_id: shared for c in problem.candidates}
    authored = await asyncio.gather(
        *(strategy.execute(ctx, problem, c.code) for c in problem.candidates)
    )
    return dict(zip((c.candidate_id for c in problem.candidates), authored))
