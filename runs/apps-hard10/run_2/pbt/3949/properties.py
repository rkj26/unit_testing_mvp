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

def prop_transpose_invariance(run, x):
    """PROPERTY: Transposing the grid (swap rows/cols) does not change feasibility."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return True
    parts = lines[0].split()
    if len(parts) < 2:
        return True
    n, m = map(int, parts)
    grid_lines = lines[1:1+n]
    # Build transposed input
    transposed_grid = [''.join(grid_lines[r][c] for r in range(n)) for c in range(m)]
    transposed_input = f"{m} {n}\n" + "\n".join(transposed_grid) + "\n"
    out1 = run(x)
    out2 = run(transposed_input)
    val1 = int(out1.strip().splitlines()[0])
    val2 = int(out2.strip().splitlines()[0])
    # Feasibility (output -1 vs not -1) must be the same
    feasible1 = (val1 != -1)
    feasible2 = (val2 != -1)
    assert feasible1 == feasible2, "Transposing should not change feasibility"
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

def prop_adding_black_cells_does_not_increase_min_north(run, x):
    """PROPERTY: Changing a white cell to black cannot decrease the minimal north count (metamorphic)."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return True
    parts = lines[0].split()
    if len(parts) < 2:
        return True
    n, m = map(int, parts)
    grid = [list(row) for row in lines[1:1+n]]
    # Find first white cell
    for i in range(n):
        for j in range(m):
            if grid[i][j] == '.':
                # Create modified input with that cell turned black
                new_grid = [list(row) for row in lines[1:1+n]]
                new_grid[i][j] = '#'
                new_input = f"{n} {m}\n" + "\n".join(''.join(r) for r in new_grid) + "\n"
                out_orig = run(x)
                out_new = run(new_input)
                val_orig = int(out_orig.strip().splitlines()[0])
                val_new = int(out_new.strip().splitlines()[0])
                # If original is infeasible, new could be anything, skip
                if val_orig == -1:
                    return True
                # Otherwise, new must be feasible and val_new >= 0
                # Minimal north magnets should not decrease when adding black cells
                # Actually, adding black cells could require more north magnets or same,
                # but never fewer. Also, if new is infeasible, val_new = -1, which is fine.
                # But if both feasible, val_new >= val_orig.
                if val_new != -1:
                    assert val_new >= val_orig, "Adding a black cell should not reduce minimal north magnets"
                return True
    # If no white cell, trivially true
    return True