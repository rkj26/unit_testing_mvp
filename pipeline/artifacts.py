"""Typed artifact store — the explicit dataflow, resume and live-status layer.

Every value that flows between pipeline steps is an *artifact* addressed by an `ArtifactKind` plus
its coordinates (`run` index, `task_id`). `has` powers resume (skip a step whose output already
exists), `load` feeds a step its inputs, and `put`/`append` persist a step's output, so the engine
moves data around declaratively without knowing which JSON file backs each kind.

Everything the flaky model phase produces is written as it happens, so a kill or hang costs at most
one in-flight call and re-running with the same ``--run-id`` resumes where it stopped. All writes go
through `atomic_write`, so a kill never leaves a half-written artifact.

Layout under ``runs/<run_id>/``::

    run.json      config manifest (written up front, before any expensive work)
    status.json   live phase/counts/heartbeat — glance here to tell "hung" from "slow"
    problems.json serialized Problem list (lets the monitor stage run standalone / resume)
    scores.json   ground-truth verdicts (deterministic + expensive -> written once, reloaded)
    run_<r>/
      pbt/<task>/suite.json           per-task PBT checkpoint {props_src, space, meta, results}
      pbt/<task>/{properties.py,...}  human-readable mirror (debugging)
      rows.jsonl                      one monitor row per line, appended as each candidate finishes
      rows.json                       full row list, written at run completion
      metrics.json                    present IFF the run completed (its existence = "skip on resume")

Public surface: `ArtifactKind`, `ArtifactStore`, `Status`, and the `read_json`/`write_json` pair
that callers outside the store (the worker rebuilding Config, the progress dashboard) still need.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .outcome import Unknown
from .schema import Candidate, Problem, ScoreResult


def atomic_write(path: Path, text: str) -> None:
    """Write via a temp file + os.replace so a kill mid-write never corrupts an existing file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def write_json(path: Path, obj: Any) -> None:
    atomic_write(path, json.dumps(obj, indent=2, sort_keys=True))


def read_json(path: Path) -> Any:
    """Parsed JSON, or None when the file is absent or torn by a mid-write kill."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


class ArtifactKind(str, Enum):
    """The kinds of artifact that flow between steps, and their coordinates.

    PROBLEMS     list[Problem] for the whole run           (no coords)     — from preprocess
    SCORES       {(task_id,candidate_id): ScoreResult}     (no coords)     — from ground-truth scoring
    SUITE        per-task PBT suite dict (meta+results)    (run, task_id)  — from the pbt step
    ROWS         per-candidate monitor rows (append-log)   (run)           — from the monitor step
    RUN_METRICS  a completed run's (rows, metrics) pair    (run)           — the run-done marker
    """

    PROBLEMS = "problems"
    SCORES = "scores"
    SUITE = "suite"
    ROWS = "rows"
    RUN_METRICS = "run_metrics"


class Status:
    """Atomic status.json writer.

    `set()` records a phase transition, `beat()` just refreshes the heartbeat so an observer can
    tell a live-but-busy run from a wedged one.
    """

    def __init__(self, run_dir: Path):
        self.path = run_dir / "status.json"
        self.state: dict[str, Any] = {
            "pid": os.getpid(), "phase": "init",
            "started_at": _now(), "updated_at": _now(), "heartbeat_at": _now(),
        }
        self._flush()

    def set(self, **kw: Any) -> None:
        self.state.update(kw)
        self.state["updated_at"] = _now()
        self.state["heartbeat_at"] = _now()
        self._flush()

    def beat(self, **kw: Any) -> None:
        self.state.update(kw)
        self.state["heartbeat_at"] = _now()
        self._flush()

    def _flush(self) -> None:
        try:
            write_json(self.path, self.state)
        except OSError:
            pass


class ArtifactStore:
    """Typed, run-scoped reader/writer for pipeline artifacts, bound to one `runs/<run_id>/`."""

    def __init__(self, run_dir: Path | str) -> None:
        self.run_dir = Path(run_dir)
        self._status: Status | None = None

    def has(self, kind: ArtifactKind, *, run: int | None = None, task_id: str | None = None) -> bool:
        """Whether the artifact already exists — the resume check (skip when present)."""
        if kind is ArtifactKind.PROBLEMS:
            return read_json(self._problems_path) is not None
        if kind is ArtifactKind.SCORES:
            return read_json(self._scores_path) is not None
        if kind is ArtifactKind.SUITE:
            suite = self.load(kind, run=run, task_id=task_id)
            return bool(suite and "meta" in suite and "results" in suite)
        if kind is ArtifactKind.RUN_METRICS:
            return self._metrics_path(_req(run)).exists()
        raise ValueError(f"has() unsupported for {kind}")

    def load(self, kind: ArtifactKind, *, run: int | None = None, task_id: str | None = None) -> Any:
        """Load an artifact's value. RUN_METRICS returns a `(rows, metrics)` pair."""
        if kind is ArtifactKind.PROBLEMS:
            return _problems_from_json(read_json(self._problems_path))
        if kind is ArtifactKind.SCORES:
            return _scores_from_json(read_json(self._scores_path))
        if kind is ArtifactKind.SUITE:
            return read_json(self._suite_path(_req(run), _req(task_id)))
        if kind is ArtifactKind.ROWS:
            return _read_jsonl(self._rows_log_path(_req(run)))
        if kind is ArtifactKind.RUN_METRICS:
            return (read_json(self._rows_path(_req(run))), read_json(self._metrics_path(_req(run))))
        raise ValueError(f"load() unsupported for {kind}")

    def put(self, kind: ArtifactKind, value: Any, *, run: int | None = None,
            task_id: str | None = None) -> None:
        """Persist a step's output. RUN_METRICS writes metrics.json LAST, as the completion marker."""
        if kind is ArtifactKind.PROBLEMS:
            write_json(self._problems_path, [_problem_to_json(p) for p in value])
        elif kind is ArtifactKind.SCORES:
            write_json(self._scores_path, _scores_to_json(value))
        elif kind is ArtifactKind.SUITE:
            path = self._suite_path(_req(run), _req(task_id))
            write_json(path, value)
            _write_readable_suite(path.parent, value)
        elif kind is ArtifactKind.RUN_METRICS:
            rows, metrics = value
            write_json(self._rows_path(_req(run)), rows)
            write_json(self._metrics_path(_req(run)), metrics)
        else:
            raise ValueError(f"put() unsupported for {kind}")

    def append(self, kind: ArtifactKind, value: Any, *, run: int | None = None) -> None:
        """Append one record to an append-log artifact (ROWS: one monitor row per line)."""
        if kind is not ArtifactKind.ROWS:
            raise ValueError(f"append() unsupported for {kind}")
        path = self._rows_log_path(_req(run))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value, sort_keys=True) + "\n")

    def status(self) -> Status:
        """The ONE live Status writer for this run, memoized so phase and heartbeat accumulate."""
        if self._status is None:
            self._status = Status(self.run_dir)
        return self._status

    @property
    def _problems_path(self) -> Path:
        return self.run_dir / "problems.json"

    @property
    def _scores_path(self) -> Path:
        return self.run_dir / "scores.json"

    def _suite_path(self, run: int, task_id: str) -> Path:
        return self.run_dir / f"run_{run}" / "pbt" / task_id.replace("/", "_") / "suite.json"

    def _rows_log_path(self, run: int) -> Path:
        return self.run_dir / f"run_{run}" / "rows.jsonl"

    def _rows_path(self, run: int) -> Path:
        return self.run_dir / f"run_{run}" / "rows.json"

    def _metrics_path(self, run: int) -> Path:
        return self.run_dir / f"run_{run}" / "metrics.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _req(coord: Any) -> Any:
    if coord is None:
        raise ValueError("missing required coordinate (run/task_id) for this artifact kind")
    return coord


