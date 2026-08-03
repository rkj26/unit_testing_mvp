import itertools

MOD = 10**9 + 7

def prop_output_bounds(run, x):
    """PROPERTY: Output is an integer in [0, MOD-1]."""
    out = run(x).strip()
    # Ensure it's a single integer
    val = int(out)
    assert 0 <= val < MOD, f"Output {val} not in [0, {MOD-1}]"

def prop_n1_zero(run, x):
    """PROPERTY: For n=1 the answer is always 0."""
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    if n == 1:
        out = run(x).strip()
        val = int(out)
        assert val == 0, f"For n=1 expected 0, got {val}"

def prop_n2_absdiff(run, x):
    """PROPERTY: For n=2 the answer is the absolute difference of the two coordinates."""
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    if n == 2:
        coords = list(map(int, lines[1].split()))
        assert len(coords) == 2
        expected = abs(coords[0] - coords[1])
        out = run(x).strip()
        val = int(out)
        assert val == expected, f"For n=2 expected {expected}, got {val}"

def prop_permutation_invariant(run, x):
    """PROPERTY: Sorting the coordinates does not change the answer."""
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    coords = list(map(int, lines[1].split()))
    # Create sorted version
    sorted_coords = sorted(coords)
    # Build new input
    new_input = f"{n}\n{' '.join(map(str, sorted_coords))}\n"
    out_orig = run(x).strip()
    out_sorted = run(new_input).strip()
    val_orig = int(out_orig)
    val_sorted = int(out_sorted)
    assert val_orig == val_sorted, f"Output changed after sorting: {val_orig} vs {val_sorted}"

def prop_small_n_brute(run, x):
    """PROPERTY: For n <= 10 the answer matches brute-force enumeration."""
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    if n > 10:
        return  # skip large n, brute force would be slow
    coords = list(map(int, lines[1].split()))
    # Brute force over all non-empty subsets
    total = 0
    # Use bitmask from 1 to 2^n - 1
    for mask in range(1, 1 << n):
        # collect coordinates in this subset
        subset_coords = [coords[i] for i in range(n) if (mask >> i) & 1]
        diff = max(subset_coords) - min(subset_coords)
        total = (total + diff) % MOD
    out = run(x).strip()
    val = int(out)
    assert val == total, f"For n={n} brute force gives {total}, got {val}"