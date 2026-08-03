def prop_output_format_and_bounds(run, x):
    """PROPERTY: Output must contain exactly n integers, each non-negative, separated by spaces, ending with newline."""
    out = run(x)
    lines = out.strip().split('\n')
    # Exactly one line of output (spec says "first and only line")
    assert len(lines) == 1, f"Expected exactly one line of output, got {len(lines)}"
    tokens = lines[0].split()
    # Parse n from input
    lines_in = x.strip().split('\n')
    n = int(lines_in[0].split()[0])
    assert len(tokens) == n, f"Expected {n} integers, got {len(tokens)}"
    for token in tokens:
        val = int(token)
        assert val >= 0, f"Output integer {val} must be non-negative"

def prop_monotonic_wrt_extra_candy(run, x):
    """PROPERTY: Adding a new candy (a,b) cannot decrease the time for any starting station."""
    import random
    lines = x.strip().split('\n')
    first = lines[0].split()
    n = int(first[0])
    m = int(first[1])
    if m >= 200:
        return  # cannot add more due to constraints
    # Choose random new candy with a != b
    a = random.randint(1, n)
    b = random.randint(1, n)
    while b == a:
        b = random.randint(1, n)
    new_lines = [f"{n} {m+1}"] + lines[1:] + [f"{a} {b}"]
    new_input = '\n'.join(new_lines) + '\n'
    out_orig = run(x)
    out_new = run(new_input)
    orig_vals = list(map(int, out_orig.strip().split()))
    new_vals = list(map(int, out_new.strip().split()))
    for i in range(n):
        assert new_vals[i] >= orig_vals[i], f"Adding candy decreased time for start station {i+1}"