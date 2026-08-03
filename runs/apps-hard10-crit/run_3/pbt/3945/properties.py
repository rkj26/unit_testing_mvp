import random

def prop_output_shape_and_range(run, x):
    """PROPERTY: Output must have n lines, m ints per line, each integer >=1."""
    out = run(x).strip()
    lines = out.splitlines()
    # Parse n,m from input
    first_line = x.split('\n')[0]
    n_str, m_str = first_line.split()
    n, m = int(n_str), int(m_str)
    # Check number of lines
    assert len(lines) == n, f"Expected {n} lines, got {len(lines)}"
    for i, line in enumerate(lines):
        parts = line.strip().split()
        assert len(parts) == m, f"Line {i}: expected {m} numbers, got {len(parts)}"
        for p in parts:
            val = int(p)
            assert val >= 1, f"Value {val} at ({i}, {parts.index(p)}) is less than 1"

def prop_row_permutation_consistency(run, x):
    """PROPERTY: Permuting rows permutes outputs identically."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m = int(first[0]), int(first[1])
    matrix_lines = lines[1:1+n]
    matrix = [list(map(int, line.split())) for line in matrix_lines]
    # Create a random permutation of rows
    perm = list(range(n))
    random.Random(42).shuffle(perm)  # deterministic shuffle
    permuted_input = f"{n} {m}\n"
    for i in range(n):
        permuted_input += " ".join(map(str, matrix[perm[i]])) + "\n"
    # Run both
    out_orig = run(x).strip()
    out_perm = run(permuted_input).strip()
    mat_orig = [list(map(int, line.split())) for line in out_orig.splitlines()]
    mat_perm = [list(map(int, line.split())) for line in out_perm.splitlines()]
    # Check that outputs are permuted the same way
    for i in range(n):
        orig_row = mat_orig[i]
        perm_row = mat_perm[perm[i]]
        assert orig_row == perm_row, f"Row {i} vs permuted row {perm[i]} mismatch"

def prop_column_permutation_consistency(run, x):
    """PROPERTY: Permuting columns permutes outputs identically."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m = int(first[0]), int(first[1])
    matrix_lines = lines[1:1+n]
    matrix = [list(map(int, line.split())) for line in matrix_lines]
    # Random permutation of columns
    perm = list(range(m))
    random.Random(43).shuffle(perm)
    permuted_input = f"{n} {m}\n"
    for i in range(n):
        row = [matrix[i][perm[j]] for j in range(m)]
        permuted_input += " ".join(map(str, row)) + "\n"
    # Run both
    out_orig = run(x).strip()
    out_perm = run(permuted_input).strip()
    mat_orig = [list(map(int, line.split())) for line in out_orig.splitlines()]
    mat_perm = [list(map(int, line.split())) for line in out_perm.splitlines()]
    # Check column permutation
    for i in range(n):
        for j in range(m):
            assert mat_orig[i][j] == mat_perm[i][perm[j]], f"Column mismatch at ({i},{j})"