def _problem_to_json(p: Problem) -> dict[str, Any]:
    return {
        "task_id": p.task_id, "main_task": p.main_task, "io_mode": p.io_mode,
        "entry_point": p.entry_point, "provided_tests_hint": p.provided_tests_hint,
        "provided_inputs": p.provided_inputs,
        "reference_code": p.reference_code, "selected_attack": p.selected_attack,
        "candidates": [
            {"candidate_id": c.candidate_id, "label": c.label, "code": c.code,
             "secret_input": c.secret_input}
            for c in p.candidates
        ],
    }


def _problems_from_json(data: Any) -> list[Problem] | None:
    if not data:
        return None
    return [
        Problem(
            task_id=d["task_id"], main_task=d["main_task"], io_mode=d["io_mode"],
            candidates=[Candidate(**c) for c in d["candidates"]],
            entry_point=d.get("entry_point"),
            provided_tests_hint=d.get("provided_tests_hint", ""),
            provided_inputs=list(d.get("provided_inputs") or []),
            reference_code=d.get("reference_code", ""), selected_attack=d.get("selected_attack"),
        )
        for d in data
    ]


def _scores_to_json(scores: dict[tuple[str, str], ScoreResult]) -> list[dict[str, Any]]:
    return [
        {"task_id": t, "candidate_id": c, "main_task_success": r.main_task_success,
         "side_task_success": r.side_task_success,
         "unknown": r.unknown.to_json() if r.unknown is not None else None}
        for (t, c), r in sorted(scores.items())
    ]


def _scores_from_json(data: Any) -> dict[tuple[str, str], ScoreResult] | None:
    if data is None:
        return None
    return {
        (d["task_id"], d["candidate_id"]): ScoreResult(
            d["main_task_success"], d["side_task_success"],
            Unknown.from_json(d["unknown"]) if d.get("unknown") else None)
        for d in data
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Rows from an append-log, tolerating a torn final line from a mid-write kill."""
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def _write_readable_suite(directory: Path, suite: dict[str, Any]) -> None:
    """Human-readable mirror of a suite checkpoint, for debugging a run after the fact."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "properties.py").write_text(
        suite.get("props_src") or f"# no valid properties\n# {suite.get('prop_err')}\n",
        encoding="utf-8")
    (directory / "search_space.json").write_text(
        json.dumps(suite.get("space") or [], indent=2), encoding="utf-8")
    (directory / "meta.json").write_text(
        json.dumps(suite.get("meta") or {}, indent=2, sort_keys=True), encoding="utf-8")
    if suite.get("props_src") is None:
        (directory / "prop_completion_raw.txt").write_text(suite.get("prop_raw") or "", encoding="utf-8")
    if suite.get("space") is None:
        (directory / "search_completion_raw.txt").write_text(suite.get("space_raw") or "", encoding="utf-8")
