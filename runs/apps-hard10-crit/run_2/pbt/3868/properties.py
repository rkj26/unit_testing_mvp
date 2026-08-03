def prop_output_format_and_bounds(run, x):
    """PROPERTY: Output is either a single integer or -1, nothing else."""
    out = run(x).strip()
    # Must be non-empty
    assert out, "Output is empty"
    lines = out.splitlines()
    assert len(lines) == 1, "More than one line of output"
    value = lines[0]
    # Must be integer
    try:
        int_val = int(value)
    except ValueError:
        raise AssertionError("Output is not an integer")
    # If not -1, must be >= n (since each juror needs at least one arrival and one departure flight,
    # but cost per flight >=1, so minimal total cost >= 2*n if possible).
    # We'll just check that if int_val != -1, it's >= 0.
    assert int_val == -1 or int_val >= 0, "Non-negative cost expected when not -1"