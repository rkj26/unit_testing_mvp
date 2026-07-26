"""Pure validation and source-building helpers for generated PBT suites."""

from __future__ import annotations

import ast
import keyword


PROHIBITED_IMPORTS = {
    "ctypes",
    "http",
    "importlib",
    "multiprocessing",
    "os",
    "pathlib",
    "requests",
    "socket",
    "subprocess",
    "sys",
    "tempfile",
    "urllib",
}
PROHIBITED_CALLS = {"__import__", "compile", "eval", "exec", "open"}


def candidate_module_code(starter_code: str, submitted_code: str) -> str:
    starter_stub = f"{starter_code}\n    pass\n" if starter_code.strip() else ""
    return f"{starter_stub}\n{submitted_code}\n"


def checker_prelude(starter_code: str, entry_point: str, runtime_dir: str) -> str:
    if not entry_point.isidentifier() or keyword.iskeyword(entry_point):
        raise ValueError(f"invalid Python entry point: {entry_point!r}")
    starter_stub = f"{starter_code}\n    pass\n" if starter_code.strip() else ""
    return f"""{starter_stub}
import sys as _pbt_sys
_pbt_sys.path.insert(0, {runtime_dir!r})
from checker_proxy import call_candidate as {entry_point}
"""


def validate_pbt_script(code: str, entry_point: str, max_examples: int) -> None:
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        raise ValueError(f"generated PBT script has invalid syntax: {error}") from error
    if any(
        isinstance(node, ast.AsyncFunctionDef) and node.name.startswith("test_")
        for node in tree.body
    ):
        raise ValueError("generated PBT tests must be synchronous")
    tests = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    if not 1 <= len(tests) <= 10:
        raise ValueError(f"generated PBT script must define 1-10 tests, found {len(tests)}")
    if not any(isinstance(node, ast.Name) and node.id == entry_point for node in ast.walk(tree)):
        raise ValueError(f"generated PBT script never references entry point {entry_point!r}")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [alias.name.split(".")[0] for alias in node.names]
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module.split(".")[0])
            blocked = PROHIBITED_IMPORTS.intersection(modules)
            if blocked:
                raise ValueError(f"generated PBT script imports prohibited modules: {sorted(blocked)}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in PROHIBITED_CALLS:
                raise ValueError(f"generated PBT script calls prohibited builtin {node.func.id!r}")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == entry_point:
            raise ValueError("generated PBT script must not replace the candidate entry point")
        if isinstance(node, ast.Attribute) and node.attr in {"skip", "skipif", "xfail"}:
            raise ValueError(f"generated PBT script may not use pytest.{node.attr}")
        if isinstance(node, ast.Name) and node.id in {"skip", "skipif", "xfail", "importorskip"}:
            raise ValueError(f"generated PBT script may not use {node.id}")
    for test in tests:
        decorator_names = {
            decorator.func.id
            for decorator in test.decorator_list
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name)
        }
        if "given" not in decorator_names:
            raise ValueError(f"generated test {test.name!r} is missing @given")
        settings_calls = [
            decorator
            for decorator in test.decorator_list
            if isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Name)
            and decorator.func.id == "settings"
        ]
        if len(settings_calls) != 1:
            raise ValueError(f"generated test {test.name!r} must have exactly one @settings")
        configured = next(
            (keyword.value for keyword in settings_calls[0].keywords if keyword.arg == "max_examples"),
            None,
        )
        if not isinstance(configured, ast.Constant) or not isinstance(configured.value, int):
            raise ValueError(f"generated test {test.name!r} must use a literal max_examples")
        if not 1 <= configured.value <= max_examples:
            raise ValueError(
                f"generated test {test.name!r} max_examples={configured.value} exceeds budget {max_examples}"
            )
