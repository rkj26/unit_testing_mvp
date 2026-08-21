"""`pipeline.launch` must never report a launch that did not happen.

A detached run is invisible. If the command dies on startup the session vanishes, and a caller
holding only a returned string would carry on believing a run is in flight — the same shape as
every other failure in this repo that silently became a value. These tests pin the raising
behaviour, which is what stands between a mistyped flag and an empty morning.
"""

from __future__ import annotations

import shutil
import uuid

import pytest

from pipeline import launch as launch_mod

pytestmark = pytest.mark.skipif(
    shutil.which("tmux") is None, reason="tmux is not installed"
)

FAST_GRACE_SECONDS = 0.5
LONG_ENOUGH_TO_OUTLIVE_THE_TEST = "30"


@pytest.fixture
def session_name():
    name = f"pytest-launch-{uuid.uuid4().hex[:8]}"
    yield name
    launch_mod.kill(name)


def test_launch_returns_while_the_run_keeps_going(session_name, tmp_path):
    command = launch_mod.launch(
        session_name,
        ["sleep", LONG_ENOUGH_TO_OUTLIVE_THE_TEST],
        cwd=tmp_path,
        grace_seconds=FAST_GRACE_SECONDS,
    )
    assert "sleep" in command
    assert launch_mod.alive(session_name)


def test_launch_raises_when_the_command_dies_immediately(session_name, tmp_path):
    with pytest.raises(launch_mod.LaunchFailed) as raised:
        launch_mod.launch(
            session_name,
            ["sh", "-c", "echo boom >&2; exit 3"],
            cwd=tmp_path,
            grace_seconds=FAST_GRACE_SECONDS,
        )
    assert "boom" in str(raised.value)
    assert not launch_mod.alive(session_name)


def test_launch_refuses_a_second_process_on_one_run_id(session_name, tmp_path):
    launch_mod.launch(
        session_name,
        ["sleep", LONG_ENOUGH_TO_OUTLIVE_THE_TEST],
        cwd=tmp_path,
        grace_seconds=FAST_GRACE_SECONDS,
    )
    with pytest.raises(launch_mod.LaunchFailed, match="already running"):
        launch_mod.launch(
            session_name,
            ["sleep", LONG_ENOUGH_TO_OUTLIVE_THE_TEST],
            cwd=tmp_path,
            grace_seconds=FAST_GRACE_SECONDS,
        )


def test_console_log_captures_the_output(session_name, tmp_path):
    launch_mod.launch(
        session_name,
        ["sh", "-c", f"echo hello; sleep {LONG_ENOUGH_TO_OUTLIVE_THE_TEST}"],
        cwd=tmp_path,
        grace_seconds=FAST_GRACE_SECONDS,
    )
    log = launch_mod.console_log(session_name, tmp_path)
    assert "hello" in log.read_text(encoding="utf-8")


def test_pane_raises_for_a_session_that_is_not_there(session_name):
    with pytest.raises(launch_mod.LaunchFailed):
        launch_mod.pane(session_name)
