"""A notebook worker owns its execution lock before paid work or failure artifacts."""

from pathlib import Path
import subprocess
import sys
import sysconfig
import time

import pytest

from pipeline.protocols import omar_notebook, omar_runtime


def test_duplicate_notebook_worker_cannot_enter_or_poison_owner_failure(tmp_path, monkeypatch):
    identity = tmp_path / "identity.json"
    identity.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(omar_notebook, "_attach_reference",
                        lambda *_: pytest.fail("duplicate entered paid worker body"))
    (tmp_path / "execution").mkdir()
    with omar_runtime.coordinator_launch_lock(tmp_path / "execution"):
        with pytest.raises(RuntimeError, match="already launching"):
            omar_notebook.worker(identity, "initial")
    assert not (tmp_path / "failed.json").exists()


def test_notebook_execution_lock_recovers_after_owner_process_dies(tmp_path, monkeypatch):
    identity = tmp_path / "identity.json"
    ready = tmp_path / "ready"
    root = Path(omar_notebook.__file__).resolve().parents[2]
    script = (
        f"import site; site.addsitedir({sysconfig.get_path('purelib')!r}); "
        "from pathlib import Path; import os, time; "
        "from pipeline.protocols import omar_notebook; "
        f"omar_notebook._worker = lambda *_: (Path({str(ready)!r}).write_text(str(os.getpid())), time.sleep(60)); "
        f"omar_notebook.worker(Path({str(identity)!r}), 'initial')"
    )
    child = subprocess.Popen([sys._base_executable, "-B", "-c", script], cwd=root,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists(), child.communicate(timeout=1)
        assert int(ready.read_text()) == child.pid
        entered = []
        monkeypatch.setattr(omar_notebook, "_worker", lambda *_: entered.append(True), raising=False)
        with pytest.raises(RuntimeError, match="already launching"):
            omar_notebook.worker(identity, "initial")
        assert not entered and not (tmp_path / "failed.json").exists()
        child.terminate()
        child.wait(timeout=5)
        omar_notebook.worker(identity, "initial")
        assert entered == [True]
        assert not (tmp_path / "failed.json").exists()
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
        child.communicate(timeout=5)
