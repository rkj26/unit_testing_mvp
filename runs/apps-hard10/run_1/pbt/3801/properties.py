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
    # Also ensure no extra whitespace lines
    lines_out = stdout.splitlines()
    assert len(lines_out) <= n, "Too many output lines"
    # Check that each line is a valid integer (already done by split)
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
    # Since expected total weight is deterministic, it must match exactly in modulo space
    total_out = sum(out_vals) % MOD
    assert total_out == expected_total_weight % MOD, f"Sum of expected weights mismatch"
    return True

def prop_identical_initial_weights_symmetry(run, x):
    """PROPERTY: If two pictures have same initial weight and same like status, their expected final weights are equal."""
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    likes = list(map(int, lines[1].split()))
    w_init = list(map(int, lines[2].split()))
    # Find pairs with same weight and same like status
    for i in range(n):
        for j in range(i+1, n):
            if w_init[i] == w_init[j] and likes[i] == likes[j]:
                stdout = run(x).strip()
                out_vals = list(map(int, stdout.split()))
                assert out_vals[i] == out_vals[j], f"Symmetry broken for indices {i},{j}"
                break  # one check is enough
    return True

def prop_monotonicity_in_initial_weight(run, x):
    """PROPERTY: For same like status, higher initial weight yields higher expected final weight."""
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    likes = list(map(int, lines[1].split()))
    w_init = list(map(int, lines[2].split()))
    stdout = run(x).strip()
    out_vals = list(map(int, stdout.split()))
    for i in range(n):
        for j in range(n):
            if likes[i] == likes[j] and w_init[i] > w_init[j]:
                assert out_vals[i] >= out_vals[j], f"Monotonicity broken: {i} w_init {w_init[i]} > {j} w_init {w_init[j]} but expected {out_vals[i]} < {out_vals[j]}"
    return True

def prop_scaling_invariance(run, x):
    """PROPERTY: Multiplying all initial weights by a positive integer k does not change expected weights (since probabilities are normalized)."""
    import random
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    likes = list(map(int, lines[1].split()))
    w_init = list(map(int, lines[2].split()))
    # Choose k such that weights remain within reasonable bounds (task constraints: w_i up to 50)
    # But we can scale down if needed, but scaling up could exceed constraints.
    # Instead, we'll create a new input with scaled weights by a factor 2 if possible, else skip.
    # Ensure scaling doesn't violate w_i <= 50 constraint.
    if max(w_init) <= 25:
        k = 2
        new_w = [wt * k for wt in w_init]
        new_input = f"{n} {m}\n" + " ".join(map(str, likes)) + "\n" + " ".join(map(str, new_w)) + "\n"
        stdout_orig = run(x).strip()
        stdout_scaled = run(new_input).strip()
        out_orig = list(map(int, stdout_orig.split()))
        out_scaled = list(map(int, stdout_scaled.split()))
        MOD = 998244353
        for i in range(n):
            assert out_orig[i] == out_scaled[i], f"Scaling invariance broken at index {i}"
    return True