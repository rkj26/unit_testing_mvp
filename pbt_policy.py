"""Pure validation and source-building helpers for generated PBT suites."""

from __future__ import annotations

import ast
import keyword


ALLOWED_IMPORTS = {
    "collections",
    "datetime",
    "decimal",
    "fractions",
    "functools",
    "hypothesis",
    "itertools",
    "json",
    "math",
    "operator",
    "pytest",
    "re",
    "statistics",
}
PROHIBITED_CALLS = {
    "__import__",
    "breakpoint",
    "compile",
    "eval",
    "exit",
    "exec",
    "getattr",
    "globals",
    "input",
    "locals",
    "open",
    "quit",
    "setattr",
    "seed",
    "vars",
}
PROHIBITED_IMPORT_NAMES = {
    "hypothesis": {"reproduce_failure", "seed"},
    "operator": {"attrgetter", "methodcaller"},
    "pytest": {
        "ExitCode",
        "console_main",
        "exit",
        "importorskip",
        "main",
        "skip",
        "skipif",
        "xfail",
    },
}
PROHIBITED_ATTRIBUTES = {
    "MonkeyPatch",
    "_setattr",
    "attrgetter",
    "console_main",
    "exit",
    "importorskip",
    "load_profile",
    "main",
    "methodcaller",
    "register_profile",
    "reproduce_failure",
    "seed",
    "setattr",
    "skip",
    "skipif",
    "xfail",
}
PROTECTED_DECORATORS = {"given", "settings"}
PROTECTED_PYTEST_HELPERS = {"approx", "raises"}
PROTECTED_BINDINGS = PROTECTED_DECORATORS | PROTECTED_PYTEST_HELPERS
ALLOWED_HYPOTHESIS_IMPORTS = {"given", "settings", "strategies"}
ALLOWED_PYTEST_ATTRIBUTES = {"approx", "raises"}
PROHIBITED_PYTEST_BINDINGS = {"pytest_plugins", "pytestmark"}
RUNTIME_PREFIX = "_control_"
PROTECTED_INTERPRETER_NAMES = {
    "SystemExit",
    "__file__",
    "__name__",
    "__package__",
    "__spec__",
}


def candidate_module_code(starter_code: str, submitted_code: str) -> str:
    starter_stub = f"{starter_code}\n    pass\n" if starter_code.strip() else ""
    return f"{starter_stub}\n{submitted_code}\n"


def checker_prelude(starter_code: str, entry_point: str, runtime_dir: str) -> str:
    if not entry_point.isidentifier() or keyword.iskeyword(entry_point):
        raise ValueError(f"invalid Python entry point: {entry_point!r}")
    starter_stub = f"{starter_code}\n    pass\n" if starter_code.strip() else ""
    return f"""{starter_stub}
import sys as _control_sys
_control_sys.path.insert(0, {runtime_dir!r})
from checker_proxy import call_candidate as {entry_point}

del _control_sys
"""


def pbt_checker_prelude(entry_point: str) -> str:
    """Return a checker prelude that exposes only the candidate RPC function."""
    if not entry_point.isidentifier() or keyword.iskeyword(entry_point):
        raise ValueError(f"invalid Python entry point: {entry_point!r}")
    return f"""import os as _control_os
import sys as _control_sys
_control_sys.path.insert(0, _control_os.path.dirname(__file__))
from checker_proxy import call_candidate as {entry_point}

del _control_os
del _control_sys
"""


