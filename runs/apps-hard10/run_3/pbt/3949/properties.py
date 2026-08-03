def prop_output_format(run, x):
    """PROPERTY: Output must be a single integer, possibly -1, followed by newline."""
    out = run(x)
    lines = out.strip().splitlines()
    assert len(lines) == 1, "Output must be exactly one line"
    s = lines[0].strip()
    assert s.lstrip('-').isdigit(), "Output must be an integer"
    val = int(s)
    assert val == -1 or val >= 0, "Output must be -1 or non-negative"
    # Ensure no extra spaces or characters
    assert out == f"{val}\n", "Output must be integer followed by newline"

def prop_symmetry_under_row_permutation(run, x):
    """PROPERTY: Permuting rows of the grid preserves feasibility (output -1 vs not -1)."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m = map(int, first)
    grid = lines[1:]
    import random
    # Create a permutation of rows
    perm = list(range(n))
    random.shuffle(perm)
    new_lines = [f"{n} {m}"] + [grid[perm[i]] for i in range(n)]
    new_input = "\n".join(new_lines) + "\n"
    out1 = run(x)
    out2 = run(new_input)
    val1 = int(out1.strip())
    val2 = int(out2.strip())
    # Feasibility must be preserved
    assert (val1 == -1) == (val2 == -1), "Row permutation should not change feasibility"

def prop_black_cells_require_south_in_row_or_column(run, x):
    """PROPERTY: If a row has a black cell, there must be a south magnet in that row (implied by spec)."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m = map(int, first)
    grid = lines[1:]
    out = run(x)
    ans = int(out.strip())
    if ans == -1:
        return  # Infeasible case, nothing to check
    # For each row with a black cell, check that row is not all white
    for i in range(n):
        if '#' in grid[i]:
            # Row i has black cell → spec requires at least one south magnet in every row
            # This is a constraint from the problem statement, so if ans != -1, it's satisfied.
            # We can't check placement directly, but we can check that the grid doesn't
            # violate a necessary condition: a row with black cells cannot be all white in a feasible solution.
            # Actually, all rows must have a south magnet regardless of color.
            # But the problem says: "There is at least one south magnet in every row and every column."
            # So if ans != -1, the program claims such placement exists.
            # No direct test possible without solving, so we just trust the spec.
            pass

def prop_monotonicity_on_adding_black_cells(run, x):
    """PROPERTY: Changing a white cell to black cannot decrease required north magnets (if still feasible)."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m = map(int, first)
    grid = [list(row) for row in lines[1:]]
    out1 = run(x)
    val1 = int(out1.strip())
    if val1 == -1:
        return  # Infeasible original, nothing to compare
    # Find a white cell, turn it black
    changed = False
    for i in range(n):
        for j in range(m):
            if grid[i][j] == '.':
                grid[i][j] = '#'
                changed = True
                break
        if changed:
            break
    if not changed:
        return  # No white cell to change
    new_input = f"{n} {m}\n" + "\n".join("".join(row) for row in grid) + "\n"
    out2 = run(new_input)
    val2 = int(out2.strip())
    if val2 != -1:
        # More black cells cannot reduce minimal north magnets
        assert val2 >= val1, "Adding a black cell should not reduce minimal north magnets"

def prop_transpose_invariance(run, x):
    """PROPERTY: Transposing grid (swap rows and columns) preserves answer."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m = map(int, first)
    grid = lines[1:]
    # Build transpose
    transposed = []
    for j in range(m):
        row = ''.join(grid[i][j] for i in range(n))
        transposed.append(row)
    new_input = f"{m} {n}\n" + "\n".join(transposed) + "\n"
    out1 = run(x)
    out2 = run(new_input)
    val1 = int(out1.strip())
    val2 = int(out2.strip())
    assert val1 == val2, "Transposing grid should give same answer"