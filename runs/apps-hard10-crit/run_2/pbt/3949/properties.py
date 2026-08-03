def prop_output_format(run, x):
    """PROPERTY: Output must be a single integer (possibly -1) followed by newline."""
    out = run(x)
    lines = out.strip().splitlines()
    assert len(lines) == 1, "Output must be exactly one line"
    val_str = lines[0].strip()
    assert val_str.lstrip('-').isdigit(), "Output must be an integer"
    val = int(val_str)
    assert val == -1 or val >= 0, "If not -1, output must be non-negative"
    return True

def prop_no_black_cells_implies_zero_or_minus_one(run, x):
    """PROPERTY: If grid has no black cells, output is 0 or -1 (never positive)."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return True
    n_m = lines[0].split()
    if len(n_m) < 2:
        return True
    try:
        n, m = map(int, n_m)
    except:
        return True
    has_black = any('#' in row for row in lines[1:1+n])
    if not has_black:
        out = run(x)
        val = int(out.strip().splitlines()[0])
        assert val == 0 or val == -1, "With no black cells, output must be 0 or -1"
    return True

def prop_row_column_white_consistency(run, x):
    """PROPERTY: If a row is all white, there must be at least one black cell in its column for feasibility."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return True
    parts = lines[0].split()
    if len(parts) < 2:
        return True
    n, m = map(int, parts)
    grid = lines[1:1+n]
    # Check if any row is all white
    all_white_rows = [i for i in range(n) if '#' not in grid[i]]
    # Check if any column is all white
    all_white_cols = [j for j in range(m) if all(grid[i][j] == '.' for i in range(n))]
    # If there exists both an all-white row and an all-white column, problem is impossible
    # because that cell (row, col) is white, but rule 1 requires south magnet there,
    # and a south magnet in a white cell would allow north magnet there via zero-move.
    if all_white_rows and all_white_cols:
        out = run(x)
        val = int(out.strip().splitlines()[0])
        assert val == -1, "If there is an all-white row and an all-white column, must output -1"
    return True