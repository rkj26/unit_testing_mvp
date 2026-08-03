def prop_output_format(run, x):
    """PROPERTY: Output must have exactly n integers, one per line, each in [0, 998244353)."""
    out = run(x).strip()
    if not out:
        raise AssertionError("Empty output")
    lines = out.split()
    # Parse n from input
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
    # total change = (likes - dislikes) * m
    total_change = (total_likes - total_dislikes) * m
    expected_total = sum(init_weights) + total_change
    out = run(x).strip().split()
    out_vals = list(map(int, out))
    # The sum of expected weights must equal expected_total modulo 998244353
    actual_sum = sum(out_vals) % 998244353
    expected_mod = expected_total % 998244353
    if actual_sum != expected_mod:
        raise AssertionError(f"Total expected weight mismatch: got {actual_sum}, expected {expected_mod}")

def prop_single_like_all_visits(run, x):
    """PROPERTY: If only one picture is liked and m visits happen, its expected weight is initial + m."""
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    likes = list(map(int, lines[1].split()))
    if sum(likes) != 1:
        return  # skip if not exactly one liked picture
    init_weights = list(map(int, lines[2].split()))
    liked_idx = likes.index(1)
    out = run(x).strip().split()
    out_vals = list(map(int, out))
    # The liked picture's expected weight must be init_weights[liked_idx] + m
    expected = init_weights[liked_idx] + m
    if out_vals[liked_idx] != expected % 998244353:
        raise AssertionError(f"Liked picture weight mismatch: got {out_vals[liked_idx]}, expected {expected % 998244353}")

def prop_swap_two_identical_pictures(run, x):
    """PROPERTY: Swapping two pictures with identical a_i and w_i should swap their outputs."""
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    likes = list(map(int, lines[1].split()))
    weights = list(map(int, lines[2].split()))
    # Find two indices i, j with same a_i and same w_i
    for i in range(n):
        for j in range(i + 1, n):
            if likes[i] == likes[j] and weights[i] == weights[j]:
                # Build swapped input
                new_likes = likes.copy()
                new_likes[i], new_likes[j] = new_likes[j], new_likes[i]
                new_weights = weights.copy()
                new_weights[i], new_weights[j] = new_weights[j], new_weights[i]
                new_input = f"{n} {m}\n" + " ".join(map(str, new_likes)) + "\n" + " ".join(map(str, new_weights)) + "\n"
                out1 = list(map(int, run(x).strip().split()))
                out2 = list(map(int, run(new_input).strip().split()))
                if out1[i] != out2[j] or out1[j] != out2[i]:
                    raise AssertionError(f"Swapping identical pictures did not swap outputs")
                # Also check all others unchanged
                for k in range(n):
                    if k != i and k != j:
                        if out1[k] != out2[k]:
                            raise AssertionError(f"Non-swapped picture changed")
                return  # one successful check suffices
    # If no such pair exists, skip
    return

def prop_scaling_initial_weights(run, x):
    """PROPERTY: Multiplying all initial weights by a positive integer k multiplies expected weights by k (mod 998244353)."""
    import random
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    likes = list(map(int, lines[1].split()))
    weights = list(map(int, lines[2].split()))
    # Choose a small multiplier to keep weights in reasonable range (since w_i <= 50, k=2 is safe)
    k = 2
    new_weights = [w * k for w in weights]
    new_input = f"{n} {m}\n" + " ".join(map(str, likes)) + "\n" + " ".join(map(str, new_weights)) + "\n"
    out1 = list(map(int, run(x).strip().split()))
    out2 = list(map(int, run(new_input).strip().split()))
    mod = 998244353
    for i in range(n):
        if (out1[i] * k) % mod != out2[i]:
            raise AssertionError(f"Scaling initial weights by {k} did not scale output {i} accordingly")