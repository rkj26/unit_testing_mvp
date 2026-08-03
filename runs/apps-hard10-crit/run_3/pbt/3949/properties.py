def prop_output_format(run, x):
    """PROPERTY: Output must be a single integer, possibly -1, followed by newline."""
    out = run(x)
    lines = out.strip().splitlines()
    assert len(lines) == 1, "Output must be exactly one line"
    s = lines[0].strip()
    assert s.lstrip('-').isdigit(), "Output must be an integer"
    val = int(s)
    assert val == -1 or val >= 0, "Output must be -1 or non-negative"
    assert out == f"{val}\n", "Output must be integer followed by newline"

def prop_transpose_invariance(run, x):
    """PROPERTY: Transposing grid (swap rows and columns) preserves answer."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m = map(int, first)
    grid = lines[1:]
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