import math

def prop_output_format_and_length(run, x):
    """PROPERTY: output must contain exactly ceil(n/2) space-separated integers."""
    lines = x.strip().splitlines()
    n = int(lines[0])
    expected_len = (n + 1) // 2
    out = run(x)
    out_tokens = out.strip().split()
    assert len(out_tokens) == expected_len, f"Expected {expected_len} numbers, got {len(out_tokens)}"
    # Ensure all tokens are integers
    for token in out_tokens:
        int(token)
    # Ensure no extra leading/trailing spaces beyond spec
    assert out.strip() == ' '.join(out_tokens), "Output should be space-separated numbers without extra spaces"

def prop_monotonic_non_decreasing(run, x):
    """PROPERTY: output values must be non-decreasing with k."""
    out = run(x)
    values = list(map(int, out.strip().split()))
    for i in range(1, len(values)):
        assert values[i] >= values[i - 1], f"Result for k={i+1} less than for k={i}: {values}"

def prop_reverse_input_symmetry(run, x):
    """PROPERTY: reversing the sequence yields same output (houses condition symmetric)."""
    lines = x.strip().splitlines()
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    reversed_x = f"{n}\n" + " ".join(map(str, reversed(a))) + "\n"
    out1 = run(x)
    out2 = run(reversed_x)
    vals1 = list(map(int, out1.strip().split()))
    vals2 = list(map(int, out2.strip().split()))
    assert vals1 == vals2, f"Results differ on reversed input: {vals1} vs {vals2}"

def prop_shift_all_by_constant(run, x):
    """PROPERTY: adding a large constant to all heights does not change answer (only relative heights matter)."""
    lines = x.strip().splitlines()
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    shift = 1000000
    shifted_a = [h + shift for h in a]
    shifted_x = f"{n}\n" + " ".join(map(str, shifted_a)) + "\n"
    out1 = run(x)
    out2 = run(shifted_x)
    vals1 = list(map(int, out1.strip().split()))
    vals2 = list(map(int, out2.strip().split()))
    assert vals1 == vals2, f"Results differ after shifting all heights: {vals1} vs {vals2}"

def prop_merge_two_identical_copies(run, x):
    """PROPERTY: concatenating two copies of the same sequence yields output where first ceil(n/2) values are same as original."""
    lines = x.strip().splitlines()
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    # Build sequence of length 2n: a + a
    new_n = 2 * n
    new_a = a + a
    new_x = f"{new_n}\n" + " ".join(map(str, new_a)) + "\n"
    out_original = run(x)
    out_double = run(new_x)
    orig_vals = list(map(int, out_original.strip().split()))
    double_vals = list(map(int, out_double.strip().split()))
    # For k up to ceil(n/2), answer should be same as original
    for k in range(1, len(orig_vals) + 1):
        # k-th value (1-indexed) in original corresponds to k-th in double
        assert double_vals[k - 1] == orig_vals[k - 1], f"For k={k}, original {orig_vals[k-1]} != double {double_vals[k-1]}"