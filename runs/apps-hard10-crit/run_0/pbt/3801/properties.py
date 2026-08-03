def prop_output_format(run, x):
    """PROPERTY: Output must have exactly n integers, one per line, each in [0, 998244353)."""
    out = run(x).strip()
    if not out:
        raise AssertionError("Empty output")
    lines = out.split()
    lines_in = x.strip().splitlines()
    n = int(lines_in[0].split()[0])
    if len(lines) != n:
        raise AssertionError(f"Expected {n} output numbers, got {len(lines)}")
    for s in lines:
        val = int(s)
        if not (0 <= val < 998244353):
            raise AssertionError(f"Output value {val} out of required range")

def prop_total_weight_conservation(run, x):
    """PROPERTY: Sum of expected weights after m visits equals sum of initial weights plus (likes - dislikes)*m."""
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    likes = list(map(int, lines[1].split()))
    init_weights = list(map(int, lines[2].split()))
    total_likes = sum(likes[i] for i in range(n))
    total_dislikes = n - total_likes
    total_change = (total_likes - total_dislikes) * m
    expected_total = sum(init_weights) + total_change
    out = run(x).strip().split()
    out_vals = list(map(int, out))
    actual_sum = sum(out_vals) % 998244353
    expected_mod = expected_total % 998244353
    if actual_sum != expected_mod:
        raise AssertionError(f"Total expected weight mismatch: got {actual_sum}, expected {expected_mod}")