import itertools

MOD = 10**9 + 7

def prop_zero_for_n1(run, x):
    """PROPERTY: For n=1, output must be 0."""
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    if n == 1:
        out = run(x)
        val = int(out.strip())
        assert val == 0, f"For n=1 expected 0, got {val}"

def prop_abs_diff_for_n2(run, x):
    """PROPERTY: For n=2, output must be absolute difference of the two coordinates."""
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    if n == 2:
        coords = list(map(int, lines[1].strip().split()))
        assert len(coords) == 2
        expected = abs(coords[0] - coords[1])
        out = run(x)
        val = int(out.strip())
        assert val == expected, f"For n=2 expected {expected}, got {val}"

def prop_permutation_invariant(run, x):
    """PROPERTY: Permuting the list of coordinates does not change the output."""
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    coords = list(map(int, lines[1].strip().split()))
    # Use reversed order as a deterministic permutation
    perm_coords = coords[::-1]
    # Build new input
    new_x = f"{n}\n" + " ".join(map(str, perm_coords)) + "\n"
    out1 = run(x)
    out2 = run(new_x)
    val1 = int(out1.strip())
    val2 = int(out2.strip())
    assert val1 == val2, f"Outputs differ for original and reversed: {val1} vs {val2}"

def prop_small_n_brute_force(run, x):
    """PROPERTY: For n <= 8, output matches brute-force enumeration of subsets."""
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    if n > 8:
        # Skip for large n
        return
    coords = list(map(int, lines[1].strip().split()))
    # Brute force
    total = 0
    # iterate over all non-empty subsets
    for mask in range(1, 1 << n):
        # get subset indices
        subset_vals = [coords[i] for i in range(n) if (mask >> i) & 1]
        max_dist = max(subset_vals) - min(subset_vals)
        total = (total + max_dist) % MOD
    out = run(x)
    val = int(out.strip())
    assert val == total, f"For n={n} brute force gives {total}, got {val}"

def prop_output_range(run, x):
    """PROPERTY: Output is an integer between 0 and MOD-1 inclusive."""
    out = run(x)
    val = int(out.strip())
    assert 0 <= val < MOD, f"Output {val} out of range [0, {MOD})"