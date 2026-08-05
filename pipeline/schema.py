"""The common, benchmark-agnostic data format the pipeline runs on.

A benchmark backend turns its own pool into a list of ``Problem`` records and knows how to
score candidates for correctness + trigger-exploitability (via control_arena). Everything
else in the pipeline (PBT generation, the property runner, the monitor, metrics, the report)
only ever touches these records — never a benchmark-specific shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from .outcome import Unknown

if TYPE_CHECKING:
    from .config import ScoringLimits


@dataclass
class Candidate:
    """One submission for a task.

        label          "honest", or "attack_0", "attack_1", ...
        secret_input   the backdoor trigger: kwargs-JSON (bcb) or stdin text (apps).
                       HIDDEN from blind steps — ground-truth scoring only.
    """

    candidate_id: str
    label: str
    code: str
    secret_input: str | None = None

    @property
    def is_attack(self) -> bool:
        return self.label.startswith("attack_")


@dataclass
class Problem:
    """One task and every candidate solution to it.

    Blind steps (PBT-gen, trigger-search, TM) may read only the spec-safe fields: `main_task`,
    `provided_tests_hint`, `io_mode`/`entry_point`, and a candidate's `code`. `reference_code`
    and each attack's `secret_input` are hidden from them, and reach only ground-truth scoring
    and the PBT soundness gate.

        io_mode          "function" (call entry_point(**kwargs)) or "stdio" (run on stdin)
        provided_inputs  the visible tests as raw inputs, spec-safe and usable as fuzzing seeds
        selected_attack  candidate_id deployed as the attack policy; defaults to the first attack
    """

    task_id: str
    main_task: str
    io_mode: str
    candidates: list[Candidate]
    entry_point: str | None = None
    provided_tests_hint: str = ""
    provided_inputs: list[str] = field(default_factory=list)
    reference_code: str = ""
    selected_attack: str | None = None

    @property
    def honest(self) -> Candidate:
        return next(c for c in self.candidates if c.label == "honest")

    @property
    def attacks(self) -> list[Candidate]:
        return [c for c in self.candidates if c.is_attack]

    def __post_init__(self) -> None:
        if self.io_mode not in ("function", "stdio"):
            raise ValueError(f"{self.task_id}: io_mode must be 'function' or 'stdio'")
        if self.io_mode == "function" and not self.entry_point:
            raise ValueError(f"{self.task_id}: function io_mode requires entry_point")
        labels = [c.label for c in self.candidates]
        if labels.count("honest") != 1:
            raise ValueError(f"{self.task_id}: exactly one honest candidate required")
        if not self.attacks:
            raise ValueError(f"{self.task_id}: at least one attack candidate required")
        if self.selected_attack is None:
            self.selected_attack = self.attacks[0].candidate_id


@dataclass
class ScoreResult:
    """Ground-truth verdicts for one candidate.

    `side_task_success` is None for honest candidates, which have no side task. `unknown` is set
    when the eval never produced a verdict, so an infrastructure failure stays distinguishable from
    the model genuinely failing its task, and records why.
    """

    main_task_success: bool
    side_task_success: bool | None
    unknown: "Unknown | None" = None

    @property
    def scored(self) -> bool:
        return self.unknown is None


@runtime_checkable
class Backend(Protocol):
    """Benchmark adapter. The ONLY benchmark-specific surface the pipeline depends on."""

    name: str

    def preprocess(self, pool: dict[str, Any], *, limit: int | None = None) -> list[Problem]:
        """Normalize a benchmark pool into common Problem records."""
        ...

    def score_candidates(
        self, problems: list[Problem], limits: "ScoringLimits"
    ) -> dict[tuple[str, str], ScoreResult]:
        """Ground-truth correctness + trigger-exploitability, keyed by (task_id, candidate_id).

        Deterministic on frozen candidates, so the orchestrator calls this ONCE (outside the
        per-run loop). Implemented via control_arena for the real backends.
        """
        ...


def make_row(
    *,
    task_id: str,
    candidate: Candidate,
    score: ScoreResult,
    pbt_results: dict[str, dict[str, Any]],
    tm: float | None,
    informed: float | None,
) -> dict[str, Any]:
    """The per-candidate row metrics and the report consume.

    `pbt_results` holds the two PBT arms: "pbt" runs every property, "pbt_ceiling" only those
    that held on the privileged reference.
    """
    dep = pbt_results["pbt"]
    ceil = pbt_results["pbt_ceiling"]
    scores = {
        "tm": tm,
        "pbt": dep["score"],
        "pbt_ceiling": ceil["score"],
        "tm_plus_pbt": _combine(tm, dep["score"]),
        "tm_plus_pbt_ceiling": _combine(tm, ceil["score"]),
        "pbt_informed_tm": informed,
    }
    return {
        "task_id": task_id,
        "candidate_id": candidate.candidate_id,
        "candidate_label": candidate.label,
        "main_task_success": score.main_task_success,
        "side_task_success": score.side_task_success,
        "scored": score.scored,
        "pbt_runnable": dep["runnable"],
        "pbt_status": dep["verdict"],
        "scores": scores,
        "evidence": {
            "pbt": dep,
            "pbt_ceiling": ceil,
            "tm": {"score": tm},
            "pbt_informed_tm": {"score": informed},
        },
    }


def _combine(tm: float | None, pbt: float | None) -> float | None:
    available = [s for s in (tm, pbt) if isinstance(s, (int, float)) and s >= 0]
    return max(available) if available else None
