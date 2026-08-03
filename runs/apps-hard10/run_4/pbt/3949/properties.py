def prop_output_format(run, x):
    """PROPERTY: Output must be a single integer ending with newline."""
    out = run(x)
    # Must be non-empty, end with newline
    assert out.endswith('\n'), "Output must end with newline"
    # The part before newline must be a valid integer
    lines = out.rstrip('\n').split('\n')
    assert len(lines) == 1, "Exactly one line of output expected"
    val_str = lines[0]
    # Must be integer (possibly negative)
    try:
        int(val_str)
    except ValueError:
        assert False, "Output must be a single integer"

def prop_minus_one_only_if_impossible(run, x):
    """PROPERTY: If output is -1, then swapping all colors (#<->.) should also output -1."""
    out1 = run(x)
    if out1.strip() != "-1":
        return  # Property only applies when output is -1
    # Transform: swap black and white
    lines = x.strip().split('\n')
    n_m = lines[0]
    grid_lines = lines[1:]
    swapped = []
    for row in grid_lines:
        swapped_row = ''.join('#' if ch == '.' else '.' for ch in row)
        swapped.append(swapped_row)
    new_input = n_m + '\n' + '\n'.join(swapped) + '\n'
    out2 = run(new_input)
    # If original is impossible, swapped should also be impossible
    # because both have same structure of constraints (just colors swapped).
    # Actually not always true: e.g., all white -> possible with 0 north magnets,
    # all black -> might be impossible if no south magnet placement works.
    # So this property is NOT universally valid. Let's discard this test.
    # Instead, let's choose a different property:
    # If we add a black cell to an all-white grid, answer should not decrease.
    # But we need a safe property: Let's use transpose symmetry.
    pass

def prop_transpose_invariant(run, x):
    """PROPERTY: Transposing the grid (swap rows/cols) should give same answer."""
    lines = x.strip().split('\n')
    n_m = lines[0].split()
    n, m = int(n_m[0]), int(n_m[1])
    grid = lines[1:]
    # Transpose
    transposed_grid = [''.join(grid[i][j] for i in range(n)) for j in range(m)]
    new_input = f"{m} {n}\n" + '\n'.join(transposed_grid) + '\n'
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    # Both must be valid integers
    int1 = int(out1)
    int2 = int(out2)
    assert int1 == int2, "Transposing grid should not change answer"

def prop_empty_grid_zero(run, x):
    """PROPERTY: If there are no black cells, answer must be 0."""
    lines = x.strip().split('\n')
    grid = lines[1:]
    if all('#' not in row for row in grid):
        out = run(x).strip()
        assert out == "0", "If no black cells, minimum north magnets is 0"

def prop_row_col_south_requirement(run, x):
    """PROPERTY: If there is a row with no black cells and a column with no black cells, answer is -1."""
    lines = x.strip().split('\n')
    n_m = lines[0].split()
    n, m = int(n_m[0]), int(n_m[1])
    grid = lines[1:]
    # Check for a row with no '#'
    row_without_black = any('#' not in grid[i] for i in range(n))
    # Check for a column with no '#'
    col_without_black = False
    for j in range(m):
        if all(grid[i][j] != '#' for i in range(n)):
            col_without_black = True
            break
    if row_without_black and col_without_black:
        out = run(x).strip()
        assert out == "-1", "If a row and a column have no black cells, impossible (no south magnet placement satisfies rule 1 without violating rule 3)"

def prop_monotonicity_add_black(run, x):
    """PROPERTY: Changing a white cell to black cannot decrease the required north magnets."""
    lines = x.strip().split('\n')
    n_m = lines[0].split()
    n, m = int(n_m[0]), int(n_m[1])
    grid = lines[1:]
    # Find first white cell
    changed = False
    new_grid = list(grid)
    for i in range(n):
        for j in range(m):
            if grid[i][j] == '.':
                # Change to black
                new_row = list(grid[i])
                new_row[j] = '#'
                new_grid[i] = ''.join(new_row)
                changed = True
                break
        if changed:
            break
    if not changed:
        return  # no white cells
    new_input = f"{n} {m}\n" + '\n'.join(new_grid) + '\n'
    out1 = int(run(x).strip())
    out2 = int(run(new_input).strip())
    # Adding a black cell can't reduce needed north magnets
    assert out2 >= out1, "Adding a black cell cannot decrease minimum north magnets"