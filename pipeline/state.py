"""Durable checkpoint + live-status I/O — the backbone of resumable, observable runs.

Everything the flaky model phase produces is written to disk as it happens, so a kill/hang costs
at most one in-flight call and re-running with the same ``--run-id`` resumes where it stopped.

Layout under ``runs/<run_id>/``::

    run.json      config manifest (written up front, before any expensive work)
    status.json   live phase/counts/heartbeat — glance here to tell "hung" from "slow"
    problems.json serialized Problem list (lets the monitor stage run standalone / resume)
    scores.json   ground-truth verdicts (deterministic + expensive -> written once, reloaded on resume)
    run_<r>/
      pbt/<task>/suite.json           per-task PBT checkpoint {props_src, space, meta, results}
      pbt/<task>/{properties.py,...}  human-readable mirror (debugging)
      rows.jsonl                      one monitor row per line, appended as each candidate finishes
      rows.json                       full row list, written at run completion
      metrics.json                    present IFF the run completed (its existence = "skip on resume")
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema import Candidate, Problem, ScoreResult


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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


def read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# --------------------------------------------------------------------------- #
# Problem + ground-truth score (de)serialization
# --------------------------------------------------------------------------- #
def _cand_to_dict(c: Candidate) -> dict[str, Any]:
    return {"candidate_id": c.candidate_id, "label": c.label, "code": c.code,
            "secret_input": c.secret_input}


def _prob_to_dict(p: Problem) -> dict[str, Any]:
    return {
        "task_id": p.task_id, "main_task": p.main_task, "io_mode": p.io_mode,
        "entry_point": p.entry_point, "provided_tests_hint": p.provided_tests_hint,
        "reference_code": p.reference_code, "selected_attack": p.selected_attack,
        "candidates": [_cand_to_dict(c) for c in p.candidates],
    }


def save_problems(run_dir: Path, problems: list[Problem]) -> None:
    write_json(run_dir / "problems.json", [_prob_to_dict(p) for p in problems])


def load_problems(run_dir: Path) -> list[Problem] | None:
    data = read_json(run_dir / "problems.json")
    if not data:
        return None
    out: list[Problem] = []
    for d in data:
        cands = [Candidate(**c) for c in d["candidates"]]
        out.append(Problem(
            task_id=d["task_id"], main_task=d["main_task"], io_mode=d["io_mode"],
            candidates=cands, entry_point=d.get("entry_point"),
            provided_tests_hint=d.get("provided_tests_hint", ""),
            reference_code=d.get("reference_code", ""), selected_attack=d.get("selected_attack"),
        ))
    return out


def save_scores(run_dir: Path, scores: dict[tuple[str, str], ScoreResult]) -> None:
    rows = [
        {"task_id": t, "candidate_id": c, "main_task_success": r.main_task_success,
         "side_task_success": r.side_task_success}
        for (t, c), r in sorted(scores.items())
    ]
    write_json(run_dir / "scores.json", rows)


def load_scores(run_dir: Path) -> dict[tuple[str, str], ScoreResult] | None:
    data = read_json(run_dir / "scores.json")
    if data is None:
        return None
    return {
        (d["task_id"], d["candidate_id"]): ScoreResult(d["main_task_success"], d["side_task_success"])
        for d in data
    }


# --------------------------------------------------------------------------- #
# per-run PBT suite checkpoint (resume unit for gen + eval)
# --------------------------------------------------------------------------- #
def _task_dir(run_dir: Path, r: int, task_id: str) -> Path:
    return run_dir / f"run_{r}" / "pbt" / task_id.replace("/", "_")


def save_suite(run_dir: Path, r: int, task_id: str, suite: dict[str, Any]) -> None:
    write_json(_task_dir(run_dir, r, task_id) / "suite.json", suite)


def load_suite(run_dir: Path, r: int, task_id: str) -> dict[str, Any] | None:
    return read_json(_task_dir(run_dir, r, task_id) / "suite.json")


def write_pbt_readable(run_dir: Path, r: int, task_id: str, suite: dict[str, Any]) -> None:
    """Human-readable mirror of a suite checkpoint (properties.py / search_space.json / meta.json)."""
    d = _task_dir(run_dir, r, task_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "properties.py").write_text(
        suite.get("props_src") or f"# no valid properties\n# {suite.get('prop_err')}\n", encoding="utf-8")
    (d / "search_space.json").write_text(json.dumps(suite.get("space") or [], indent=2), encoding="utf-8")
    (d / "meta.json").write_text(json.dumps(suite.get("meta") or {}, indent=2, sort_keys=True), encoding="utf-8")
    if suite.get("props_src") is None:
        (d / "prop_completion_raw.txt").write_text(suite.get("prop_raw") or "", encoding="utf-8")
    if suite.get("space") is None:
        (d / "search_completion_raw.txt").write_text(suite.get("space_raw") or "", encoding="utf-8")


# --------------------------------------------------------------------------- #
# per-run monitor rows (write-ahead log)
# --------------------------------------------------------------------------- #
def append_row(run_dir: Path, r: int, row: dict[str, Any]) -> None:
    p = run_dir / f"run_{r}" / "rows.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def load_rows(run_dir: Path, r: int) -> list[dict[str, Any]]:
    p = run_dir / f"run_{r}" / "rows.jsonl"
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass  # tolerate a torn final line from a mid-write kill; that candidate just re-runs
    return out


# --------------------------------------------------------------------------- #
# run completion (metrics.json presence == run done)
# --------------------------------------------------------------------------- #
def is_run_done(run_dir: Path, r: int) -> bool:
    return (run_dir / f"run_{r}" / "metrics.json").exists()


def save_run_complete(run_dir: Path, r: int, rows: list[dict[str, Any]], metrics: dict[str, Any]) -> None:
    write_json(run_dir / f"run_{r}" / "rows.json", rows)
    write_json(run_dir / f"run_{r}" / "metrics.json", metrics)  # write LAST: its presence marks "done"


def load_run_complete(run_dir: Path, r: int) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
    return (read_json(run_dir / f"run_{r}" / "rows.json"),
            read_json(run_dir / f"run_{r}" / "metrics.json"))


# --------------------------------------------------------------------------- #
# live status file (queryable progress + heartbeat)
# --------------------------------------------------------------------------- #
class Status:
    """Atomic status.json writer. `set()` records a phase transition, `beat()` just refreshes the
    heartbeat so an observer can tell a live-but-busy run from a wedged one."""

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
        if kw:
            self.state.update(kw)
        self.state["heartbeat_at"] = _now()
        self._flush()

    def _flush(self) -> None:
        try:
            write_json(self.path, self.state)
        except OSError:
            pass  # status is best-effort; never let it crash the run
