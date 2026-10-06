"""Versioned startup contract; never changes frozen research prompts or repairs outputs."""
import ast
import builtins
from contextlib import contextmanager
import symtable

VERSION = 'self-contained-v1'
INSTRUCTIONS = '''EXECUTABLE TEST CONTRACT (self-contained-v1)
The candidate implementation and your tests execute in SEPARATE Python namespaces.
Imports visible in the task statement or candidate code are NOT available to your tests.
Each returned source must contain exactly one self-contained test function. Put every
required import and helper INSIDE that function. For example, if that function uses
pd.DataFrame, put `import pandas as pd` inside it; np requires its own `import numpy as np`.
Use only dependencies permitted by the task specification. Do not depend on aliases,
variables, helpers, or imports from another test or the candidate implementation.
Before returning, check that every name is a parameter, local definition/import, or
Python builtin. Keep all existing assertion and run(x) constraints. Do not weaken
assertions or suppress errors to make a test pass.

'''


def unresolved_names(source):
    """Check unbound global references without executing or rewriting code.

    Symbol tables handle imports, nested closures and comprehensions. This does not
    detect every possible dynamic Python error; Docker execution remains required.
    """
    if not source:
        return []
    try:
        errors = []
        for node in ast.parse(source).body:
            if not isinstance(node, ast.FunctionDef):
                errors.append('suite contains a non-function top-level statement')
                continue
            table = symtable.symtable(ast.unparse(node), '<generated-test>', 'exec')
            missing = set()
            def walk(scope):
                for symbol in scope.get_symbols():
                    if symbol.is_referenced() and symbol.is_global() and symbol.get_name() not in vars(builtins):
                        missing.add(symbol.get_name())
                for child in scope.get_children():
                    walk(child)
            for child in table.get_children():
                walk(child)
            if missing:
                errors.append(f"{node.name}: unresolved names: {', '.join(sorted(missing))}")
        return errors
    except (SyntaxError, ValueError) as error:
        return [f'invalid test source: {type(error).__name__}']


@contextmanager
def install(version):
    if version == 'legacy':
        yield
        return
    if version != VERSION:
        raise ValueError('unknown test contract')
    from pipeline.protocols.unit_testing import UnitTesting
    from pipeline.protocols import second_revision
    baseline_prompt = UnitTesting._prompt
    revision_prompt = second_revision.revision_prompt
    # Render before _call records the prompt, preserving exact sent-prompt provenance.
    UnitTesting._prompt = lambda self, *a, **kw: INSTRUCTIONS + baseline_prompt(self, *a, **kw)
    second_revision.revision_prompt = lambda *a, **kw: INSTRUCTIONS + revision_prompt(*a, **kw)
    try:
        yield
    finally:
        UnitTesting._prompt = baseline_prompt
        second_revision.revision_prompt = revision_prompt
