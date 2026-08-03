def prop_output_format_and_bounds(run, x):
    """PROPERTY: Output has exactly n integers, each between 0 and a safe upper bound."""
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    out = run(x)
    out_vals = out.strip().split()
    assert len(out_vals) == n, f"Expected {n} output numbers, got {len(out_vals)}"
    for s in out_vals:
        val = int(s)
        # Upper bound: worst case, train must visit each candy's start and destination,
        # each travel step taking 1 second, and there are m candies, each requiring at most n-1 steps
        # from its start to destination, plus possibly extra full loops for loading.
        # A safe very loose bound: m * (2*n) (each candy may need to go around almost full circle twice).
        assert 0 <= val <= m * 2 * n, f"Output value {val} out of plausible range"

def prop_adding_duplicate_candy_increases_time(run, x):
    """PROPERTY: Adding an extra candy (duplicate of existing) cannot decrease time for any start."""
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    if m >= 200:  # can't add more, m max 200
        return
    candies = [tuple(map(int, line.split())) for line in lines[1:1+m]]
    # Duplicate the first candy
    a1, b1 = candies[0]
    new_candies = candies + [(a1, b1)]
    new_input = f"{n} {m+1}\n" + "\n".join(f"{a} {b}" for a, b in new_candies)
    out_orig = list(map(int, run(x).strip().split()))
    out_new = list(map(int, run(new_input).strip().split()))
    # More candies cannot make delivery faster
    for i in range(n):
        assert out_new[i] >= out_orig[i], f"Adding candy decreased time for start station {i+1}"