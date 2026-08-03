def prop_output_format_and_range(run, x):
    """PROPERTY: Output must be a single integer in [-1, n*m] range."""
    out = run(x)
    lines = out.strip().splitlines()
    assert len(lines) > 0, "No output"
    first_line = lines[0].strip()
    assert first_line.isdigit() or (first_line.startswith('-') and first_line[1:].isdigit()), f"Not an integer: {first_line}"
    val = int(first_line)
    n_str = x.split()[0]
    n = int(n_str) if n_str.isdigit() else 0
    m_str = x.split()[1]
    m = int(m_str) if m_str.isdigit() else 0
    # Upper bound: can't need more north magnets than black cells (each black cell could get its own north magnet)
    # Actually, a tighter bound: can't need more than n*m, but we can use n*m safely.
    assert -1 <= val <= n * m, f"Output {val} out of plausible range [-1, {n*m}]"

def prop_white_rows_and_cols_consistency(run, x):
    """PROPERTY: If any row is fully white, output must be -1 (no south magnet possible in that row)."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n, m = map(int, lines[0].split())
    grid = lines[1:]
    all_white_row = any(all(c == '.' for c in row) for row in grid)
    if all_white_row:
        out = run(x)
        val = int(out.strip().splitlines()[0])
        assert val == -1, f"Row fully white => impossible, but got {val}"

def prop_transpose_symmetry(run, x):
    """PROPERTY: Transposing input (swap n,m and rows↔columns) should give same output."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n, m = map(int, lines[0].split())
    grid = lines[1:]
    # Build transposed input
    new_grid = []
    for c in range(m):
        col = ''.join(grid[r][c] for r in range(n))
        new_grid.append(col)
    transposed_input = f"{m} {n}\n" + "\n".join(new_grid) + "\n"
    out1 = run(x)
    out2 = run(transposed_input)
    val1 = int(out1.strip().splitlines()[0])
    val2 = int(out2.strip().splitlines()[0])
    assert val1 == val2, f"Transpose symmetry broken: {val1} vs {val2}"

def prop_monotonicity_on_black_cells(run, x):
    """PROPERTY: Changing a white cell to black cannot decrease the required north magnets."""
    import copy
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n, m = map(int, lines[0].split())
    grid = [list(row) for row in lines[1:]]
    # Find a white cell
    for r in range(n):
        for c in range(m):
            if grid[r][c] == '.':
                new_grid = copy.deepcopy(grid)
                new_grid[r][c] = '#'
                new_input = f"{n} {m}\n" + "\n".join(''.join(row) for row in new_grid) + "\n"
                out_orig = run(x)
                out_new = run(new_input)
                val_orig = int(out_orig.strip().splitlines()[0])
                val_new = int(out_new.strip().splitlines()[0])
                if val_orig != -1 and val_new != -1:
                    assert val_new >= val_orig, f"Adding black cell decreased north magnets: {val_orig} -> {val_new}"
                # If original impossible (-1), new could be possible or impossible, no constraint.
                # If new is impossible (-1), original could be anything.
                # Only enforce when both are possible.
                break
        else:
            continue
        break

def prop_empty_grid_zero(run, x):
    """PROPERTY: If grid has no black cells, answer must be 0."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n, m = map(int, lines[0].split())
    grid = lines[1:]
    if all(cell == '.' for row in grid for cell in row):
        out = run(x)
        val = int(out.strip().splitlines()[0])
        assert val == 0, f"All white grid should output 0, got {val}"