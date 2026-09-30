"""Test isolation: no test may write into the repo, poison the process environment, or resume
another test's artifacts.

`engine.run` resolves `Path("runs") / run_id` against the current working directory, and
`search.SEARCH_CACHE` is likewise CWD-relative, so without `isolate_working_directory` a pipeline
test writes into the real `runs/` and the next invocation short-circuits on its own leftovers.
`model.resolve` calls `os.environ.setdefault` on six credential variables, which outlives the test
that triggered it unless the environment is restored.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest



@pytest.fixture(autouse=True)
def isolate_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run each test in its own empty directory so CWD-relative artifact paths stay disposable."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def restore_environment():
    """Undo `model.resolve`'s credential `setdefault` calls so they cannot leak between tests."""
    snapshot = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(snapshot)


