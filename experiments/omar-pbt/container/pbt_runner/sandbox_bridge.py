"""Docker-only execution bridge for the frozen PBT harness.

The Docker CLI runs on the trusted runner. Candidate code runs only in a disposable
container with no host mounts, network, capabilities, or writable root filesystem.
"""

from __future__ import annotations

import re
import json
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

MAX_RESULT_BYTES = 8 * 1024 * 1024
CANDIDATE_PYTHON_LABEL = "org.omar-pbt.candidate-python"
_CANDIDATE_INTERPRETER_CACHE: dict[str, str] = {}


def _sandbox():
    """Import the frozen pipeline only when a caller asks to run a harness."""
    from pipeline import sandbox

    return sandbox


def _container_name() -> str:
    return "pbt-runner-" + uuid.uuid4().hex


def _candidate_interpreter(image: str) -> str:
    """Choose the candidate-only interpreter declared by an image, caching by digest ref."""
    if image in _CANDIDATE_INTERPRETER_CACHE:
        return _CANDIDATE_INTERPRETER_CACHE[image]
    inspected = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{json .Config.Labels}}", image],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        labels = json.loads(inspected.stdout or "null")
    except json.JSONDecodeError as error:
        raise ValueError("docker image labels were not valid JSON") from error
    if labels is None:
        labels = {}
    if not isinstance(labels, dict):
        raise ValueError("docker image labels were not an object")
    if CANDIDATE_PYTHON_LABEL in labels:
        interpreter = labels[CANDIDATE_PYTHON_LABEL]
        if (not isinstance(interpreter, str) or
            not re.fullmatch(r"/[A-Za-z0-9_./+-]+", interpreter)):
            raise ValueError("candidate-python image label must be an absolute executable path")
    else:
        interpreter = "python"
    _CANDIDATE_INTERPRETER_CACHE[image] = interpreter
    return interpreter


def _result_reader_code() -> str:
    """Trusted bounded reader for the candidate-writable tmpfs result file."""
    return f'''import os, stat, sys
path = os.environ["PBT_RESULT"]
flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
fd = os.open(path, flags)
try:
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode):
        raise SystemExit("result is not a regular file")
    limit = {MAX_RESULT_BYTES}
    if info.st_size > limit:
        raise SystemExit("result exceeds byte limit")
    chunks = []
    remaining = limit + 1
    while remaining:
        chunk = os.read(fd, min(65536, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    data = b"".join(chunks)
    if len(data) > limit:
        raise SystemExit("result exceeds byte limit")
    sys.stdout.buffer.write(data)
finally:
    os.close(fd)
'''


def _create_command(image: str, name: str) -> list[str]:
    if not image or not re.fullmatch(r"(?:sha256:|[^\s]+@sha256:)[0-9a-f]{64}", image):
        raise ValueError("docker_image must be an immutable sha256 image reference")
    sandbox = _sandbox()
    interpreter = _candidate_interpreter(image)
    return [
        "docker", "create", "--name", name,
        "--entrypoint", interpreter,
        "--network", "none",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--memory", sandbox.DOCKER_MEMORY_LIMIT,
        "--memory-swap", sandbox.DOCKER_MEMORY_LIMIT,
        "--cpus", sandbox.DOCKER_CPU_LIMIT,
        "--pids-limit", str(sandbox.DOCKER_PID_LIMIT),
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        "--tmpfs", "/opt/archive:ro,noexec,nosuid,nodev,size=1m",
        "--tmpfs", "/opt/runner:ro,noexec,nosuid,nodev,size=1m",
        "--workdir", "/tmp",
        "--env", f"PBT_RESULT=/tmp/{sandbox.RESULT_FILENAME}",
        "--env", "PYTHONPATH=",
        "--env", "PBT_ARCHIVE=",
        image, "-c", "import time; time.sleep(86400)",
    ]


def run_raw(
    task: Any,
    code: str,
    props_src: str,
    space: list[Any],
    *,
    timeout_s: int = 60,
    probe_bare_run: bool = False,
    isolation: Any = None,
    docker_image: str = "",
) -> dict[str, Any]:
    """Run a snapshot-compatible harness in a network-disabled Docker container.

    The optional `isolation` keyword is accepted for call-site compatibility, but this
    adapter never delegates candidate execution to the host subprocess implementation.
    Apply any study-specific candidate wrapper (for example BCB deepcopy) to ``code``
    before calling this function.
    """
    del isolation
    sandbox = _sandbox()
    interpreter = _candidate_interpreter(docker_image)
    name = _container_name()
    host_dir = tempfile.mkdtemp(prefix="pbt_runner_trusted_")
    harness_path = Path(host_dir) / sandbox.HARNESS_FILENAME
    created = False
    exit_note = "container completed"
    try:
        harness_path.write_text(
            sandbox.build_harness(
                task, code, props_src, space,
                probe_bare_run=probe_bare_run,
                work_seconds=timeout_s,
            ),
            encoding="utf-8",
        )
        subprocess.run(_create_command(docker_image, name), check=True, capture_output=True, text=True, timeout=30)
        created = True
        subprocess.run(["docker", "start", name], check=True, capture_output=True, text=True, timeout=30)
        hard_kill_s = max(1, timeout_s) + sandbox.HARNESS_KILL_GRACE_SECONDS
        proc = subprocess.Popen(
            ["docker", "exec", "-i", "--workdir", "/tmp", name, interpreter, "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            proc.communicate(input=harness_path.read_bytes(), timeout=hard_kill_s)
            exit_note = f"harness exited {proc.returncode}"
        except subprocess.TimeoutExpired:
            exit_note = f"killed after {hard_kill_s}s"
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        try:
            reader = subprocess.run(
                ["docker", "exec", "--workdir", "/tmp", name, interpreter, "-c", _result_reader_code()],
                check=True,
                capture_output=True,
                timeout=30,
            )
        except subprocess.CalledProcessError as error:
            stderr = error.stderr.decode("utf-8", errors="replace") if isinstance(error.stderr, bytes) else str(error.stderr or "")
            return sandbox._failed(f"container result retrieval failed: {stderr[:400] or 'reader exited nonzero'}")
        except subprocess.TimeoutExpired:
            return sandbox._failed("container result retrieval timed out after 30s")
        try:
            result_text = reader.stdout.decode("utf-8")
        except UnicodeDecodeError:
            return sandbox._failed("container result file is not UTF-8")
        result, unreadable = sandbox._stream(result_text)
        if result is None:
            return sandbox._failed(f"{unreadable} ({exit_note})")
        try:
            props, records = sandbox._validated(result, len(space))
            bare_run_ok = sandbox._validated_bare_run(result, len(space)) if probe_bare_run else None
        except (ValueError, TypeError, KeyError) as error:
            return sandbox._failed(f"malformed harness result: {error}")
        n_expected = len(props) * len(space)
        n_records = len({(r["prop"], r["i"]) for r in records})
        if n_expected and not n_records:
            return sandbox._failed(f"harness recorded no property-input pair ({exit_note})")
        complete = n_records >= n_expected
        return {
            "ok": True,
            "complete": complete,
            "error": None if complete else f"{n_records}/{n_expected} pairs ({exit_note})",
            "records": records,
            "props": props,
            "n_records": n_records,
            "n_expected": n_expected,
            "bare_run_ok": bare_run_ok,
        }
    finally:
        if created:
            try:
                subprocess.run(["docker", "rm", "--force", name], capture_output=True, timeout=20)
            except Exception:
                pass
        shutil.rmtree(host_dir, ignore_errors=True)
