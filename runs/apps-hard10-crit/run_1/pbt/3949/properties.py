def prop_output_format_and_bounds(run, x):
    """PROPERTY: Output must be a single integer -1 or nonnegative, fitting spec."""
    out = run(x).strip()
    lines = out.splitlines()
    assert len(lines) == 1, "Output must be exactly one line"
    val_str = lines[0].strip()
    assert val_str.lstrip('-').isdigit(), "Output must be an integer"
    val = int(val_str)
    assert val == -1 or val >= 0, "Output must be -1 or nonnegative integer"

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