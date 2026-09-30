"""The Docker hard-timeout boundary must clean up on Windows without POSIX APIs."""

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

from pipeline import sandbox


def test_windows_timeout_kills_container_then_cli_and_preserves_partial_grid(monkeypatch):
    events = []
    monkeypatch.setattr(sandbox, "os", SimpleNamespace(name="nt", environ=os.environ))

    class DockerCli:
        pid = 12345
        returncode = None

        def __init__(self, command, **kwargs):
            assert command[:2] == ["docker", "run"]
            self.container = command[command.index("--name") + 1]
            self.communications = 0
            result = Path(kwargs["cwd"]) / sandbox.RESULT_FILENAME
            result.write_text(json.dumps({"props": ["test_value"], "bare_run_ok": None})
                              + "\n" + json.dumps({"prop": "test_value", "i": 0,
                                                    "outcome": "pass"}) + "\n")

        def communicate(self, timeout):
            self.communications += 1
            if self.communications == 1:
                raise subprocess.TimeoutExpired("docker", timeout)
            events.append("drain")
            return "", ""

        def kill(self):
            events.append("kill_cli")

        def wait(self, timeout):
            events.append("wait_cli")
            return 1

    def kill_container(command, **kwargs):
        assert command[:2] == ["docker", "kill"]
        assert command[2].startswith("pbt-")
        assert kwargs["timeout"] == 20
        events.append("kill_container")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(sandbox.subprocess, "Popen", DockerCli)
    monkeypatch.setattr(sandbox.subprocess, "run", kill_container)
    task = SimpleNamespace(io_mode="function", entry_point="solve")
    result = sandbox.run_raw(task, "def solve(a): return a", "def test_value(run, x): pass",
                             [{"a": 1}, {"a": 2}], timeout_s=1,
                             isolation=sandbox.Isolation.DOCKER, docker_image="offline-image")
    assert events == ["kill_container", "kill_cli", "wait_cli", "drain"]
    assert result["ok"] is True
    assert result["complete"] is False
    assert result["n_records"] == 1 and result["n_expected"] == 2
    assert "killed after" in result["error"]


def test_posix_cleanup_still_kills_the_process_group(monkeypatch):
    events = []
    monkeypatch.setattr(sandbox, "os", SimpleNamespace(
        name="posix", getpgid=lambda pid: pid + 10,
        killpg=lambda pgid, sig: events.append((pgid, sig))))
    monkeypatch.setattr(sandbox, "signal", SimpleNamespace(SIGKILL=9))
    process = SimpleNamespace(pid=20, wait=lambda timeout: events.append(("wait", timeout)))
    sandbox.kill_group(process)
    assert events == [(30, 9), ("wait", 5)]
