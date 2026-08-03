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