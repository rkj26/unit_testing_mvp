def prop_output_format(run, x):
    """PROPERTY: Output must have exactly n integers, each between 0 and MOD-1 inclusive, separated by whitespace."""
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    stdout = run(x).strip()
    out_vals = list(map(int, stdout.split()))
    assert len(out_vals) == n, f"Expected {n} output numbers, got {len(out_vals)}"
    MOD = 998244353
    for val in out_vals:
        assert 0 <= val < MOD, f"Output value {val} out of range [0, {MOD-1}]"
    lines_out = stdout.splitlines()
    assert len(lines_out) <= n, "Too many output lines"
    return True

def prop_sum_of_weights_expected(run, x):
    """PROPERTY: Expected total weight after m steps equals initial total weight plus m * (liked_count - disliked_count) in expectation."""
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    likes = list(map(int, lines[1].split()))
    w_init = list(map(int, lines[2].split()))
    total_init = sum(w_init)
    liked_count = sum(likes)
    disliked_count = n - liked_count
    expected_total_change = m * (liked_count - disliked_count)
    expected_total_weight = total_init + expected_total_change
    stdout = run(x).strip()
    out_vals = list(map(int, stdout.split()))
    MOD = 998244353
    total_out = sum(out_vals) % MOD
    assert total_out == expected_total_weight % MOD, f"Sum of expected weights mismatch"
    return True