"""Omar-only runtime checks kept out of shared team infrastructure."""

from __future__ import annotations

import shutil
import subprocess
import sys
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator


LAUNCH_GUARD_MARKER = b"omar-os-startup-lock-v1\n"


def _set_launch_lock(handle: BinaryIO, *, acquire: bool) -> None:
    """Acquire one nonblocking OS lock, or release it; never infer ownership from a PID."""
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        mode = msvcrt.LK_NBLCK if acquire else msvcrt.LK_UNLCK
        msvcrt.locking(handle.fileno(), mode, 1)
    else:
        import fcntl

        mode = fcntl.LOCK_EX | fcntl.LOCK_NB if acquire else fcntl.LOCK_UN
        fcntl.flock(handle.fileno(), mode)


@contextmanager
def coordinator_launch_lock(folder: Path) -> Iterator[None]:
    """Serialize startup; process death releases the lock, but legacy guards fail closed.

    The persistent version-marked guard must never be deleted: replacing its inode
    would permit two owners. Legacy launchers also refuse this existing guard.
    Hold the context through the PID write; this alone cannot cover a parent dying
    between spawning its worker and publishing the worker PID.
    """
    guard_path = folder / "coordinator.launching"
    try:
        handle = guard_path.open("r+b")
    except FileNotFoundError:
        with tempfile.NamedTemporaryFile(dir=folder, prefix=".omar-launch-", delete=False) as marker:
            marker_path = Path(marker.name)
            try:
                marker.write(LAUNCH_GUARD_MARKER)
                marker.flush()
                os.fsync(marker.fileno())
            except BaseException:
                marker.close()
                marker_path.unlink()
                raise
        try:
            try:
                os.link(marker_path, guard_path)
            except FileExistsError:
                pass
        finally:
            marker_path.unlink()
        handle = guard_path.open("r+b")
    with handle:
        try:
            _set_launch_lock(handle, acquire=True)
        except OSError as error:
            raise RuntimeError(
                f"Omar coordinator {folder.name!r} is already launching or its lock is unavailable"
            ) from error
        try:
            handle.seek(0)
            if handle.read() != LAUNCH_GUARD_MARKER:
                raise RuntimeError(
                    f"Omar coordinator {folder.name!r} is already launching; "
                    "legacy guard ownership is unknown. Stop all launchers and "
                    "verify no coordinator is running before manually migrating "
                    f"{guard_path}; it was not removed."
                )
            yield
        finally:
            _set_launch_lock(handle, acquire=False)


def validate_paid_options(allow_paid: bool, max_model_calls: int) -> None:
    if type(allow_paid) is not bool:
        raise TypeError("allow_paid must be an explicit bool")
    if type(max_model_calls) is not int or max_model_calls < 0:
        raise TypeError("max_model_calls must be a nonnegative int, not bool")


def require_paid(allow_paid: bool, max_model_calls: int, required: int) -> None:
    """Authorize logical workflow calls, not dollars or provider retry attempts."""
    validate_paid_options(allow_paid, max_model_calls)
    if not allow_paid or max_model_calls < required:
        raise PermissionError(
            f"New Omar work requires allow_paid=True and max_model_calls >= {required}; "
            "this is logical workflow authorization, not a monetary or HTTP-attempt cap")


def preflight_docker(image: str) -> None:
    """Fail before Omar model calls if the selected Docker image cannot run."""
    if shutil.which("docker") is None:
        raise RuntimeError("docker is not on PATH; no sandbox grid can run")
    try:
        proc = subprocess.run(["docker", "run", "--rm", image, "true"],
                              capture_output=True, timeout=180)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"docker image {image!r} did not start within 180 seconds") from error
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or b"").decode("utf-8", "replace").strip()
        raise RuntimeError(f"docker image {image!r} could not run: {detail[:400]}")
