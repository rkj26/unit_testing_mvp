"""Liveness poller and supervisor for a batch of runs. Reads artifacts, never trusts the log.

    .venv/bin/python poll.py b1                    # follow, refreshing every 60s
    .venv/bin/python poll.py b1 --once             # one pass, exit 1 if anything is unhealthy
    .venv/bin/python poll.py b1 --supervise        # follow AND relaunch what has died

Diagnoses in the order CLAUDE.md prescribes: status.json heartbeat, then artifact counts, then the
log. A cell is STALLED when its heartbeat is older than STALL_SECONDS while its tmux session is
still up, and DEAD when the session is gone with runs left to do — the two failures that leave a
batch looking busy while nothing advances.

Under `--supervise` both are relaunched through `run_batch.sh`, which resumes from checkpoint, so
an intervention costs at most one in-flight call. A cell is given up on after MAX_RESTARTS so a
config error cannot become a restart loop.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

STALL_SECONDS = 900
POLL_SECONDS = 60
MAX_RESTARTS = 6
RUNS_DIR = Path("runs")
UNHEALTHY = ("DEAD", "STALLED")


def sessions() -> set[str]:
    out = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}"], capture_output=True, text=True
    )
    return set(out.stdout.split())


def read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def heartbeat_age(status: dict | None) -> float | None:
    if not status or "heartbeat_at" not in status:
        return None
    beat = datetime.fromisoformat(status["heartbeat_at"])
    return (datetime.now(timezone.utc) - beat).total_seconds()


def row_count(run_dir: Path) -> int:
    rows = run_dir / "rows.jsonl"
    if rows.exists():
        return sum(1 for line in rows.read_text().splitlines() if line.strip())
    loaded = read_json(run_dir / "rows.json")
    return len(loaded) if isinstance(loaded, list) else 0


def cell_state(run_id: str, expected_runs: int, live: set[str]) -> dict:
    directory = RUNS_DIR / run_id
    status = read_json(directory / "status.json")
    age = heartbeat_age(status)
    finished = len(list(directory.glob("run_*/metrics.json")))
    current = sorted(directory.glob("run_*"))
    log = Path(f"runs_{run_id}.log")
    text = log.read_text(errors="ignore") if log.exists() else ""

    alive = run_id in live
    if finished >= expected_runs:
        health = "COMPLETE"
    elif not alive:
        health = "DEAD"
    elif age is not None and age > STALL_SECONDS:
        health = "STALLED"
    else:
        health = "ok"

    return {
        "cell": run_id,
        "health": health,
        "runs": f"{finished}/{expected_runs}",
        "phase": (status or {}).get("phase", "-"),
        "suites": len(list(current[-1].glob("pbt/*/meta.json"))) if current else 0,
        "beat": "-" if age is None else f"{age:.0f}s",
        "rows": row_count(current[-1]) if current else 0,
        "warns": text.count("[warn]"),
        "throttle": sum(
            text.lower().count(marker) for marker in ("rate limit", "429", "throttl")
        ),
    }


COLUMNS = ("cell", "health", "runs", "phase", "suites", "beat", "rows", "warns", "throttle")


def load_average() -> str:
    """One-minute load. A batch that wedges the machine shows here before it shows anywhere else."""
    try:
        one, five, fifteen = __import__("os").getloadavg()
        return f"load {one:.0f}/{five:.0f}/{fifteen:.0f}"
    except OSError:
        return "load -"


def render(states: list[dict]) -> str:
    stamp = datetime.now(timezone.utc).strftime("%H:%M:%SZ") + "  " + load_average()
    widths = {c: max(len(c), *(len(str(s[c])) for s in states)) for c in COLUMNS}
    head = "  ".join(c.ljust(widths[c]) for c in COLUMNS)
    body = [
        "  ".join(str(s[c]).ljust(widths[c]) for c in COLUMNS) for s in states
    ]
    bad = [s["cell"] for s in states if s["health"] in ("DEAD", "STALLED")]
    tail = f"\nUNHEALTHY: {', '.join(bad)}" if bad else ""
    return f"[{stamp}]\n{head}\n{'-' * len(head)}\n" + "\n".join(body) + tail


def relaunch(prefix: str, cell_id: str) -> str:
    """Kill whatever is left of a cell and start it again; `run_batch.sh` resumes from checkpoint."""
    suffix = cell_id[len(prefix) + 1 :]
    subprocess.run(["tmux", "kill-session", "-t", cell_id], capture_output=True)
    done = subprocess.run(
        ["bash", "run_batch.sh", suffix], capture_output=True, text=True
    )
    return (done.stdout.strip() or done.stderr.strip() or "no output").splitlines()[-1]


def supervise(states: list[dict], prefix: str, restarts: dict[str, int]) -> list[str]:
    actions = []
    for state in states:
        if state["health"] not in UNHEALTHY:
            continue
        cell = state["cell"]
        if restarts[cell] >= MAX_RESTARTS:
            actions.append(f"GIVING UP on {cell} after {MAX_RESTARTS} restarts")
            continue
        restarts[cell] += 1
        actions.append(
            f"RESTART {cell} ({state['health']}, attempt {restarts[cell]}): "
            f"{relaunch(prefix, cell)}"
        )
    return actions


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    prefix = sys.argv[1]
    once = "--once" in sys.argv
    supervising = "--supervise" in sys.argv
    expected = next(
        (int(a.split("=")[1]) for a in sys.argv if a.startswith("--runs=")), 10
    )
    only = next(
        (a.split("=")[1].split(",") for a in sys.argv if a.startswith("--only=")), []
    )
    supervised = {f"{prefix}-{c}" for c in only}
    restarts: dict[str, int] = {}
    while True:
        live = sessions()
        ids = sorted({p.name for p in RUNS_DIR.glob(f"{prefix}-*")} | {
            s for s in live if s.startswith(f"{prefix}-")
        })
        if not ids:
            print(f"no runs matching {prefix}-*")
            return 1
        states = [cell_state(i, expected, live) for i in ids]
        print(render(states), flush=True)
        unhealthy = any(s["health"] in UNHEALTHY for s in states)
        if supervising and unhealthy:
            for cell in ids:
                restarts.setdefault(cell, 0)
            mine = [s for s in states if not supervised or s["cell"] in supervised]
            for line in supervise(mine, prefix, restarts):
                print(f"  {line}", flush=True)
        if once:
            return 1 if unhealthy else 0
        if all(s["health"] == "COMPLETE" for s in states):
            print("all cells complete", flush=True)
            return 0
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
