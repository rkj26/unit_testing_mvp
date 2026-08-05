"""PBT execution harness generation and subprocess runner.

Extracted from pbt.py to isolate sandbox code generation, timeout signal handling,
and process-group lifecycle management.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .schema import Problem

SINGLE_CANDIDATE_CALL_SECONDS = 6
DEFAULT_PBT_TIMEOUT = 60

_HARNESS = '''\
import json, sys, io, contextlib, os, subprocess
RESULT = os.environ["PBT_RESULT"]

class _CandidateError(Exception):
    """The CANDIDATE under test raised (or a stdio program exited nonzero)."""

__ENTRY_SETUP__

# ---- model-written properties ----
__PROPERTIES__
# ---- end properties ----

SPACE = json.loads(__SPACE_JSON__)
_props = [(n, f) for n, f in sorted(globals().items())
          if (n.startswith("prop_") or n.startswith("test_")) and callable(f)]
_records = []
for _pname, _pfn in _props:
    for _i, _x in enumerate(SPACE):
        _rec = {"prop": _pname, "i": _i}
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                _pfn(run, _x)
            _rec["outcome"] = "pass"
        except AssertionError as _e:
            _rec["outcome"] = "catch"; _rec["msg"] = str(_e)[:300]
        except _CandidateError as _e:
            _rec["outcome"] = "candidate_crash"; _rec["msg"] = str(_e)[:300]
        except Exception as _e:
            _rec["outcome"] = "prop_error"; _rec["msg"] = type(_e).__name__ + ": " + str(_e)[:300]
        _records.append(_rec)
with open(RESULT, "w") as _f:
    json.dump({"props": [n for n, _ in _props], "records": _records}, _f)
'''

_ENTRY_FUNCTION = """\
import signal as _signal
_g = {}
exec(compile(__CANDIDATE_SRC__, "candidate.py", "exec"), _g)
_ENTRY = _g[__ENTRY_NAME__]
class _Timeout(BaseException):
    pass
def _on_alarm(_s, _f):
    raise _Timeout()
_signal.signal(_signal.SIGALRM, _on_alarm)
def run(x):
    _signal.setitimer(_signal.ITIMER_REAL, __CAND_TIMEOUT__)
    try:
        return _ENTRY(**x)
    except _Timeout:
        raise _CandidateError("timeout")
    except Exception as _e:
        raise _CandidateError(type(_e).__name__ + ": " + str(_e)[:200])
    finally:
        _signal.setitimer(_signal.ITIMER_REAL, 0)
"""

_ENTRY_STDIO = """\
import io as _io, signal as _signal
_CAND_CODE = compile(__CANDIDATE_SRC__, "candidate_prog.py", "exec")
class _Timeout(BaseException):
    pass
def _on_alarm(_s, _f):
    raise _Timeout()
_signal.signal(_signal.SIGALRM, _on_alarm)
def run(x):
    _old_in, _old_out, _old_argv = sys.stdin, sys.stdout, sys.argv
    _signal.setitimer(_signal.ITIMER_REAL, __CAND_TIMEOUT__)
    try:
        sys.stdin, sys.stdout, sys.argv = _io.StringIO(x), _io.StringIO(), ["candidate_prog.py"]
        exec(_CAND_CODE, {"__name__": "__main__"})
    except _Timeout:
        raise _CandidateError("timeout")
    except SystemExit as _e:
        if _e.code not in (0, None):
            raise _CandidateError("exit %s" % _e.code)
    except Exception as _e:
        raise _CandidateError(type(_e).__name__ + ": " + str(_e)[:200])
    finally:
        _signal.setitimer(_signal.ITIMER_REAL, 0)
        _result = sys.stdout.getvalue() if hasattr(sys.stdout, "getvalue") else ""
        sys.stdin, sys.stdout, sys.argv = _old_in, _old_out, _old_argv
    return _result
"""


def build_harness(problem: Problem, code: str, props_src: str, space: list[Any]) -> str:
    if problem.io_mode == "function":
        setup = (
            _ENTRY_FUNCTION.replace("__CANDIDATE_SRC__", repr(code))
            .replace("__ENTRY_NAME__", repr(problem.entry_point))
            .replace("__CAND_TIMEOUT__", str(SINGLE_CANDIDATE_CALL_SECONDS))
        )
    else:
        setup = _ENTRY_STDIO.replace("__CANDIDATE_SRC__", repr(code)).replace(
            "__CAND_TIMEOUT__", str(SINGLE_CANDIDATE_CALL_SECONDS)
        )
    return (
        _HARNESS.replace("__ENTRY_SETUP__", setup)
        .replace("__PROPERTIES__", props_src)
        .replace("__SPACE_JSON__", repr(json.dumps(space)))
    )


def kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        proc.wait(timeout=5)
    except Exception:
        pass


def run_raw(
    problem: Problem,
    code: str,
    props_src: str,
    space: list[Any],
    *,
    timeout_s: int = DEFAULT_PBT_TIMEOUT,
) -> dict[str, Any]:
    """Run every property over every search-space input against one implementation."""
    directory = tempfile.mkdtemp(prefix="pbt_")
    try:
        (Path(directory) / "harness.py").write_text(
            build_harness(problem, code, props_src, space), encoding="utf-8"
        )
        env = {**os.environ, "PBT_RESULT": "pbt_result.json"}
        proc = subprocess.Popen(
            [sys.executable, "harness.py"],
            cwd=directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            start_new_session=True,
        )
        try:
            _out, err = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            kill_group(proc)
            return {"ok": False, "error": "timeout", "records": [], "props": []}
        try:
            result = json.loads(
                (Path(directory) / "pbt_result.json").read_text(encoding="utf-8")
            )
            records, props = result["records"], result["props"]
        except Exception:
            return {
                "ok": False,
                "error": (err or "no result file")[:500],
                "records": [],
                "props": [],
            }
        return {"ok": True, "error": None, "records": records, "props": props}
    finally:
        shutil.rmtree(directory, ignore_errors=True)
