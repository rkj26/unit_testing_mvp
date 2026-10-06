import json
import subprocess
from types import SimpleNamespace

import pytest

from pbt_runner import sandbox_bridge as bridge


def _fake_sandbox():
    def stream(text):
        rows = [json.loads(line) for line in text.splitlines()]
        return ({**rows[0], "records": rows[1:]}, "") if rows else (None, "no result file")

    def validated(result, n_space):
        assert all(0 <= row["i"] < n_space for row in result["records"])
        return result["props"], result["records"]

    return SimpleNamespace(
        DOCKER_MEMORY_LIMIT="2g", DOCKER_CPU_LIMIT="2", DOCKER_PID_LIMIT=256,
        HARNESS_FILENAME="harness.py", RESULT_FILENAME="pbt_result.jsonl",
        HARNESS_KILL_GRACE_SECONDS=6, PIPE_DRAIN_SECONDS=5,
        build_harness=lambda *a, **k: "trusted harness source",
        _stream=stream, _validated=validated,
        _validated_bare_run=lambda result, n: result["bare_run_ok"],
        _failed=lambda error: {"ok": False, "complete": False, "error": error,
                              "records": [], "props": [], "n_records": 0,
                              "n_expected": 0, "bare_run_ok": None},
        kill_group=lambda proc: None,
    )


def test_create_command_has_no_host_mounts_or_docker_socket():
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(bridge, "_sandbox", _fake_sandbox)
    monkeypatch.setattr(bridge, "_candidate_interpreter", lambda image: "/opt/bcb-venv/bin/python")
    command = bridge._create_command("registry.example/pbt@sha256:" + "a" * 64, "pbt-test")
    monkeypatch.undo()
    assert command[:3] == ["docker", "create", "--name"]
    assert command[command.index("--entrypoint") + 1] == "/opt/bcb-venv/bin/python"
    assert "--network" in command and command[command.index("--network") + 1] == "none"
    assert "--read-only" in command and "--cap-drop" in command
    assert "ALL" in command and "no-new-privileges" in command
    assert "--pids-limit" in command and "--memory" in command and "--cpus" in command
    assert "-v" not in command and "--volume" not in command
    assert command[-2:] == ["-c", "import time; time.sleep(86400)"]
    assert command[command.index("--workdir") + 1] == "/tmp"
    assert "/opt/archive:ro,noexec,nosuid,nodev,size=1m" in command
    assert "/opt/runner:ro,noexec,nosuid,nodev,size=1m" in command
    assert "PYTHONPATH=" in command and "PBT_ARCHIVE=" in command
    assert not any("docker.sock" in arg or "DOCKER_CONFIG" in arg or "API_KEY" in arg for arg in command)


def test_candidate_python_label_is_cached_and_legacy_falls_back(monkeypatch):
    monkeypatch.setattr(bridge, "_CANDIDATE_INTERPRETER_CACHE", {})
    calls = []

    def inspect(command, **kwargs):
        calls.append((command, kwargs))
        labels = {bridge.CANDIDATE_PYTHON_LABEL: "/opt/bcb-venv/bin/python"} if command[-1] == "unified" else {}
        return SimpleNamespace(stdout=json.dumps(labels))

    monkeypatch.setattr(bridge.subprocess, "run", inspect)
    assert bridge._candidate_interpreter("unified") == "/opt/bcb-venv/bin/python"
    assert bridge._candidate_interpreter("unified") == "/opt/bcb-venv/bin/python"
    assert bridge._candidate_interpreter("legacy") == "python"
    assert len(calls) == 2
    assert all(call[1]["timeout"] == 30 for call in calls)


