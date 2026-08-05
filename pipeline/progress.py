"""Optional live progress dashboard (rich), driven entirely by `status.json`.

When enabled, the engine routes its own and the workers' log lines to a file and renders this dashboard
on the terminal instead — so a foreground run shows clean nested bars (overall runs + the active
phase) while a backgrounded / non-TTY run keeps the plain timestamped log. Because it reads only
`status.json` + on-disk artifact counts, it is fully decoupled from execution and works the same for
in-process, subprocess, and Docker runs.

Public surface (top): `ProgressReporter`. Private render helpers are at the bottom.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from .artifacts import ArtifactKind, ArtifactStore, read_json


class ProgressReporter:
    """A context manager that renders a live rich dashboard from `status.json` in a daemon thread.

    Use as `with ProgressReporter(run_dir, runs=N, label=...):`. It polls the run's status + completed
    runs a few times a second; nothing about the engine's execution depends on it.
    """

    def __init__(self, run_dir: Path | str, *, runs: int, label: str) -> None:
        """Bind to a run directory; `runs` sizes the overall bar, `label` heads it (e.g. domain/model)."""
        self.run_dir = Path(run_dir)
        self._store = ArtifactStore(self.run_dir)
        self.runs = runs
        self.label = label
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "ProgressReporter":
        """Start the render thread."""
        self._thread = threading.Thread(target=self._render_loop, daemon=True, name="progress")
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> bool:
        """Stop the render thread and let it paint the final state."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
        return False

    def _render_loop(self) -> None:
        """Render overall-runs + active-phase bars until stopped, refreshing from `status.json`."""
        from rich.progress import (BarColumn, MofNCompleteColumn, Progress, SpinnerColumn,
                                    TextColumn, TimeElapsedColumn)

        columns = [
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None),
            MofNCompleteColumn(),
            TextColumn("[dim]{task.fields[note]}"),
            TimeElapsedColumn(),
        ]
        with Progress(*columns, refresh_per_second=6) as prog:
            runs_task = prog.add_task(self.label, total=max(self.runs, 1), note="")
            phase_task = prog.add_task("starting…", total=None, note="")
            while not self._stop.is_set():
                self._refresh(prog, runs_task, phase_task)
                time.sleep(0.25)
            self._refresh(prog, runs_task, phase_task, final=True)

    def _refresh(self, prog: Any, runs_task: Any, phase_task: Any, *, final: bool = False) -> None:
        """Pull the latest status + completed-run count and update the two bars."""
        done_runs = sum(1 for r in range(self.runs)
                        if self._store.has(ArtifactKind.RUN_METRICS, run=r))
        prog.update(runs_task, completed=done_runs)
        st = read_json(self.run_dir / "status.json") or {}
        phase = st.get("phase", "…")
        run_index = st.get("run_index")
        done, total = st.get("done"), st.get("total")
        desc = f"run {run_index} · {phase}" if run_index is not None else str(phase)
        note = _heartbeat_note(st)
        if final and done_runs >= self.runs:
            prog.update(phase_task, description="done", total=1, completed=1, note="")
        elif total:
            prog.update(phase_task, description=desc, total=total, completed=done or 0, note=note)
        else:
            prog.update(phase_task, description=desc, total=None, note=note)


def _heartbeat_note(status: dict[str, Any]) -> str:
    """A short freshness note (e.g. 'attempt 2' or a stall warning) for the active-phase bar."""
    attempt = status.get("attempt")
    if attempt and attempt > 1:
        return f"attempt {attempt}"
    return ""
