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

def prop_rotation_symmetry(run, x):
    """PROPERTY: Rotating all station numbers (a_i, b_i) by +1 mod n and starting station by +1 mod n rotates output by +1."""
    lines = x.strip().split('\n')
    first = lines[0].split()
    n = int(first[0])
    m = int(first[1])
    if n <= 1:
        return  # trivial case, but n >= 2 per spec
    # Build rotated input
    rotated_lines = [f"{n} {m}"]
    for line in lines[1:]:
        if not line.strip():
            continue
        a, b = map(int, line.split())
        a_rot = (a % n) + 1
        b_rot = (b % n) + 1
        rotated_lines.append(f"{a_rot} {b_rot}")
    rotated_input = '\n'.join(rotated_lines) + '\n'
    out_orig = run(x)
    out_rot = run(rotated_input)
    orig_vals = list(map(int, out_orig.strip().split()))
    rot_vals = list(map(int, out_rot.strip().split()))
    # rot_vals[i] should equal orig_vals[(i-2) mod n] because starting station shifted by +1
    for i in range(n):
        expected = orig_vals[(i - 2) % n]  # Python modulo handles negative
        assert rot_vals[i] == expected, f"Rotation symmetry broken at position {i}"

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

def prop_identical_candies_merge(run, x):
    """PROPERTY: Duplicating a candy (same a,b) increases time by at most one full cycle per duplicate."""
    lines = x.strip().split('\n')
    first = lines[0].split()
    n = int(first[0])
    m = int(first[1])
    if m == 0:
        return
    # Pick first candy to duplicate
    a1, b1 = map(int, lines[1].split())
    # Duplicate it k times
    k = 2
    new_m = m + k
    new_lines = [f"{n} {new_m}"] + lines[1:] + [f"{a1} {b1}"] * k
    new_input = '\n'.join(new_lines) + '\n'
    out_orig = run(x)
    out_new = run(new_input)
    orig_vals = list(map(int, out_orig.strip().split()))
    new_vals = list(map(int, out_new.strip().split()))
    # Each duplicate adds at most n seconds (full cycle) because you can pick it up on next pass
    for i in range(n):
        assert new_vals[i] <= orig_vals[i] + k * n, f"Duplicate increased time too much for start {i+1}"

def prop_reverse_track_symmetry(run, x):
    """PROPERTY: Reversing direction (replacing each station i with n+1-i) yields same times but reversed output order."""
    lines = x.strip().split('\n')
    first = lines[0].split()
    n = int(first[0])
    m = int(first[1])
    # Build reversed input: station i -> n+1-i
    rev_lines = [f"{n} {m}"]
    for line in lines[1:]:
        if not line.strip():
            continue
        a, b = map(int, line.split())
        a_rev = n + 1 - a
        b_rev = n + 1 - b
        rev_lines.append(f"{a_rev} {b_rev}")
    rev_input = '\n'.join(rev_lines) + '\n'
    out_orig = run(x)
    out_rev = run(rev_input)
    orig_vals = list(map(int, out_orig.strip().split()))
    rev_vals = list(map(int, out_rev.strip().split()))
    # Output for start station i in original corresponds to start station n+1-i in reversed
    for i in range(n):
        assert rev_vals[n - 1 - i] == orig_vals[i], f"Reverse symmetry broken at position {i}"