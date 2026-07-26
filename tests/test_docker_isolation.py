import json
import subprocess
import time
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _run(command, *, input_text=None, check=True):
    return subprocess.run(
        command,
        cwd=ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        check=check,
        timeout=120,
    )


@pytest.mark.docker
def test_candidate_and_checker_are_distinct_security_principals():
    project = "pbtboundary" + uuid.uuid4().hex[:10]
    compose = ["docker", "compose", "-p", project]
    session = uuid.uuid4().hex
    candidate_dir = f"/tmp/candidate-{session}"
    checker_dir = f"/tmp/checker-{session}"
    socket_path = f"/rpc/{session}/candidate.sock"
    candidate_source = """
import ctypes, os, pathlib, sys
libc = ctypes.CDLL(None)
marker_key = 0x554E4954
marker_seen = libc.shmget(marker_key, 1, 0o600) >= 0
if not marker_seen:
    assert libc.shmget(marker_key, 1, 0o1000 | 0o600) >= 0

def f(x):
    if 'pytest' in sys.modules or pathlib.Path('/tmp/checker-secret').exists():
        return -999
    if marker_seen:
        return -998
    if x == 7:
        try:
            child = os.fork()
        except OSError:
            return x + 1
        if child == 0:
            os._exit(0)
        return -997
    if x == 5:
        with open('/tmp/persistent-marker', 'w') as handle:
            handle.write('monitored')
    if x == 99:
        os._exit(0)
    return x + 1
"""
    payload = json.dumps(
        {
            "module_code": candidate_source,
            "entry_point": "f",
            "call_timeout_seconds": 2,
            "memory_mb": 128,
            "cpu_seconds": 10,
        }
    )

    try:
        _run(compose + ["up", "-d", "--build"])
        _run(compose + ["exec", "-T", "default", "mkdir", "-p", candidate_dir])
        for name in ("codec.py", "candidate_supervisor.py"):
            source = (ROOT / "sandbox_tools" / name).read_text()
            _run(
                compose
                + ["exec", "-T", "default", "sh", "-c", f"cat > {candidate_dir}/{name}"],
                input_text=source,
            )
        _run(
            compose
            + ["exec", "-T", "default", "sh", "-c", f"cat > {candidate_dir}/payload.json"],
            input_text=payload,
        )
        _run(
            compose
            + [
                "exec",
                "-T",
                "default",
                "chmod",
                "700",
                f"{candidate_dir}/codec.py",
                f"{candidate_dir}/candidate_supervisor.py",
            ]
        )
        _run(
            compose
            + ["exec", "-T", "default", "chmod", "600", f"{candidate_dir}/payload.json"]
        )
        launch = (
            f"python3 -I {candidate_dir}/candidate_supervisor.py {candidate_dir}/payload.json "
            f"{socket_path} >{candidate_dir}/log 2>&1 & echo $! > {candidate_dir}/pid"
        )
        _run(compose + ["exec", "-T", "default", "sh", "-c", launch])

        _run(compose + ["exec", "-T", "checker", "mkdir", "-p", checker_dir])
        _run(compose + ["exec", "-T", "checker", "mkdir", "-p", f"{checker_dir}/work"])
        for name in ("codec.py", "checker_proxy.py", "checker_supervisor.py"):
            source = (ROOT / "sandbox_tools" / name).read_text()
            _run(
                compose
                + ["exec", "-T", "checker", "sh", "-c", f"cat > {checker_dir}/{name}"],
                input_text=source,
            )
        _run(
            compose
            + [
                "exec",
                "-T",
                "checker",
                "chmod",
                "700",
                f"{checker_dir}/checker_supervisor.py",
            ]
        )
        _run(
            compose
            + [
                "exec",
                "-T",
                "checker",
                "chown",
                "1000:2000",
                f"{checker_dir}/work",
            ]
        )
        _run(
            compose + ["exec", "-T", "checker", "sh", "-c", "echo secret > /tmp/checker-secret"]
        )
        for _ in range(50):
            ready = _run(
                compose + ["exec", "-T", "checker", "test", "-S", socket_path], check=False
            )
            if ready.returncode == 0:
                break
            time.sleep(0.1)
        else:
            pytest.fail("candidate RPC socket did not become ready")

        script = f"""
import sys
sys.path.insert(0, {checker_dir!r})
from checker_proxy import call_candidate
import pathlib
locked = pathlib.Path({(checker_dir + '/work/locked')!r})
locked.mkdir()
(locked / 'owned').write_text('checker artifact')
locked.chmod(0)
assert call_candidate(1) == 2
try:
    import os
    os.fork()
except OSError:
    pass
else:
    raise AssertionError('checker worker unexpectedly forked')
assert call_candidate(7) == 8
try:
    open('/tmp/checker-marker', 'w')
except PermissionError:
    pass
else:
    raise AssertionError('checker worker unexpectedly wrote to global /tmp')
try:
    call_candidate(5)
except PermissionError:
    pass
else:
    raise AssertionError('candidate unexpectedly wrote to global /tmp')
try:
    call_candidate(99)
except Exception:
    pass
else:
    raise AssertionError('os._exit(0) was interpreted as success')
"""
        result = _run(
            compose
            + [
                "exec",
                "-T",
                "-e",
                f"PBT_RPC_SOCKET={socket_path}",
                "checker",
                "python3",
                "-I",
                f"{checker_dir}/checker_supervisor.py",
                f"{checker_dir}/work",
                "--",
                "python3",
                "-c",
                script,
            ],
            check=False,
        )
        assert result.returncode == 0, result.stderr or result.stdout
        marker = _run(
            compose + ["exec", "-T", "default", "test", "-e", "/tmp/persistent-marker"],
            check=False,
        )
        assert marker.returncode != 0

        # End the first candidate session, then start the same source again.
        # The second worker must not observe the first session's SysV IPC marker.
        stop = (
            f"p=$(cat {candidate_dir}/pid); kill -TERM $p 2>/dev/null || true; "
            "i=0; while kill -0 $p 2>/dev/null && [ $i -lt 50 ]; "
            "do i=$((i+1)); sleep 0.05; done"
        )
        _run(compose + ["exec", "-T", "default", "sh", "-c", stop])
        _run(compose + ["exec", "-T", "default", "sh", "-c", launch])
        for _ in range(50):
            ready = _run(
                compose + ["exec", "-T", "checker", "test", "-S", socket_path],
                check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.1)
        else:
            pytest.fail("restarted candidate RPC socket did not become ready")
        second = _run(
            compose
            + [
                "exec",
                "-T",
                "-e",
                f"PBT_RPC_SOCKET={socket_path}",
                "checker",
                "python3",
                "-I",
                f"{checker_dir}/checker_supervisor.py",
                f"{checker_dir}/work",
                "--",
                "python3",
                "-c",
                f"import sys; sys.path.insert(0, {checker_dir!r}); "
                "from checker_proxy import call_candidate; assert call_candidate(1) == 2",
            ],
            check=False,
        )
        assert second.returncode == 0, second.stderr or second.stdout

        services = _run(compose + ["config", "--services"]).stdout.splitlines()
        assert {
            "default",
            "candidate-main",
            "candidate-canonical",
            "candidate-side",
            "checker",
        }.issubset(services)
        cleanup = _run(
            compose
            + [
                "exec",
                "-T",
                "checker",
                "sh",
                "-c",
                f"rm -rf {checker_dir} && test ! -e {checker_dir}",
            ],
            check=False,
        )
        assert cleanup.returncode == 0, cleanup.stderr or cleanup.stdout
    finally:
        _run(compose + ["down", "-v", "--remove-orphans"], check=False)
