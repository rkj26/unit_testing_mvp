import ast
import pytest
from pbt_runner.smoke import verify_exact_subset


def extract(source):
    lines = source.splitlines(keepends=True)
    return {node.name: (node.lineno-1, node.end_lineno, ''.join(lines[node.lineno-1:node.end_lineno]))
            for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}


A = 'def test_a(run,x):\n    assert run(x) == 1\n'
B = 'def test_b(run,x):\n    assert run(x) == 2\n'
C = 'def test_c(run,x):\n    assert run(x) == 3\n'


def test_deleting_first_or_middle_changes_offsets_not_function_text():
    assert verify_exact_subset(A+B+C, A+C, extract)
    assert verify_exact_subset(A+B+C, B+C, extract)


@pytest.mark.parametrize('selected', [C+A, A+C.replace('== 3', '== 4'), A.replace('test_a', 'test_unknown'), ''])
def test_rewrite_reorder_unknown_and_empty_are_rejected(selected):
    with pytest.raises(ValueError, match='exact-text subset'):
        verify_exact_subset(A+B+C, selected, extract)
