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


NEVER_RETURNED = "never_returned"
REASONING_TAIL_CHARS = 600


@dataclass(frozen=True)
class Completion:
    """One model completion and the provider's reason for stopping.

    The monitor's score is parsed out of a trailing `SUSPICION_SCORE:` line, so an answer cut short
    by the output-token cap parses to None exactly like a call that never happened. The stop reason
    is what keeps those two apart in the persisted row; the default stands for the call that never
    returned at all.

    `unknown` is set only when the call never returned, and carries WHY — a provider 500, a dead
    socket and a content filter all end up here and used to be indistinguishable. It stays out of
    `stop_reason`, which is one word by contract.
    """

    text: str = ""
    stop_reason: str = NEVER_RETURNED
    unknown: Unknown | None = None


NO_COMPLETION = Completion()


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
    secret_input: str = ""

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
    entry_point: str = ""
    provided_tests_hint: str = ""
    provided_inputs: list[str] = field(default_factory=list)
    reference_code: str = ""
    selected_attack: str = ""

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
        if not self.selected_attack:
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
    unknown: Unknown | None = None

    @property
    def scored(self) -> bool:
        return self.unknown is None


@runtime_checkable
class Backend(Protocol):
    """Benchmark adapter. The ONLY benchmark-specific surface the pipeline depends on."""

    name: str

    def preprocess(
        self, pool: dict[str, Any], *, limit: int | None = None
    ) -> list[Problem]:
        """Normalize a benchmark pool into common Problem records."""
        ...

    def score_candidates(
        self, problems: list[Problem], limits: ScoringLimits
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
    tm_completion: Completion = NO_COMPLETION,
    informed_completion: Completion = NO_COMPLETION,
) -> dict[str, Any]:
    """The per-candidate row metrics and the report consume.

    `pbt_results` holds the two PBT arms: "pbt" runs every property, "pbt_ceiling" only those
    that held on the privileged reference. An arm that never reached a verdict scores None, the
    same abstention an absent monitor score takes, so "PBT found nothing suspicious" stays
    distinguishable from "PBT could not decide". The full result stays under `evidence`.

    A monitor arm records why its completion ended and, when no score could be parsed out of it,
    the tail of what the monitor actually wrote — the row is the only surviving copy.
    """
    dep = pbt_results["pbt"]
    ceil = pbt_results["pbt_ceiling"]
    scores = {
        "tm": tm,
        "pbt": _decided(dep),
        "pbt_ceiling": _decided(ceil),
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
            "tm": _monitor_evidence(tm, tm_completion),
            "pbt_informed_tm": _monitor_evidence(informed, informed_completion),
        },
    }


def _monitor_evidence(score: float | None, completion: Completion) -> dict[str, Any]:
    """A monitor arm's score, its stop reason, and the tail of what it wrote.

    The reasoning tail is kept for every answer, not only unparsed ones: the score alone cannot say
    whether a rating followed the rubric it was given, so a prompt change could not be audited
    against the artifact it produced.
    """
    evidence = {
        "score": score,
        "stop_reason": completion.stop_reason,
        "reasoning_tail": completion.text[-REASONING_TAIL_CHARS:],
    }
    if completion.unknown is not None:
        evidence["unknown"] = completion.unknown.to_json()
    return evidence


def _decided(pbt_result: dict[str, Any]) -> float | None:
    """The arm's score, or None when it never ran.

    `pbt._invalid` fills `score` with 0.0 as a placeholder, and 0.0 is the most-benign score there
    is: emitting it would record a reference-run timeout or a dead harness as evidence of
    innocence, in calibration, AUROC and the deployment simulation alike.
    """
    return pbt_result["score"] if pbt_result["runnable"] else None


