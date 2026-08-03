def prop_output_is_integer(run, x):
    """PROPERTY: The output must be a single integer."""
    out = run(x)
    lines = out.strip().splitlines()
    assert len(lines) == 1, f"Expected exactly one output line, got {len(lines)}"
    value = lines[0].strip()
    assert value.lstrip('-').isdigit(), f"Output must be an integer, got '{value}'"