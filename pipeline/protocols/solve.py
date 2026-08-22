"""The trusted model's own attempt at the task, used later as a second implementation.

Not a monitor. It never sees a candidate and produces no verdict about one; it answers the problem
statement and nothing else, so its output is a comparator that owes nothing to the submission it
will later be compared against.

Scored per candidate like every other protocol, which means two independent attempts per task. That
is deliberate: where the two disagree, the trusted model is unreliable on that task, and a filter
built on its output should say so rather than trust one draw.

    solve = TrustedSolve(run_name="solve-v1", data=data, model=MODEL)
    solve.run()
    {r["task_id"]: r["solution"] for r in solve.get_records("test")}
"""

from __future__ import annotations

from typing import Any

from .. import parse, prompts
from ..data import Blame, Candidate, Dataset, Task
from ..model import (
    INSPECT_HTTP_RETRIES,
    MULTI_RUN_TEMPERATURE,
    SINGLE_RUN_TEMPERATURE,
    ModelRuntime,
    ModelSpec,
    Reasoning,
    TimeoutLadder,
    TrustedModel,
    complete_sync,
    resolve,
)
from .base import CALLS, Run

TEMPLATE = "trusted_solve.txt"
SOLVE_KIND = "property_gen"
DEFAULT_REASONING = Reasoning.LOW.value
REASON_CHARS = 300


def _runtime(name: str, reasoning: str, seed: int, temperature: float, cache: bool) -> ModelRuntime:
    """Endpoint knobs for one attempt, with the timeout ladder derived from the spec."""
    spec = ModelSpec(name=name, reasoning=Reasoning(reasoning))
    ladder = TimeoutLadder.derive(spec, spec)
    return ModelRuntime(
        name=name,
        temperature=temperature,
        seed=seed,
        attempt_timeout=ladder.trusted_call,
        http_timeout=ladder.http_retry_budget,
        http_retries=INSPECT_HTTP_RETRIES,
        max_tokens=spec.max_tokens,
        reasoning_effort=spec.reasoning,
        inspect_cache=cache,
    )


class TrustedSolve(Run):
    """One trusted attempt at each task, recorded as source a sandbox can run."""

    protocol = "trusted_solve"

    def __init__(self, *, reasoning: str = DEFAULT_REASONING, **kwargs: Any) -> None:
        super().__init__(reasoning=reasoning, **kwargs)
        if not self.model:
            raise ValueError(
                f"{self.run_name}: a solver with no model produces nothing — pass "
                "model='openai-api/azureai/DeepSeek-V3.2', or model='mock'"
            )
        self.reasoning = Reasoning(reasoning).value
        self.solvers: tuple[TrustedModel, ...] = ()

    @property
    def temperature(self) -> float:
        return SINGLE_RUN_TEMPERATURE if self.runs == 1 else MULTI_RUN_TEMPERATURE

    def prepare(self, data: Dataset) -> None:
        """One client per repetition, since each fixes its seed when it resolves."""
        self.solvers = tuple(
            resolve(_runtime(self.model, self.reasoning, seed, self.temperature, self.cache))
            for seed in self.seeds
        )

    def score(self, task: Task, candidate: Candidate) -> dict[str, Any]:
        """The attempt, as source. Blind: the prompt carries the statement and nothing else.

        `solution` is `None` when no repetition returned a parseable program, and the record is
        `failed`. An empty string would read downstream as a solver that answered with nothing,
        which is a different claim from a solver that never answered.
        """
        if not self.solvers:
            raise RuntimeError(f"{self.run_name}: prepare() has not run, so there is no solver")

        prompt = prompts.render(TEMPLATE, **task.blind())
        calls = [self._one_attempt(rep, prompt) for rep in range(self.runs)]
        solved = [call["solution"] for call in calls if call["solution"]]
        if not solved:
            return {
                CALLS: calls,
                "solution": None,
                "solution_chars": 0,
                "failed": True,
                "blame": Blame.MODEL.value,
                "reason": "; ".join(
                    f"rep {call['rep']}: {call['reason']}" for call in calls if call["reason"]
                )[:REASON_CHARS]
                or "no parseable program in any repetition",
            }
        return {
            CALLS: calls,
            "solution": solved[0],
            "solution_chars": len(solved[0]),
            "attempts_agree": len(set(solved)) == 1 if len(solved) > 1 else None,
        }

    def _one_attempt(self, rep: int, prompt: str) -> dict[str, Any]:
        """One call, with the program extracted from its fenced block."""
        completion = complete_sync(self.solvers[rep], prompt, SOLVE_KIND)
        source, error = parse.parse_program(completion.text)
        return {
            "rep": rep,
            "seed": self.seeds[rep],
            "prompt": prompt,
            "raw": completion.text,
            "reasoning": completion.reasoning,
            "stop_reason": completion.stop_reason,
            "solution": source,
            "reason": error,
        }
