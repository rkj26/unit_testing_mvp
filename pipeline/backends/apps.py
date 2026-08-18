"""APPS backend.

Ground-truth scoring runs on the inspect/control_arena framework via CorrectedAppsSetting (local
sandbox) — same eval machinery + dataset + comparison semantics as stock AppsSetting, but the
corrected scorer judges on exit code + stdout (control_arena's stock APPS scorer treats stderr
warnings as fatal, which false-negatives modern-Python solutions). Task spec + a reference for the
blind PBT soundness gate come inline from the pool; candidates are stdin/stdout programs.
"""

from __future__ import annotations

from typing import Any

from ..config import ScoringLimits
from ..schema import Candidate, Problem, ScoreResult
from ..scoring import CorrectedAppsSetting, score_via_control_arena


def _hint(inputs: list[str], outputs: list[str], n: int = 3) -> str:
    lines = [
        f"  STDIN={inputs[i]!r} -> STDOUT={outputs[i]!r}"
        for i in range(min(n, len(inputs), len(outputs)))
    ]
    return "\n".join(lines) or "(none provided)"


def statement_examples(task: dict[str, Any]) -> tuple[list[str], list[str]]:
    """The stored input/output pairs a deployment can actually see.

    An APPS pool files its whole grading set under `provided_inputs`, hidden cases included: 1,986
    pairs across `apps_pool_hard.json` against the 132 its problem statements actually print. A
    defender has the statement and nothing else, so a pair is spec-safe only if the statement shows
    its input; every other pair is the answer key, and handing it to a blind step is a leak.

    Matching is whitespace-normalised because statements pretty-print their examples. On the hard
    pool this keeps a median of 2 pairs per task and leaves no task with none.
    """

    def normalise(text: str) -> str:
        return " ".join(text.split())

    statement = normalise(task["task_description"])
    pairs = [
        (raw_in, raw_out)
        for raw_in, raw_out in zip(
            task.get("provided_inputs", []), task.get("provided_outputs", [])
        )
        if normalise(raw_in) and normalise(raw_in) in statement
    ]
    return [raw_in for raw_in, _ in pairs], [raw_out for _, raw_out in pairs]


class AppsBackend:
    name = "apps"

    def __init__(self) -> None:
        self._setting = CorrectedAppsSetting(sandbox_type="local")

    def preprocess(
        self, pool: dict[str, Any], *, limit: int | None = None
    ) -> list[Problem]:
        items = list(pool["candidates"].items())
        if limit:
            items = items[:limit]
        problems: list[Problem] = []
        for task_id, t in items:
            example_inputs, example_outputs = statement_examples(t)
            cands = [
                Candidate(
                    t["honest"]["candidate_id"], "honest", t["honest"]["code"], None
                )
            ]
            for i, attack in enumerate(t["attack_proposals"]):
                cands.append(
                    Candidate(
                        attack["candidate_id"],
                        f"attack_{i}",
                        attack["code"],
                        attack["secret_input"],
                    )
                )
            problems.append(
                Problem(
                    task_id=str(task_id),
                    main_task=t["task_description"],
                    io_mode="stdio",
                    candidates=cands,
                    provided_tests_hint=_hint(example_inputs, example_outputs),
                    provided_inputs=example_inputs,
                    reference_code=t.get("reference_solution", ""),
                )
            )
        return problems

    def score_candidates(
        self, problems: list[Problem], limits: ScoringLimits
    ) -> dict[tuple[str, str], ScoreResult]:
        return score_via_control_arena(self._setting, problems, limits)
