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