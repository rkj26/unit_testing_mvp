"""Root-owned launcher that contains and reaps one checker execution."""

from __future__ import annotations

import os
import ctypes
import resource
import signal
import sys
from pathlib import Path


IPC_RMID = 0


def _kill_checker_processes(checker_uid: int) -> None:
    for status_path in Path("/proc").glob("[0-9]*/status"):
        try:
            lines = status_path.read_text(encoding="utf-8").splitlines()
            uid_line = next(line for line in lines if line.startswith("Uid:"))
            if int(uid_line.split()[1]) == checker_uid:
                os.kill(int(status_path.parent.name), signal.SIGKILL)
        except (
            FileNotFoundError,
            ProcessLookupError,
            PermissionError,
            StopIteration,
            ValueError,
        ):
            pass


def _remove_checker_sysv_ipc(checker_uid: int) -> None:
    specs = {
        "shm": ("shmid", lambda libc, value: libc.shmctl(value, IPC_RMID, None)),
        "msg": ("msqid", lambda libc, value: libc.msgctl(value, IPC_RMID, None)),
        "sem": ("semid", lambda libc, value: libc.semctl(value, 0, IPC_RMID)),
    }
    owned: list[tuple[str, int]] = []
    for kind, (id_column, _) in specs.items():
        try:
            lines = (
                Path(f"/proc/sysvipc/{kind}").read_text(encoding="utf-8").splitlines()
            )
        except (FileNotFoundError, PermissionError):
            continue
        if not lines:
            continue
        columns = lines[0].split()
        for line in lines[1:]:
            row = dict(zip(columns, line.split()))
            try:
                if int(row["uid"]) == checker_uid or int(row["cuid"]) == checker_uid:
                    owned.append((kind, int(row[id_column])))
            except (KeyError, ValueError):
                continue
    if not owned:
        return
    libc = ctypes.CDLL(None, use_errno=True)
    failures: list[tuple[str, int, int]] = []
    os.seteuid(checker_uid)
    try:
        for kind, value in owned:
            if specs[kind][1](libc, value) == -1:
                error_number = ctypes.get_errno()
                if error_number not in {22, 43}:  # EINVAL / EIDRM: already gone
                    failures.append((kind, value, error_number))
    finally:
        os.seteuid(0)
    if failures:
        raise RuntimeError(f"failed to remove checker SysV IPC objects: {failures}")


def _worker(
    work_dir: str, command: list[str], checker_uid: int, checker_gid: int
) -> None:
    os.setsid()
    os.setgroups([])
    os.setgid(checker_gid)
    os.setuid(checker_uid)
    resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    resource.setrlimit(resource.RLIMIT_FSIZE, (4_000_000, 4_000_000))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))
    os.chdir(work_dir)
    environment = os.environ.copy()
    environment.update({"HOME": work_dir, "TMPDIR": work_dir})
    os.execvpe(command[0], command, environment)


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(
            "usage: checker_supervisor.py UID GID [--cleanup | WORK_DIR -- COMMAND]"
        )
    checker_uid = int(sys.argv[1])
    checker_gid = int(sys.argv[2])
    _kill_checker_processes(checker_uid)
    _remove_checker_sysv_ipc(checker_uid)
    if sys.argv[3:] == ["--cleanup"]:
        return
    if len(sys.argv) < 6 or sys.argv[4] != "--":
        raise SystemExit("usage: checker_supervisor.py UID GID WORK_DIR -- COMMAND")

    work_dir = sys.argv[3]
    command = sys.argv[5:]
    child = os.fork()
    if child == 0:
        _worker(work_dir, command, checker_uid, checker_gid)
        os._exit(127)

    def stop(_signum, _frame) -> None:
        raise SystemExit(1)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        _, status = os.waitpid(child, 0)
        if os.WIFEXITED(status):
            raise SystemExit(os.WEXITSTATUS(status))
        raise SystemExit(128 + os.WTERMSIG(status))
    finally:
        try:
            os.killpg(child, signal.SIGKILL)
        except ProcessLookupError:
            pass
        _kill_checker_processes(checker_uid)
        _remove_checker_sysv_ipc(checker_uid)


if __name__ == "__main__":
    main()
