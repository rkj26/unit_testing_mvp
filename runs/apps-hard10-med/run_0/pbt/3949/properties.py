def prop_output_format_and_range(run, x):
    """PROPERTY: Output is a single integer >= -1."""
    out = run(x).strip()
    # Must be able to parse as int
    val = int(out)
    # Must be >= -1
    assert val >= -1, f"Output {val} is less than -1"

def prop_no_black_cells_zero(run, x):
    """PROPERTY: If grid has no '#', output must be 0."""
    lines = x.strip().splitlines()
    if not lines:
        return
    # First line: n m
    # Rest: grid rows
    grid = lines[1:]
    # Check if any '#' appears
    has_black = any('#' in row for row in grid)
    if not has_black:
        out = run(x).strip()
        val = int(out)
        assert val == 0, f"Expected 0 for no black cells, got {val}"

def prop_some_black_cells_not_zero(run, x):
    """PROPERTY: If grid has at least one '#', output cannot be 0."""
    lines = x.strip().splitlines()
    if not lines:
        return
    grid = lines[1:]
    has_black = any('#' in row for row in grid)
    if has_black:
        out = run(x).strip()
        val = int(out)
        assert val != 0, f"Output is 0 but grid has black cells"

def prop_transpose_invariance(run, x):
    """PROPERTY: Transposing the grid does not change the output."""
    lines = x.strip().splitlines()
    if not lines:
        return
    # Parse n, m
    first = lines[0].split()
    if len(first) != 2:
        return  # malformed input, skip
    n, m = map(int, first)
    grid = lines[1:]
    if len(grid) != n:
        return  # malformed
    # Build transposed grid
    transposed = []
    for j in range(m):
        row = ''.join(grid[i][j] for i in range(n))
        transposed.append(row)
    # New first line: m n
    new_input = f"{m} {n}\n" + "\n".join(transposed)
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    # Both must be integers, compare
    val1 = int(out1)
    val2 = int(out2)
    assert val1 == val2, f"Output {val1} for original != {val2} for transpose"

def prop_row_reversal_invariance(run, x):
    """PROPERTY: Reversing the order of rows does not change the output."""
    lines = x.strip().splitlines()
    if not lines:
        return
    first = lines[0].split()
    if len(first) != 2:
        return
    n, m = map(int, first)
    grid = lines[1:]
    if len(grid) != n:
        return
    # Reverse rows
    reversed_grid = list(reversed(grid))
    new_input = f"{n} {m}\n" + "\n".join(reversed_grid)
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    val1 = int(out1)
    val2 = int(out2)
    assert val1 == val2, f"Output {val1} for original != {val2} for row-reversed"