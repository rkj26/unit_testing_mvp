"""Windows detached-launch checks; no provider or coordinator is started."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from pipeline.protocols import omar_runtime, omar_shared


def test_windows_coordinator_is_detached_logged_and_pid_guarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(omar_shared.os, "name", "nt")
    monkeypatch.setattr(omar_shared, "_windows_process_alive", lambda _pid: True)
    monkeypatch.setattr(omar_shared.subprocess, "DETACHED_PROCESS", 0x00000008, raising=False)
    monkeypatch.setattr(omar_shared.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200,
                        raising=False)
    calls: list[dict[str, object]] = []

    class Process:
        pid = 43210

    def fake_popen(argv: list[str], **kwargs: object) -> Process:
        calls.append({"argv": argv, **kwargs})
        return Process()

    monkeypatch.setattr(omar_shared.subprocess, "Popen", fake_popen)
    omar_shared._launch_windows_coordinator("demo-coordinator", ["python", "runner.py"])

    folder = tmp_path / "runs" / "demo-coordinator"
    assert (folder / "coordinator.pid").read_text() == "43210\n"
    assert (folder / "console.log").is_file()
    assert (folder / "coordinator.launching").read_bytes() == omar_runtime.LAUNCH_GUARD_MARKER
    assert calls[0]["creationflags"] == (0x00000008 | 0x00000200)
    assert calls[0]["stdout"].closed
    assert calls[0]["stderr"] is omar_shared.subprocess.STDOUT
    with pytest.raises(RuntimeError, match="already running"):
        omar_shared._launch_windows_coordinator("demo-coordinator", ["python", "runner.py"])
    assert len(calls) == 1


def test_windows_coordinator_refuses_a_concurrent_launch_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(omar_shared.os, "name", "nt")
    folder = tmp_path / "runs" / "demo-coordinator"
    folder.mkdir(parents=True)
    (folder / "coordinator.launching").touch()
    with pytest.raises(RuntimeError, match="already launching"):
        omar_shared._launch_windows_coordinator("demo-coordinator", ["python", "runner.py"])


@pytest.mark.skipif(omar_shared.os.name != "nt", reason="requires Windows process APIs")
def test_windows_liveness_query_does_not_signal_a_real_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    child = omar_shared.subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"]
    )
    try:
        folder = tmp_path / "runs" / "disposable-sleep"
        folder.mkdir(parents=True)
        (folder / "coordinator.pid").write_text(f"{child.pid}\n", encoding="ascii")

        assert omar_shared._session_alive("disposable-sleep") is True
        time.sleep(0.25)
        assert child.poll() is None, "a liveness query must not terminate its target"
        assert omar_shared._session_alive("disposable-sleep") is True

        child.terminate()
        child.wait(timeout=5)
        assert omar_shared._session_alive("disposable-sleep") is False
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)


def test_inputs_runner_attaches_and_executes_without_base_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeTriggerSearch:
        def __init__(self) -> None:
            self.executed = False

        def execute(self) -> None:
            self.executed = True

        def pending(self):
            return [object()]

    trigger = FakeTriggerSearch()
    monkeypatch.setattr(omar_shared, "TriggerSearch", FakeTriggerSearch)
    monkeypatch.setattr(omar_shared.Run, "attach",
                        classmethod(lambda _cls, _name: trigger))
    monkeypatch.setattr(sys, "argv", ["omar_runner", "--inputs", "fresh-inputs"])
    approved = []
    monkeypatch.setattr(omar_shared, "_verify_input_authorization", lambda arm: approved.append(arm))

    omar_shared.main()
    assert approved == [trigger]

    assert trigger.executed is True
