"""Typed artifact store — the explicit dataflow + resume layer.

Every value that flows between pipeline steps is an *artifact* addressed by an `ArtifactKind` plus its
coordinates (`run` index, `task_id`). `ArtifactStore` is a thin, typed facade over the on-disk
checkpoint functions in `state.py`: `has` powers resume (skip a step whose output already exists),
`load` feeds a step its inputs, and `put`/`append` persist a step's output. Keeping this behind one
object lets the engine move data around declaratively — `store.put(step.produces, value, run=r,
task_id=t)` — without knowing which JSON file backs each kind.

Public surface (top): `ArtifactKind`, `ArtifactStore` and its `has`/`load`/`put`/`append`/`status`.
Private dispatch details are at the bottom.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from . import state


class ArtifactKind(str, Enum):
    """The kinds of artifact that flow between steps (and their coordinates).

    PROBLEMS     list[Problem] for the whole run          (no coords)      — from preprocess
    SCORES       {(task_id,candidate_id): ScoreResult}    (no coords)      — from ground-truth scoring
    SUITE        per-task PBT suite dict (meta+results)    (run, task_id)   — from the pbt step
    ROWS         per-candidate monitor rows (append-log)   (run)            — from the monitor step
    RUN_METRICS  a completed run's (rows, metrics) pair    (run)            — the run-done marker
    """

    PROBLEMS = "problems"
    SCORES = "scores"
    SUITE = "suite"
    ROWS = "rows"
    RUN_METRICS = "run_metrics"


class ArtifactStore:
    """Typed, run-scoped facade over `state.py` for reading/writing pipeline artifacts.

    Bound to one `runs/<run_id>/` directory. All persistence is atomic (see `state.atomic_write`), so a
    kill never leaves a half-written artifact.
    """

    def __init__(self, run_dir: Path | str) -> None:
        """Bind the store to a run directory (created on demand by the underlying writers)."""
        self.run_dir = Path(run_dir)
        self._status: "state.Status | None" = None

    def has(self, kind: ArtifactKind, *, run: int | None = None, task_id: str | None = None) -> bool:
        """Return True if the artifact already exists on disk — the resume check (skip when present)."""
        if kind is ArtifactKind.PROBLEMS:
            return state.load_problems(self.run_dir) is not None
        if kind is ArtifactKind.SCORES:
            return state.load_scores(self.run_dir) is not None
        if kind is ArtifactKind.SUITE:
            suite = state.load_suite(self.run_dir, _req(run), _req(task_id))
            return bool(suite and "meta" in suite and "results" in suite)
        if kind is ArtifactKind.RUN_METRICS:
            return state.is_run_done(self.run_dir, _req(run))
        raise ValueError(f"has() unsupported for {kind}")

    def load(self, kind: ArtifactKind, *, run: int | None = None, task_id: str | None = None) -> Any:
        """Load an artifact's value (feeds a step its inputs). Shapes mirror `state.py`.

        RUN_METRICS returns the `(rows, metrics)` tuple; ROWS returns the per-run row list (possibly
        empty); the rest return their stored object, or None/[] when absent.
        """
        if kind is ArtifactKind.PROBLEMS:
            return state.load_problems(self.run_dir)
        if kind is ArtifactKind.SCORES:
            return state.load_scores(self.run_dir)
        if kind is ArtifactKind.SUITE:
            return state.load_suite(self.run_dir, _req(run), _req(task_id))
        if kind is ArtifactKind.ROWS:
            return state.load_rows(self.run_dir, _req(run))
        if kind is ArtifactKind.RUN_METRICS:
            return state.load_run_complete(self.run_dir, _req(run))
        raise ValueError(f"load() unsupported for {kind}")

    def put(self, kind: ArtifactKind, value: Any, *, run: int | None = None,
            task_id: str | None = None) -> None:
        """Persist a step's output artifact (the durable checkpoint).

        SUITE also writes the human-readable mirror. RUN_METRICS takes a `(rows, metrics)` pair and
        writes metrics.json LAST, so its presence is the atomic "run complete" marker.
        """
        if kind is ArtifactKind.PROBLEMS:
            state.save_problems(self.run_dir, value)
        elif kind is ArtifactKind.SCORES:
            state.save_scores(self.run_dir, value)
        elif kind is ArtifactKind.SUITE:
            state.save_suite(self.run_dir, _req(run), _req(task_id), value)
            state.write_pbt_readable(self.run_dir, _req(run), _req(task_id), value)
        elif kind is ArtifactKind.RUN_METRICS:
            rows, metrics = value
            state.save_run_complete(self.run_dir, _req(run), rows, metrics)
        else:
            raise ValueError(f"put() unsupported for {kind}")

    def append(self, kind: ArtifactKind, value: Any, *, run: int | None = None) -> None:
        """Append one record to an append-log artifact (ROWS: write-ahead one monitor row per line)."""
        if kind is ArtifactKind.ROWS:
            state.append_row(self.run_dir, _req(run), value)
        else:
            raise ValueError(f"append() unsupported for {kind}")

    def status(self) -> "state.Status":
        """Return the ONE live `Status` writer for this run (status.json phase + heartbeat).

        Memoized per store: every caller shares a single in-memory state, so a `set(phase=...)` and a
        later `beat()` accumulate on the same dict. (Constructing a fresh `Status` each call would reset
        it to `phase="init"`, silently wiping the phase/progress the dashboard reads.)
        """
        if self._status is None:
            self._status = state.Status(self.run_dir)
        return self._status


# --------------------------------------------------------------------------- #
# private helpers
# --------------------------------------------------------------------------- #
def _req(coord: Any) -> Any:
    """Assert a required coordinate (run / task_id) was supplied, returning it; raise otherwise."""
    if coord is None:
        raise ValueError("missing required coordinate (run/task_id) for this artifact kind")
    return coord
