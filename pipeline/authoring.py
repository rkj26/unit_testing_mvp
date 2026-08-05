"""Declarative authoring pipelines for PBT generation strategies.

Replaces hardcoded branch logic with a declarative, composable step architecture
for authoring properties, plans, and trigger search spaces, including an interactive
critique refinement loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import pbt
from .config import GenStrategy
from .schema import Problem

if TYPE_CHECKING:
    from .engine import RunContext


@dataclass
class Authored:
    """The completions one task's authoring produced, with each abstention recorded by name."""

    properties: str = ""
    search_space: str = ""
    plan: str = ""
    plan_required: bool = False

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


async def _call(
    ctx: RunContext, prompt: str, kind: str, model: Any
) -> Coroutine[Any, Any, str]:
    from .engine import with_retry

    res = await with_retry(
        lambda: model.complete(prompt, kind), ctx.retry, sem=ctx.sem, label=kind
    )
    return res or ""


class RefinementLoop:
    """Interactive critique & refinement loop for generated properties.

    Evaluates property code syntax and spec-only critique feedback over 1 or more turns,
    refining property completions before freezing the task suite.
    """

    def __init__(self, max_turns: int = 1) -> None:
        self.max_turns = max_turns

    async def refine(self, ctx: RunContext, problem: Problem, prop_c: str) -> str:
        from .engine import log

        if not (ctx.config.self_critique and prop_c):
            return prop_c

        current = prop_c
        for turn in range(self.max_turns):
            base_src, error = pbt.parse_properties(current)
            if not base_src:
                break
            crit_c = await _call(
                ctx, pbt.critique_prompt(problem, base_src), "property_gen", ctx.t_model
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
        author_fn: Callable[[RunContext, Problem], Coroutine[Any, Any, Authored]],
    ) -> None:
        self.name = name
        self.author_fn = author_fn

    async def execute(self, ctx: RunContext, problem: Problem) -> Authored:
        return await self.author_fn(ctx, problem)


async def _author_blind_t(ctx: RunContext, problem: Problem) -> Authored:
    n = ctx.config.tests_per_problem
    search = _call(
        ctx,
        pbt.search_prompt(problem, ctx.config.search_prompt),
        "trigger_search",
        ctx.t_model,
    )
    prop_c, space_c = await asyncio.gather(
        _call(
            ctx,
            pbt.property_prompt(problem, n, ctx.config.property_prompt),
            "property_gen",
            ctx.t_model,
        ),
        search,
    )
    return Authored(
        properties=await _maybe_critique(ctx, problem, prop_c), search_space=space_c
    )


async def _author_u_writes(ctx: RunContext, problem: Problem) -> Authored:
    n = ctx.config.tests_per_problem
    search = _call(
        ctx,
        pbt.search_prompt(problem, ctx.config.search_prompt),
        "trigger_search",
        ctx.t_model,
    )
    prop_c, space_c = await asyncio.gather(
        _call(
            ctx,
            pbt.property_prompt(problem, n, ctx.config.property_prompt),
            "property_gen",
            ctx.u_model,
        ),
        search,
    )
    return Authored(
        properties=await _maybe_critique(ctx, problem, prop_c), search_space=space_c
    )


async def _author_plan_writes(
    ctx: RunContext, problem: Problem, writer_is_trusted: bool
) -> Authored:
    from .engine import log

    n = ctx.config.tests_per_problem
    search = _call(
        ctx,
        pbt.search_prompt(problem, ctx.config.search_prompt),
        "trigger_search",
        ctx.t_model,
    )
    writer = ctx.t_model if writer_is_trusted else ctx.u_model
    plan = await _call(ctx, pbt.plan_prompt(problem, n), "plan", ctx.u_model)
    if not plan:
        log(
            f"    plan abstained ({problem.task_id}) — not writing properties from an empty plan"
        )
        return Authored(
            properties="", search_space=await search, plan="", plan_required=True
        )
    prop_c, space_c = await asyncio.gather(
        _call(
            ctx, pbt.write_from_plan_prompt(problem, plan, n), "write_from_plan", writer
        ),
        search,
    )
    return Authored(
        properties=await _maybe_critique(ctx, problem, prop_c),
        search_space=space_c,
        plan=plan,
        plan_required=True,
    )


_STRATEGY_FUNCS: dict[
    GenStrategy, Callable[[RunContext, Problem], Coroutine[Any, Any, Authored]]
] = {
    GenStrategy.BLIND_T: _author_blind_t,
    GenStrategy.U_WRITES: _author_u_writes,
    GenStrategy.U_PLANS_T_WRITES: lambda ctx, p: _author_plan_writes(
        ctx, p, writer_is_trusted=True
    ),
    GenStrategy.U_PLANS_U_WRITES: lambda ctx, p: _author_plan_writes(
        ctx, p, writer_is_trusted=False
    ),
}


async def author_task(ctx: RunContext, problem: Problem) -> Authored:
    """Execute the configured authoring strategy for one problem."""
    author_fn = _STRATEGY_FUNCS[ctx.config.gen_strategy]
    strategy = StrategyPipeline(ctx.config.gen_strategy, author_fn)
    return await strategy.execute(ctx, problem)
