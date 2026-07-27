"""Root-owned supervisor for a persistent, unprivileged candidate worker."""

from __future__ import annotations

import json
import ctypes
import os
import resource
import select
import signal
import socket
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from codec import decode_value, encode_value

MAX_MESSAGE_BYTES = 1_000_000
IPC_RMID = 0


def _read_message(fd: int, timeout: float) -> bytes:
    ready, _, _ = select.select([fd], [], [], timeout)
    if not ready:
        raise TimeoutError("candidate call timed out")
    header = os.read(fd, 4)
    if len(header) != 4:
        raise EOFError("candidate worker closed its protocol pipe")
    size = struct.unpack("!I", header)[0]
    if size > MAX_MESSAGE_BYTES:
        raise ValueError("candidate message exceeded limit")
    chunks = bytearray()
    while len(chunks) < size:
        ready, _, _ = select.select([fd], [], [], timeout)
        if not ready:
            raise TimeoutError("candidate call timed out")
        chunk = os.read(fd, size - len(chunks))
        if not chunk:
            raise EOFError("candidate worker closed its protocol pipe")
        chunks.extend(chunk)
    return bytes(chunks)


def _write_message(fd: int, body: bytes) -> None:
    if len(body) > MAX_MESSAGE_BYTES:
        raise ValueError("candidate message exceeded limit")
    payload = struct.pack("!I", len(body)) + body
    while payload:
        written = os.write(fd, payload)
        payload = payload[written:]


def _recv_exact(connection: socket.socket, size: int) -> bytes:
    value = bytearray()
    while len(value) < size:
        chunk = connection.recv(size - len(value))
        if not chunk:
            raise EOFError("incomplete RPC request")
        value.extend(chunk)
    return bytes(value)


def _worker(read_fd: int, write_fd: int, payload: dict) -> None:
    os.setsid()
    os.setgroups([])
    os.setgid(int(payload["worker_gid"]))
    os.setuid(int(payload["worker_uid"]))
    memory = int(payload["memory_mb"]) * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_CPU, (int(payload["cpu_seconds"]),) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (1_000_000, 1_000_000))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))

    namespace = {"__name__": "candidate_module", "__file__": "<candidate>"}
    try:
        exec(compile(payload["module_code"], "<candidate>", "exec"), namespace)
        function = namespace.get(payload["entry_point"])
        if not callable(function):
            raise ValueError(f"candidate does not define {payload['entry_point']!r}")
    except BaseException as error:
        body = json.dumps(
            {
                "ok": False,
                "exception": type(error).__name__,
                "message": str(error)[:1000],
            }
        ).encode()
        _write_message(write_fd, body)
        return

    while True:
        try:
            request = json.loads(_read_message(read_fd, 86_400))
            args = decode_value(request["args"])
            kwargs = decode_value(request["kwargs"])
            result = function(*args, **kwargs)
            response = {
                "ok": True,
                "result": encode_value(result),
                "args_after": encode_value(args),
                "kwargs_after": encode_value(kwargs),
            }
        except BaseException as error:
            response = {
                "ok": False,
                "exception": type(error).__name__,
                "message": str(error)[:1000],
            }
        _write_message(
            write_fd,
            json.dumps(response, separators=(",", ":"), allow_nan=False).encode(),
        )


def _spawn_worker(payload: dict) -> tuple[int, int, int]:
    parent_read, child_write = os.pipe()
    child_read, parent_write = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(parent_read)
        os.close(parent_write)
        _worker(child_read, child_write, payload)
        os._exit(0)
    os.close(child_read)
    os.close(child_write)
    return pid, parent_read, parent_write


def _error(error: BaseException) -> bytes:
    return json.dumps(
        {"ok": False, "exception": type(error).__name__, "message": str(error)[:1000]}
    ).encode()


def _kill_unprivileged_processes(worker_uid: int) -> None:
    """Kill escaped descendants even if they created a new process group."""
    for status_path in Path("/proc").glob("[0-9]*/status"):
        try:
            lines = status_path.read_text(encoding="utf-8").splitlines()
            uid_line = next(line for line in lines if line.startswith("Uid:"))
            if int(uid_line.split()[1]) == worker_uid:
                os.kill(int(status_path.parent.name), signal.SIGKILL)
        except (
            FileNotFoundError,
            ProcessLookupError,
            PermissionError,
            StopIteration,
            ValueError,
        ):
            pass


def _remove_worker_sysv_ipc(worker_uid: int) -> None:
    """Remove SysV IPC markers owned by the worker without CAP_SYS_ADMIN."""
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
                if int(row["uid"]) == worker_uid or int(row["cuid"]) == worker_uid:
                    owned.append((kind, int(row[id_column])))
            except (KeyError, ValueError):
                continue
    if not owned:
        return
    libc = ctypes.CDLL(None, use_errno=True)
    failures: list[tuple[str, int, int]] = []
    os.seteuid(worker_uid)
    try:
        for kind, value in owned:
            if specs[kind][1](libc, value) == -1:
                error_number = ctypes.get_errno()
                if error_number not in {22, 43}:  # EINVAL / EIDRM: already gone
                    failures.append((kind, value, error_number))
    finally:
        os.seteuid(0)
    if failures:
        raise RuntimeError(f"failed to remove worker SysV IPC objects: {failures}")


def main() -> None:
    cleanup_only = len(sys.argv) == 3 and sys.argv[1] == "--cleanup"
    payload_path = sys.argv[2] if cleanup_only else sys.argv[1]
    payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    worker_uid = int(payload["worker_uid"])
    if cleanup_only:
        _kill_unprivileged_processes(worker_uid)
        _remove_worker_sysv_ipc(worker_uid)
        return
    socket_path = Path(sys.argv[2])
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    os.chown(socket_path.parent, 0, int(payload["rpc_gid"]))
    os.chmod(socket_path.parent, 0o750)
    socket_path.unlink(missing_ok=True)

    _kill_unprivileged_processes(worker_uid)
    _remove_worker_sysv_ipc(worker_uid)
    worker_pid, worker_read, worker_write = _spawn_worker(payload)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(socket_path))
    os.chown(socket_path, 0, int(payload["rpc_gid"]))
    os.chmod(socket_path, 0o660)
    server.listen(8)

    def stop(_signum, _frame) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        while True:
            connection, _ = server.accept()
            with connection:
                connection.settimeout(float(payload["call_timeout_seconds"]))
                try:
                    header = _recv_exact(connection, 4)
                    size = struct.unpack("!I", header)[0]
                    if size > MAX_MESSAGE_BYTES:
                        raise ValueError("RPC request exceeded limit")
                    body = _recv_exact(connection, size)
                    json.loads(body)
                    _write_message(worker_write, bytes(body))
                    response = _read_message(
                        worker_read, float(payload["call_timeout_seconds"])
                    )
                except BaseException as error:
                    response = _error(error)
                    try:
                        os.killpg(worker_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    _kill_unprivileged_processes(worker_uid)
                connection.sendall(struct.pack("!I", len(response)) + response)
    finally:
        socket_path.unlink(missing_ok=True)
        try:
            os.killpg(worker_pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        _kill_unprivileged_processes(worker_uid)
        _remove_worker_sysv_ipc(worker_uid)


if __name__ == "__main__":
    main()