def test_run_raw_streams_trusted_harness_to_container_and_validates_result(monkeypatch):
    fake = _fake_sandbox()
    monkeypatch.setattr(bridge, "_sandbox", lambda: fake)
    monkeypatch.setattr(bridge, "_container_name", lambda: "pbt-fixed")
    monkeypatch.setattr(bridge, "_CANDIDATE_INTERPRETER_CACHE", {})
    seen = []
    calls = []

    def run(command, **kwargs):
        seen.append(command)
        calls.append((command, kwargs))
        if command[1:3] == ["image", "inspect"]:
            return SimpleNamespace(returncode=0, stdout=json.dumps({bridge.CANDIDATE_PYTHON_LABEL: "/opt/bcb-venv/bin/python"}), stderr="")
        if command[1:2] == ["exec"] and "-c" in command:
            stdout = (json.dumps({"props": ["prop_ok"], "bare_run_ok": [True]}) + "\n" +
                      json.dumps({"prop": "prop_ok", "i": 0, "outcome": "catch"}) + "\n").encode()
            return SimpleNamespace(returncode=0, stdout=stdout, stderr=b"")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    class Proc:
        returncode = 0
        input_bytes = None
        def communicate(self, input=None, timeout=None):
            self.input_bytes = input
            assert input == b"trusted harness source"
            return b"", b""

    monkeypatch.setattr(bridge.subprocess, "run", run)
    process = Proc()
    monkeypatch.setattr(bridge.subprocess, "Popen", lambda *a, **k: seen.append(a[0]) or process)
    result = bridge.run_raw(object(), "candidate", "props", [1], timeout_s=3,
                            probe_bare_run=True, docker_image="sha256:" + "b" * 64)
    assert result["ok"] and result["complete"]
    assert result["records"][0]["outcome"] == "catch"
    assert result["bare_run_ok"] == [True]
    assert any(c[:3] == ["docker", "create", "--name"] for c in seen)
    assert any(c[1:3] == ["rm", "--force"] for c in seen)
    assert not any(c[1] == "cp" for c in seen)
    assert ["docker", "start", "pbt-fixed"] in seen
    assert ["docker", "exec", "-i", "--workdir", "/tmp", "pbt-fixed", "/opt/bcb-venv/bin/python", "-"] in seen
    assert any(c[1:2] == ["exec"] and "/opt/bcb-venv/bin/python" in c and "-c" in c for c in seen)
    assert process.input_bytes == b"trusted harness source"
    assert all(kwargs.get("timeout") == 30 for command, kwargs in calls
               if command[0:2] in (["docker", "create"], ["docker", "start"]) or
               command[1:3] == ["image", "inspect"] or
               command[1:2] == ["exec"])


def test_timeout_kills_and_removes_container(monkeypatch):
    fake = _fake_sandbox()
    monkeypatch.setattr(bridge, "_sandbox", lambda: fake)
    monkeypatch.setattr(bridge, "_container_name", lambda: "pbt-timeout")
    monkeypatch.setattr(bridge, "_candidate_interpreter", lambda image: "/opt/bcb-venv/bin/python")
    seen = []
    def run(command, **kwargs):
        seen.append(command)
        if command[1:2] == ["exec"] and "-c" in command:
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
    monkeypatch.setattr(bridge.subprocess, "run", run)

    class Proc:
        returncode = -9
        calls = 0
        def communicate(self, input=None, timeout=None):
            self.calls += 1
            if self.calls == 1:
                assert input == b"trusted harness source"
                raise subprocess.TimeoutExpired("docker exec", timeout)
            return b"", b""
        def terminate(self):
            pass
        def wait(self, timeout=None): return -9
        def kill(self): pass
    monkeypatch.setattr(bridge.subprocess, "Popen", lambda *a, **k: seen.append(a[0]) or Proc())
    result = bridge.run_raw(object(), "candidate", "props", [1], timeout_s=1,
                            docker_image="sha256:" + "c" * 64)
    assert not result["ok"]
    assert ["docker", "rm", "--force", "pbt-timeout"] in seen
    reader = next(i for i, command in enumerate(seen) if command[1:2] == ["exec"] and "-c" in command)
    removed = next(i for i, command in enumerate(seen) if command[1] == "rm")
    assert reader < removed
    assert not any(command[1] == "cp" for command in seen)


def test_requires_pinned_digest():
    with pytest.raises(ValueError, match="immutable sha256"):
        bridge._create_command("registry.example/pbt:latest", "pbt-test")


def test_result_reader_rejects_symlinks_and_nonregular_files():
    reader = bridge._result_reader_code()
    assert 'getattr(os, "O_NOFOLLOW", 0)' in reader
    assert 'stat.S_ISREG(info.st_mode)' in reader
    assert 'getattr(os, "O_NONBLOCK", 0)' in reader
    assert f"limit = {bridge.MAX_RESULT_BYTES}" in reader
