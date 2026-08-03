def prop_output_format_and_bounds(run, x):
    """PROPERTY: Output must be a single integer -1 or nonnegative, fitting spec."""
    out = run(x).strip()
    # Must be a single integer
    lines = out.splitlines()
    assert len(lines) == 1, "Output must be exactly one line"
    val_str = lines[0].strip()
    assert val_str.lstrip('-').isdigit(), "Output must be an integer"
    val = int(val_str)
    # Either -1 or >= 0
    assert val == -1 or val >= 0, "Output must be -1 or nonnegative integer"
    # Upper bound: worst case every cell black, we could put a north magnet in each black cell.
    # But we don't know n,m here; we can only check it's not obviously huge.
    # Since n,m <= 1000, max black cells <= 1e6. If val > 1e6, suspicious.
    if val > 1_000_000:
        # Still possible if n*m > 1e6, but given constraints n,m <= 1000, n*m <= 1e6.
        # So if val > 1e6, it's impossible because we can't have more north magnets than cells.
        # Actually, spec allows multiple magnets per cell, so in principle we could have more north magnets than cells.
        # But minimal number won't exceed number of black cells (since each black cell might need its own north magnet).
        # So safe bound: val <= n*m (but we don't have n,m here). We'll skip numeric bound here.
        pass
    # No extra whitespace check
    assert out == val_str + "\n" or out == val_str, "No extra whitespace except maybe newline"

def prop_no_black_cells_implies_zero(run, x):
    """PROPERTY: If grid has no black cells, answer must be 0."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n_m = lines[0].split()
    if len(n_m) != 2:
        return
    n, m = map(int, n_m)
    has_black = any('#' in row for row in lines[1:1+n])
    if not has_black:
        out = run(x).strip()
        val = int(out)
        assert val == 0, "If no black cells, minimum north magnets must be 0"

def prop_transpose_symmetry(run, x):
    """PROPERTY: Transposing input (swap rows/columns) yields same output."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n_m = lines[0].split()
    if len(n_m) != 2:
        return
    n, m = map(int, n_m)
    grid = lines[1:1+n]
    # Build transposed input
    transposed_grid = [''.join(grid[i][j] for i in range(n)) for j in range(m)]
    transposed_input = f"{m} {n}\n" + "\n".join(transposed_grid) + "\n"
    out1 = run(x).strip()
    out2 = run(transposed_input).strip()
    # Both must be same integer (or both -1)
    assert out1 == out2, "Transposing grid should not change answer"

def prop_adding_south_magnets_does_not_require_more_north(run, x):
    """PROPERTY: Changing '.' to '#' cannot decrease required north magnets (monotonicity in black cells)."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n_m = lines[0].split()
    if len(n_m) != 2:
        return
    n, m = map(int, n_m)
    grid = lines[1:1+n]
    # Find a white cell to turn black, if any
    for i in range(n):
        for j in range(m):
            if grid[i][j] == '.':
                new_grid = list(grid)
                row = list(new_grid[i])
                row[j] = '#'
                new_grid[i] = ''.join(row)
                new_input = f"{n} {m}\n" + "\n".join(new_grid) + "\n"
                out_orig = run(x).strip()
                out_new = run(new_input).strip()
                if out_orig == "-1":
                    # If original impossible, new might be possible or impossible
                    pass
                else:
                    orig_val = int(out_orig)
                    if out_new != "-1":
                        new_val = int(out_new)
                        # More black cells cannot require fewer north magnets
                        assert new_val >= orig_val, "Adding black cells should not decrease required north magnets"
                return  # Only test one change to keep test fast
    # If no white cell, skip

def prop_row_column_south_requirement_unsatisfiable(run, x):
    """PROPERTY: If a row is all white but another row has black, then impossible (-1)."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n_m = lines[0].split()
    if len(n_m) != 2:
        return
    n, m = map(int, n_m)
    grid = lines[1:1+n]
    # Condition: there exists at least one black cell somewhere in grid,
    # and there exists a row with no black cells.
    has_black_anywhere = any('#' in row for row in grid)
    row_without_black = any('#' not in row for row in grid)
    col_without_black = any(all(grid[i][j] != '#' for i in range(n)) for j in range(m))
    # If there's a row with no black cells, then to satisfy "south magnet in every row",
    # we must place a south magnet in that row. But that south magnet would be in a white cell,
    # which could allow north magnet to reach that white cell (since south is immovable and north can move towards it).
    # Actually spec: white cell means impossible for north magnet to occupy it after any sequence.
    # If a south magnet is in a white cell, then a north magnet could move towards it and occupy that white cell — violation.
    # Therefore, if a white row exists and there is any black cell anywhere, impossible.
    # Similarly for columns.
    # But careful: if entire grid is white, answer is 0 (tested in another property).
    if has_black_anywhere and (row_without_black or col_without_black):
        out = run(x).strip()
        assert out == "-1", "If any all-white row/column exists while some black cell exists, should be impossible"