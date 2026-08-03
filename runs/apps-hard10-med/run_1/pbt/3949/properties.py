import re

def prop_output_format(run, x):
    """PROPERTY: Output is a single integer, either -1 or a non-negative integer."""
    out = run(x).strip()
    try:
        val = int(out)
    except ValueError:
        assert False, f"Output is not an integer: {out}"
    assert val == -1 or val >= 0, f"Output integer {val} is not -1 and not non-negative"

def prop_no_black_implies_zero(run, x):
    """PROPERTY: If grid has no black cells, output must be 0."""
    lines = x.strip().splitlines()
    if not lines:
        return
    first = lines[0].split()
    if len(first) != 2:
        return
    n, m = map(int, first)
    grid = lines[1:1+n]
    black_count = sum(row.count('#') for row in grid)
    if black_count == 0:
        out = run(x).strip()
        try:
            val = int(out)
        except ValueError:
            assert False, f"Output not integer: {out}"
        assert val == 0, f"Expected 0 for no black cells, got {val}"

def prop_zero_implies_no_black(run, x):
    """PROPERTY: If output is 0, then grid has no black cells."""
    out = run(x).strip()
    try:
        val = int(out)
    except ValueError:
        return
    if val == 0:
        lines = x.strip().splitlines()
        if not lines:
            return
        first = lines[0].split()
        if len(first) != 2:
            return
        n, m = map(int, first)
        grid = lines[1:1+n]
        black_count = sum(row.count('#') for row in grid)
        assert black_count == 0, f"Output is 0 but grid has {black_count} black cells"

def prop_transpose_symmetry(run, x):
    """PROPERTY: Transposing the grid (swap rows and columns) does not change the answer."""
    lines = x.strip().splitlines()
    if not lines:
        return
    first = lines[0].split()
    if len(first) != 2:
        return
    n, m = map(int, first)
    grid = lines[1:1+n]
    if len(grid) != n:
        return
    new_grid = [''.join(grid[i][j] for i in range(n)) for j in range(m)]
    new_input = f"{m} {n}\n" + "\n".join(new_grid) + "\n"
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    try:
        val1 = int(out1)
        val2 = int(out2)
    except ValueError:
        return
    assert val1 == val2, f"Transpose symmetry violated: {val1} vs {val2}"

def prop_row_reversal_symmetry(run, x):
    """PROPERTY: Reversing the order of rows does not change the answer."""
    lines = x.strip().splitlines()
    if not lines:
        return
    first = lines[0].split()
    if len(first) != 2:
        return
    n, m = map(int, first)
    grid = lines[1:1+n]
    if len(grid) != n:
        return
    reversed_grid = list(reversed(grid))
    new_input = f"{n} {m}\n" + "\n".join(reversed_grid) + "\n"
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    try:
        val1 = int(out1)
        val2 = int(out2)
    except ValueError:
        return
    assert val1 == val2, f"Row reversal symmetry violated: {val1} vs {val2}"