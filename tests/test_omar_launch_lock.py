"""Startup-lock process boundaries, without coordinator, candidate, or model calls."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event

import pytest

from pipeline.protocols import omar_runtime


def test_os_primitive_nonblocking_lock_is_released_explicitly(tmp_path):
    path = tmp_path / "primitive.lock"
    with path.open("a+b") as owner, path.open("a+b") as contender:
        omar_runtime._set_launch_lock(owner, acquire=True)
        try:
            with pytest.raises(OSError):
                omar_runtime._set_launch_lock(contender, acquire=True)
        finally:
            omar_runtime._set_launch_lock(owner, acquire=False)
        omar_runtime._set_launch_lock(contender, acquire=True)
        omar_runtime._set_launch_lock(contender, acquire=False)


def test_dead_owner_file_does_not_block_and_live_owner_fails_without_waiting(tmp_path):
    lock_path = tmp_path / "coordinator.launching"
    lock_path.write_bytes(omar_runtime.LAUNCH_GUARD_MARKER)
    with omar_runtime.coordinator_launch_lock(tmp_path):
        started = time.monotonic()
        with pytest.raises(RuntimeError, match="already launching"):
            with omar_runtime.coordinator_launch_lock(tmp_path):
                pytest.fail("a live owner was bypassed")
        assert time.monotonic() - started < 1
    assert lock_path.read_bytes() == omar_runtime.LAUNCH_GUARD_MARKER
    with omar_runtime.coordinator_launch_lock(tmp_path):
        pass


@pytest.mark.parametrize("content", [b"", b"unverifiable old owner"])
def test_legacy_owner_is_unknowable_and_guard_is_never_removed(tmp_path, content):
    legacy = tmp_path / "coordinator.launching"
    legacy.write_bytes(content)
    with pytest.raises(RuntimeError, match="already launching"):
        with omar_runtime.coordinator_launch_lock(tmp_path):
            pytest.fail("unknown legacy owner was bypassed")
    assert legacy.read_bytes() == content


def test_two_simultaneous_launchers_have_exactly_one_owner(tmp_path):
    ready = Barrier(2)
    contender_finished = Event()

    def contend():
        ready.wait(timeout=5)
        try:
            with omar_runtime.coordinator_launch_lock(tmp_path):
                assert contender_finished.wait(timeout=5)
                return "owner"
        except RuntimeError as error:
            assert "already launching" in str(error)
            contender_finished.set()
            return "blocked"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: contend(), range(2)))
    assert sorted(results) == ["blocked", "owner"]


def test_startup_exception_releases_os_lock_without_removing_file(tmp_path):
    with pytest.raises(ValueError, match="startup failed"):
        with omar_runtime.coordinator_launch_lock(tmp_path):
            raise ValueError("startup failed")
    assert (tmp_path / "coordinator.launching").read_bytes() == omar_runtime.LAUNCH_GUARD_MARKER
    with omar_runtime.coordinator_launch_lock(tmp_path):
        pass


def test_real_child_death_releases_lock_and_live_child_cannot_be_bypassed(tmp_path):
    module_path = Path(omar_runtime.__file__).resolve()
    ready = tmp_path / "child-ready"
    script = (
        "import importlib.util, os, pathlib, sys\n"
        "spec = importlib.util.spec_from_file_location('lock_runtime', sys.argv[1])\n"
        "runtime = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(runtime)\n"
        "with runtime.coordinator_launch_lock(pathlib.Path(sys.argv[2])):\n"
        "    pathlib.Path(sys.argv[3]).write_text(str(os.getpid()))\n"
        "    sys.stdin.read()\n"
    )
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    child = subprocess.Popen(
        [sys._base_executable, "-c", script, str(module_path), str(tmp_path), str(ready)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options,
    )
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists(), "disposable lock-only child did not acquire its lock"
        assert int(ready.read_text()) == child.pid, "kill must target the real lock holder"
        with pytest.raises(RuntimeError, match="already launching"):
            with omar_runtime.coordinator_launch_lock(tmp_path):
                pytest.fail("a real live child lock was bypassed")
        child.kill()
        child.wait(timeout=5)
        with omar_runtime.coordinator_launch_lock(tmp_path):
            pass
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)
