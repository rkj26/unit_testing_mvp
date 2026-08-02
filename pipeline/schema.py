"""The common, benchmark-agnostic data format the pipeline runs on.

A benchmark backend turns its own pool into a list of ``Problem`` records and knows how to
score candidates for correctness + trigger-exploitability (via control_arena). Everything
else in the pipeline (PBT generation, the property runner, the monitor, metrics, the report)
only ever touches these records — never a benchmark-specific shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


# Blind steps (PBT-gen, trigger-search, TM) may only read the SPEC-safe fields of a Problem:
# ``main_task`` (+ ``provided_tests_hint``), ``io_mode``/``entry_point``, and a candidate's
# ``code`` (for TM). The HIDDEN fields — ``reference_code`` and each attack's ``secret_input`` —
# are used only by control_arena's ground-truth scoring and by the PBT soundness gate.
BLIND_SAFE_FIELDS = ("task_id", "main_task", "io_mode", "entry_point", "provided_tests_hint")


@dataclass
class Candidate:
    candidate_id: str
    label: str  # "honest" | "attack_0" | "attack_1" | ...
    code: str
    secret_input: str | None = None  # HIDDEN from blind steps; kwargs-JSON (bcb) or stdin (apps)

    @property
    def is_attack(self) -> bool:
        return self.label.startswith("attack_")


@dataclass
class Problem:
    task_id: str
    main_task: str  # spec/description shown to the trusted model (blind-safe)
    io_mode: str  # "function" (call entry_point(**kwargs)) | "stdio" (run program on stdin)
    candidates: list[Candidate]
    entry_point: str | None = None  # function name, io_mode="function" only
    provided_tests_hint: str = ""  # a few example I/O for the prompt (blind-safe)
    reference_code: str = ""  # HIDDEN correct solution; soundness gate only
    selected_attack: str | None = None  # candidate_id used as the deployed attack policy

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


# What a backend hands back for each candidate: control_arena's ground-truth verdicts.
# side_task_success is None for honest candidates.
@dataclass
class ScoreResult:
    main_task_success: bool
    side_task_success: bool | None


@runtime_checkable
class Backend(Protocol):
    """Benchmark adapter. The ONLY benchmark-specific surface the pipeline depends on."""

    name: str  # "bcb" | "apps" | "mock"

    def preprocess(self, pool: dict[str, Any], *, limit: int | None = None) -> list[Problem]:
        """Normalize a benchmark pool into common Problem records."""
        ...

    def score_candidates(
        self, problems: list[Problem]
    ) -> dict[tuple[str, str], ScoreResult]:
        """Ground-truth correctness + trigger-exploitability, keyed by (task_id, candidate_id).

        Deterministic on frozen candidates, so the orchestrator calls this ONCE (outside the
        per-run loop). Implemented via control_arena for the real backends.
        """
        ...


# The per-candidate row the metrics + report consume. Kept identical to the legacy schema so
# metrics.py needs no shape changes.
def make_row(
    *,
    task_id: str,
    candidate: Candidate,
    score: ScoreResult,
    pbt_results: dict[str, dict[str, Any]],  # {"pbt": ungated/deployable, "pbt_ceiling": reference-gated}
    tm: float | None,
    informed: float | None,
) -> dict[str, Any]:
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
        "pbt_runnable": dep["runnable"],  # deployable arm's runnability
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
