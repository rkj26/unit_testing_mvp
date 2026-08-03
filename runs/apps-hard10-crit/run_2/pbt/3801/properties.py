def prop_output_format_and_bounds(run, x):
    """PROPERTY: Output must have n integers (one per line), each in [0, 998244353)."""
    stdout = run(x).strip()
    if not stdout:
        raise AssertionError("Empty output")
    lines = stdout.splitlines()
    # First line of input is n m
    n = int(x.split()[0])
    if len(lines) != n:
        raise AssertionError(f"Expected {n} output lines, got {len(lines)}")
    for line in lines:
        val = int(line)
        if not (0 <= val < 998244353):
            raise AssertionError(f"Output value {val} out of range [0, 998244353)")


def prop_total_weight_increase_by_m(run, x):
    """PROPERTY: Expected sum of final weights = initial sum of weights + m * (liked_count - disliked_count)."""
    lines = x.strip().splitlines()
    header = lines[0].split()
    n = int(header[0])
    m = int(header[1])
    a_line = list(map(int, lines[1].split()))
    w_line = list(map(int, lines[2].split()))
    initial_sum = sum(w_line)
    liked_count = sum(a_line)
    disliked_count = n - liked_count
    expected_total = initial_sum + m * (liked_count - disliked_count)
    out_vals = list(map(int, run(x).strip().split()))
    total_out = sum(out_vals) % 998244353
    if total_out != expected_total % 998244353:
        raise AssertionError(f"Total expected weight mismatch: got {total_out}, expected {expected_total % 998244353}")


def prop_permutation_invariance(run, x):
    """PROPERTY: Permuting pictures together with their a_i and w_i permutes outputs accordingly."""
    import random
    random.seed(123)  # deterministic
    lines = x.strip().splitlines()
    header = lines[0].split()
    n = int(header[0])
    m = int(header[1])
    a_line = list(map(int, lines[1].split()))
    w_line = list(map(int, lines[2].split()))
    perm = list(range(n))
    random.shuffle(perm)
    # Build permuted input
    a_perm = [a_line[i] for i in perm]
    w_perm = [w_line[i] for i in perm]
    x_perm = f"{n} {m}\n" + " ".join(map(str, a_perm)) + "\n" + " ".join(map(str, w_perm))
    out_orig = run(x).strip().split()
    out_perm = run(x_perm).strip().split()
    # Check correspondence
    for orig_idx, perm_idx in enumerate(perm):
        if out_orig[orig_idx] != out_perm[perm_idx]:
            raise AssertionError(f"Permutation invariance violated: orig index {orig_idx} -> perm index {perm_idx}")