def pbt_runtime_runner(execution_seed: int, attestation_nonce: str) -> str:
    """Return a deterministic pytest runner with semantic PBT integrity checks."""
    if isinstance(execution_seed, bool) or not isinstance(execution_seed, int):
        raise ValueError("Hypothesis execution seed must be an integer")
    if len(attestation_nonce) != 64 or any(
        character not in "0123456789abcdef" for character in attestation_nonce
    ):
        raise ValueError("PBT attestation nonce must be 64 lowercase hex characters")
    return f"""
if __name__ == "__main__":
    import sys as _control_sys
    import pytest as _control_pytest
    from hypothesis import HealthCheck as _control_health_check
    from hypothesis import settings as _control_settings
    from checker_proxy import candidate_call_count as _control_candidate_call_count

    _control_settings.register_profile(
        "control_deterministic",
        deadline=None,
        database=None,
        suppress_health_check=[_control_health_check.too_slow],
    )
    _control_settings.load_profile("control_deterministic")

    class _control_integrity_plugin:
        def __init__(self):
            self.missing_calls = []
            self.skipped = []
            self.xfailed = []

        @_control_pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_call(self, item):
            before = _control_candidate_call_count()
            yield
            if _control_candidate_call_count() <= before:
                self.missing_calls.append(item.nodeid)

        def pytest_runtest_logreport(self, report):
            if report.skipped:
                if hasattr(report, "wasxfail"):
                    self.xfailed.append(report.nodeid)
                else:
                    self.skipped.append(report.nodeid)

        def pytest_sessionfinish(self, session, exitstatus):
            problems = []
            if self.missing_calls:
                problems.append("tests without candidate RPC calls: " + repr(self.missing_calls))
            if self.skipped:
                problems.append("skipped tests: " + repr(self.skipped))
            if self.xfailed:
                problems.append("xfailed tests: " + repr(self.xfailed))
            if session.testscollected == 0:
                problems.append("no property tests were collected")
            if problems:
                print("PBT integrity failure: " + "; ".join(problems), file=_control_sys.stderr)
                session.exitstatus = _control_pytest.ExitCode.TESTS_FAILED

    _control_plugin = _control_integrity_plugin()
    _control_exit_code = _control_pytest.main(
        [
            __file__,
            "-q",
            "--tb=short",
            "-p",
            "no:cacheprovider",
            "--hypothesis-seed={execution_seed}",
        ],
        plugins=[_control_plugin],
    )
    _control_sys.stdout.write(
        "\n__CONTROL_PBT_ATTESTATION_{attestation_nonce}__="
        f"{{_control_exit_code.value}}\n"
    )
    _control_sys.stdout.flush()
    raise SystemExit(_control_exit_code)
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
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    if not 1 <= len(tests) <= 10:
        raise ValueError(
            f"generated PBT script must define 1-10 tests, found {len(tests)}"
        )
    protected_binding_names = {
        entry_point,
        *PROTECTED_BINDINGS,
        *PROHIBITED_CALLS,
        *PROTECTED_INTERPRETER_NAMES,
        *PROHIBITED_PYTEST_BINDINGS,
    }
    imported_hypothesis_decorators: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.level:
                raise ValueError("generated PBT script may not use relative imports")
            if any(alias.name == "*" for alias in node.names):
                raise ValueError("generated PBT script may not use wildcard imports")
            modules = (
                [node.module.split(".")[0]]
                if isinstance(node, ast.ImportFrom) and node.module
                else [alias.name.split(".")[0] for alias in node.names]
            )
            blocked = sorted(set(modules).difference(ALLOWED_IMPORTS))
            if blocked:
                raise ValueError(
                    f"generated PBT script imports non-allowlisted modules: {blocked}"
                )
            if isinstance(node, ast.ImportFrom) and node.module:
                root_module = node.module.split(".")[0]
                if root_module == "hypothesis" and any(
                    alias.name not in ALLOWED_HYPOTHESIS_IMPORTS for alias in node.names
                ):
                    raise ValueError(
                        "generated PBT script imports unsupported Hypothesis names"
                    )
                if root_module == "pytest" and any(
                    alias.name not in PROTECTED_PYTEST_HELPERS
                    or alias.asname is not None
                    for alias in node.names
                ):
                    raise ValueError(
                        "generated PBT script may import only unaliased pytest "
                        "raises/approx helpers"
                    )
                blocked_names = sorted(
                    alias.name
                    for alias in node.names
                    if alias.name in PROHIBITED_IMPORT_NAMES.get(root_module, set())
                )
                if blocked_names:
                    raise ValueError(
                        f"generated PBT script imports prohibited names: {blocked_names}"
                    )
                if root_module == "hypothesis":
                    for alias in node.names:
                        if alias.name in PROTECTED_DECORATORS and alias.asname is None:
                            imported_hypothesis_decorators.add(alias.name)
            for alias in node.names:
                bound_name = alias.asname or alias.name.split(".")[0]
                if bound_name.startswith(RUNTIME_PREFIX):
                    raise ValueError(
                        "generated PBT script may not bind reserved runtime names"
                    )
                if (
                    isinstance(node, ast.Import)
                    and alias.name.split(".")[0] == "hypothesis"
                ):
                    raise ValueError(
                        "generated PBT script must import Hypothesis names directly"
                    )
                if (
                    isinstance(node, ast.Import)
                    and alias.name.split(".")[0] == "pytest"
                    and alias.asname is not None
                ):
                    raise ValueError("generated PBT script may not alias pytest")
                if bound_name in {
                    entry_point,
                    *PROHIBITED_CALLS,
                    *PROTECTED_INTERPRETER_NAMES,
                    *PROHIBITED_PYTEST_BINDINGS,
                }:
                    raise ValueError(
                        f"generated PBT script imports protected name {bound_name!r}"
                    )
                if bound_name in PROTECTED_BINDINGS and not (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    and (
                        (
                            node.module.split(".")[0] == "hypothesis"
                            and alias.name in PROTECTED_DECORATORS
                        )
                        or (
                            node.module.split(".")[0] == "pytest"
                            and alias.name in PROTECTED_PYTEST_HELPERS
                        )
                    )
                    and alias.name == bound_name
                    and alias.asname is None
                ):
                    raise ValueError(
                        f"generated PBT script must not shadow {bound_name!r}"
                    )
        if isinstance(node, ast.Name) and node.id in PROHIBITED_CALLS:
            raise ValueError(
                f"generated PBT script uses prohibited builtin {node.id!r}"
            )
        if isinstance(node, ast.Name) and node.id.startswith(RUNTIME_PREFIX):
            raise ValueError("generated PBT script may not use reserved runtime names")
        if isinstance(node, ast.Name) and node.id in PROTECTED_INTERPRETER_NAMES:
            raise ValueError(
                f"generated PBT script may not use interpreter control {node.id!r}"
            )
        if isinstance(node, ast.Name) and node.id == "pytest":
            parent = parents.get(node)
            if not (
                isinstance(parent, ast.Attribute)
                and parent.value is node
                and parent.attr in ALLOWED_PYTEST_ATTRIBUTES
            ):
                raise ValueError(
                    "generated PBT script may use pytest only for raises or approx"
                )
        if (
            isinstance(node, ast.Name)
            and node.id in {entry_point, *PROTECTED_BINDINGS}
            and not isinstance(node.ctx, ast.Load)
        ):
            raise ValueError(
                f"generated PBT script must not rebind protected name {node.id!r}"
            )
        if isinstance(node, ast.Name) and node.id in PROHIBITED_PYTEST_BINDINGS:
            raise ValueError(
                f"generated PBT script may not define pytest control {node.id!r}"
            )
        if isinstance(node, (ast.Global, ast.Nonlocal)) and any(
            name in protected_binding_names for name in node.names
        ):
            raise ValueError("generated PBT script may not mutate protected globals")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name.startswith(RUNTIME_PREFIX):
                raise ValueError(
                    "generated PBT script may not define reserved runtime names"
                )
            if node.name in protected_binding_names:
                raise ValueError(
                    f"generated PBT script must not define protected name {node.name!r}"
                )
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            arguments = [
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
            ]
            if node.args.vararg:
                arguments.append(node.args.vararg)
            if node.args.kwarg:
                arguments.append(node.args.kwarg)
            if any(argument.arg in protected_binding_names for argument in arguments):
                raise ValueError(
                    "generated PBT script may not shadow protected names in arguments"
                )
            if any(argument.arg.startswith(RUNTIME_PREFIX) for argument in arguments):
                raise ValueError(
                    "generated PBT script may not bind reserved runtime names"
                )
        string_bindings = []
        if isinstance(node, ast.ExceptHandler) and node.name:
            string_bindings.append(node.name)
        if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            string_bindings.append(node.name)
        if isinstance(node, ast.MatchMapping) and node.rest:
            string_bindings.append(node.rest)
        if any(name in protected_binding_names for name in string_bindings):
            raise ValueError(
                "generated PBT script may not bind protected interpreter names"
            )
        if any(name.startswith(RUNTIME_PREFIX) for name in string_bindings):
            raise ValueError("generated PBT script may not bind reserved runtime names")
        if isinstance(node, ast.Attribute) and node.attr in PROHIBITED_ATTRIBUTES:
            raise ValueError(
                f"generated PBT script may not use pytest.{node.attr} or an equivalent "
                "prohibited attribute"
            )
        if isinstance(node, ast.Attribute) and not isinstance(node.ctx, ast.Load):
            raise ValueError(
                "generated PBT script may not mutate module or object attributes"
            )
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("generated PBT script may not access dunder attributes")
        if isinstance(node, ast.Name) and node.id == "__builtins__":
            raise ValueError("generated PBT script may not access __builtins__")
        if isinstance(node, ast.Name) and node.id in {
            "skip",
            "skipif",
            "xfail",
            "importorskip",
        }:
            raise ValueError(f"generated PBT script may not use {node.id}")
    missing_decorator_imports = PROTECTED_DECORATORS.difference(
        imported_hypothesis_decorators
    )
    if missing_decorator_imports:
        raise ValueError(
            "generated PBT script must import unaliased Hypothesis decorators: "
            f"{sorted(missing_decorator_imports)}"
        )
    for test in tests:
        decorators = []
        for decorator in test.decorator_list:
            if not (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Name)
                and decorator.func.id in PROTECTED_DECORATORS
            ):
                raise ValueError(
                    f"generated test {test.name!r} uses an unsupported decorator"
                )
            decorators.append(decorator)
        decorator_names = [decorator.func.id for decorator in decorators]
        if decorator_names.count("given") != 1:
            raise ValueError(
                f"generated test {test.name!r} must have exactly one @given"
            )
        given_call = next(
            decorator for decorator in decorators if decorator.func.id == "given"
        )
        if not given_call.args and not given_call.keywords:
            raise ValueError(
                f"generated test {test.name!r} must generate at least one argument"
            )
        if any(
            isinstance(argument, ast.Starred) for argument in given_call.args
        ) or any(item.arg is None for item in given_call.keywords):
            raise ValueError(
                f"generated test {test.name!r} may not expand dynamic @given arguments"
            )
        settings_calls = [
            decorator for decorator in decorators if decorator.func.id == "settings"
        ]
        if len(settings_calls) != 1:
            raise ValueError(
                f"generated test {test.name!r} must have exactly one @settings"
            )
        if settings_calls[0].args or any(
            item.arg is None for item in settings_calls[0].keywords
        ):
            raise ValueError(
                f"generated test {test.name!r} must use explicit @settings keywords"
            )
        keyword_names = [item.arg for item in settings_calls[0].keywords]
        if len(keyword_names) != len(set(keyword_names)):
            raise ValueError(f"generated test {test.name!r} repeats @settings keywords")
        configured_names = {keyword.arg for keyword in settings_calls[0].keywords}
        blocked_settings = configured_names.intersection(
            {
                "database",
                "deadline",
                "derandomize",
                "phases",
                "suppress_health_check",
            }
        )
        if blocked_settings:
            raise ValueError(
                f"generated test {test.name!r} overrides deterministic settings: "
                f"{sorted(blocked_settings)}"
            )
        configured = next(
            (
                keyword.value
                for keyword in settings_calls[0].keywords
                if keyword.arg == "max_examples"
            ),
            None,
        )
        if (
            not isinstance(configured, ast.Constant)
            or type(configured.value) is not int
        ):
            raise ValueError(
                f"generated test {test.name!r} must use a literal max_examples"
            )
        if not 1 <= configured.value <= max_examples:
            raise ValueError(
                f"generated test {test.name!r} max_examples={configured.value} exceeds budget {max_examples}"
            )
        if not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == entry_point
            for node in ast.walk(test)
        ):
            raise ValueError(
                f"generated test {test.name!r} never calls entry point {entry_point!r}"
            )
