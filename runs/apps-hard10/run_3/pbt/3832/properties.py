import math

def prop_output_length_matches_ceil_n_over_2(run, x):
    """PROPERTY: Output has exactly ceil(n/2) numbers."""
    lines = x.strip().splitlines()
    n = int(lines[0])
    output = run(x).strip()
    if not output:
        # If output is empty, n must be 0, but n >= 1 per spec, so this would be wrong.
        assert False, "Empty output"
    out_numbers = output.split()
    expected_len = (n + 1) // 2
    assert len(out_numbers) == expected_len, f"Expected {expected_len} numbers, got {len(out_numbers)}"

def prop_non_negative_output(run, x):
    """PROPERTY: All output numbers are non-negative integers."""
    output = run(x).strip()
    if not output:
        # No output means no numbers to check, but spec requires at least one number for n>=1.
        # So this is an error.
        assert False, "Empty output"
    out_numbers = output.split()
    for num_str in out_numbers:
        num = int(num_str)
        assert num >= 0, f"Negative output value {num}"

def prop_monotonic_non_decreasing(run, x):
    """PROPERTY: Output sequence is non-decreasing (more houses require at least as many hours)."""
    output = run(x).strip()
    if not output:
        return  # n=0 case not in spec, but guard anyway
    out_numbers = list(map(int, output.split()))
    for i in range(1, len(out_numbers)):
        assert out_numbers[i] >= out_numbers[i-1], f"Output decreases at position {i}: {out_numbers[i-1]} -> {out_numbers[i]}"

def prop_permutation_invariance(run, x):
    """PROPERTY: Reversing the sequence yields the same output (symmetry)."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return  # malformed, skip
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    # Reverse the hills
    x_rev = f"{n}\n" + " ".join(map(str, reversed(a))) + "\n"
    out_orig = run(x).strip()
    out_rev = run(x_rev).strip()
    # Output should be identical because problem is symmetric under reversal
    assert out_orig == out_rev, f"Output differs after reversal: '{out_orig}' vs '{out_rev}'"

def prop_linear_scaling_of_heights(run, x):
    """PROPERTY: Adding a constant to all heights does not decrease the output values."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    # Add a positive constant C (large enough to avoid negatives after subtraction)
    C = 1000000
    a_shifted = [h + C for h in a]
    x_shifted = f"{n}\n" + " ".join(map(str, a_shifted)) + "\n"
    out_orig = list(map(int, run(x).strip().split()))
    out_shifted = list(map(int, run(x_shifted).strip().split()))
    # Shifting heights up cannot increase the required hours (we can simulate the same reductions).
    # Actually, shifting up may allow cheaper solutions? Wait: We can only decrease heights.
    # If we shift up, the relative differences stay the same, but absolute heights increase.
    # The excavator works in hours per unit decrease. The required decreases in terms of
    # "how much to cut from a hill" are the same in relative terms, but the absolute heights
    # are larger, so the same cuts are still possible. Thus the minimal hours should be identical.
    # More formally: if we take an optimal solution for original heights and add C to each final height,
    # we get a feasible solution for the shifted input with same hours. Conversely, subtracting C
    # from a solution for shifted input gives a feasible solution for original with same hours.
    # Therefore outputs must be equal.
    assert out_orig == out_shifted, f"Output changed after shifting heights: {out_orig} vs {out_shifted}"