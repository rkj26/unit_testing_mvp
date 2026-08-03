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
    assert -1 <= val <= n * m, f"Output {val} out of plausible range [-1, {n*m}]"

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