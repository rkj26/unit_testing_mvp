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

def prop_permutation_of_stations(run, x):
    """PROPERTY: Cyclically shifting stations by 1 shifts answers by 1, adjusting candy positions."""
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    candies = [tuple(map(int, line.split())) for line in lines[1:1+m]]
    # Shift stations: station i -> i+1 (mod n, with 1..n)
    def shift(v):
        return v % n + 1
    new_candies = [(shift(a), shift(b)) for a, b in candies]
    new_input = f"{n} {m}\n" + "\n".join(f"{a} {b}" for a, b in new_candies)
    out_orig = run(x).strip().split()
    out_new = run(new_input).strip().split()
    # If original start station s gives time t, then after shifting stations +1,
    # starting from shifted station s+1 should give same t, because the relative positions
    # are identical. So output list is rotated left by 1.
    expected_new = out_orig[1:] + out_orig[:1]
    assert out_new == expected_new, f"Output not rotated as expected after station shift"

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

def prop_reverse_direction_symmetry(run, x):
    """PROPERTY: Reversing direction (reversing station order) and swapping a_i<->b_i yields same times."""
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    candies = [tuple(map(int, line.split())) for line in lines[1:1+m]]
    # Reverse station numbering: station i -> n+1-i
    def rev(v):
        return n + 1 - v
    # New candies: start at rev(b), dest at rev(a) (swap roles because direction reversed)
    new_candies = [(rev(b), rev(a)) for a, b in candies]
    new_input = f"{n} {m}\n" + "\n".join(f"{a} {b}" for a, b in new_candies)
    out_orig = run(x).strip().split()
    out_new = run(new_input).strip().split()
    # Starting from station s in original corresponds to starting from rev(s) in reversed,
    # and the minimal time should be same.
    expected_new = [out_orig[rev(i+1)-1] for i in range(n)]
    assert out_new == expected_new, f"Reverse direction symmetry broken"

def prop_merge_two_inputs_upper_bound(run, x):
    """PROPERTY: Time for union of two candy sets ≤ sum of times for each set separately."""
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    candies = [tuple(map(int, line.split())) for line in lines[1:1+m]]
    if m < 2:
        return
    # Split candies into two halves
    mid = m // 2
    set1 = candies[:mid]
    set2 = candies[mid:]
    input1 = f"{n} {len(set1)}\n" + "\n".join(f"{a} {b}" for a, b in set1)
    input2 = f"{n} {len(set2)}\n" + "\n".join(f"{a} {b}" for a, b in set2)
    out_full = list(map(int, run(x).strip().split()))
    out1 = list(map(int, run(input1).strip().split()))
    out2 = list(map(int, run(input2).strip().split()))
    # You can deliver all candies by first delivering set1 optimally, then set2 optimally,
    # but maybe better interleaving exists, so full time ≤ out1[i] + out2[i].
    for i in range(n):
        assert out_full[i] <= out1[i] + out2[i], f"Full time exceeds sum of parts for start {i+1}"