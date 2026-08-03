def prop_output_length_and_format(run, x):
    """PROPERTY: Output must have exactly n integers, separated by single spaces, ending with newline."""
    out = run(x)
    lines = out.strip().split('\n')
    # Exactly one line of output
    assert len(lines) == 1, f"Expected exactly one output line, got {len(lines)}"
    parts = lines[0].strip().split()
    # First line of input gives n
    first_line = x.strip().split('\n')[0]
    n = int(first_line.split()[0])
    assert len(parts) == n, f"Expected {n} numbers in output, got {len(parts)}"
    # All parts must be integers
    for p in parts:
        int(p)  # will raise if not integer
    # Check that output ends with newline (as in examples)
    assert out.endswith('\n'), "Output must end with newline"
    # No extra whitespace
    assert out.count('\n') == 1, "Extra newlines in output"

def prop_non_negative_time(run, x):
    """PROPERTY: All output times are non-negative integers."""
    out = run(x)
    nums = list(map(int, out.strip().split()))
    for t in nums:
        assert t >= 0, f"Negative time {t} in output"