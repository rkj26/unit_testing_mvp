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

def prop_shift_symmetry(run, x):
    """PROPERTY: Rotating all stations (a_i, b_i) by +1 mod n rotates output by +1."""
    lines = x.strip().split('\n')
    header = lines[0].split()
    n = int(header[0])
    m = int(header[1])
    if n == 0:
        return
    # Build shifted input
    shifted_lines = [f"{n} {m}"]
    for i in range(m):
        a, b = map(int, lines[i+1].split())
        shifted_a = (a % n) + 1
        shifted_b = (b % n) + 1
        shifted_lines.append(f"{shifted_a} {shifted_b}")
    shifted_input = '\n'.join(shifted_lines) + '\n'
    # Run original and shifted
    out_orig = run(x)
    out_shifted = run(shifted_input)
    orig_times = list(map(int, out_orig.strip().split()))
    shifted_times = list(map(int, out_shifted.strip().split()))
    # Check rotation: shifted_times[i] should equal orig_times[(i-2) mod n]
    for i in range(n):
        idx_in_orig = (i - 2) % n  # because station numbers are 1‑based, shifting a,b by +1 moves start station -1 in output
        assert shifted_times[i] == orig_times[idx_in_orig], f"Shift symmetry broken at position {i}"

def prop_duplicate_candy_removal(run, x):
    """PROPERTY: Adding a duplicate candy (same a,b) cannot decrease delivery time for any start station."""
    lines = x.strip().split('\n')
    header = lines[0].split()
    n = int(header[0])
    m = int(header[1])
    # Build input with one extra duplicate of first candy
    new_lines = [f"{n} {m+1}"]
    new_lines.extend(lines[1:])  # all original candies
    # duplicate first candy
    a1, b1 = map(int, lines[1].split())
    new_lines.append(f"{a1} {b1}")
    new_input = '\n'.join(new_lines) + '\n'
    out_orig = run(x)
    out_new = run(new_input)
    orig_times = list(map(int, out_orig.strip().split()))
    new_times = list(map(int, out_new.strip().split()))
    for i in range(n):
        assert new_times[i] >= orig_times[i], f"Adding a duplicate candy decreased time for start station {i+1}"

def prop_time_monotonicity_wrt_candy_distance(run, x):
    """PROPERTY: If a candy's delivery distance (forward distance a->b) is increased, total time cannot decrease."""
    import copy
    lines = x.strip().split('\n')
    header = lines[0].split()
    n = int(header[0])
    m = int(header[1])
    if m == 0:
        return
    # Find a candy where b can be increased modulo n without making a=b
    for idx in range(1, m+1):
        a, b = map(int, lines[idx].split())
        new_b = (b % n) + 1
        if new_b == a:
            continue
        # Build modified input with this candy's destination changed to new_b
        mod_lines = [f"{n} {m}"]
        for j in range(1, m+1):
            if j == idx:
                mod_lines.append(f"{a} {new_b}")
            else:
                mod_lines.append(lines[j])
        mod_input = '\n'.join(mod_lines) + '\n'
        out_orig = run(x)
        out_mod = run(mod_input)
        orig_times = list(map(int, out_orig.strip().split()))
        mod_times = list(map(int, out_mod.strip().split()))
        # Since new_b is one step farther in circular order, delivery time for this candy increases,
        # so total time cannot decrease for any start station.
        for i in range(n):
            assert mod_times[i] >= orig_times[i], f"Increasing candy distance decreased total time for start {i+1}"
        # Only need to check one candy
        break