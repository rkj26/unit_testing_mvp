import math

def prop_output_format_and_length(run, x):
    """PROPERTY: output must contain exactly ceil(n/2) space-separated integers."""
    lines = x.strip().splitlines()
    n = int(lines[0])
    expected_len = (n + 1) // 2
    out = run(x)
    out_tokens = out.strip().split()
    assert len(out_tokens) == expected_len, f"Expected {expected_len} numbers, got {len(out_tokens)}"
    for token in out_tokens:
        int(token)
    assert out.strip() == ' '.join(out_tokens), "Output should be space-separated numbers without extra spaces"

def prop_monotonic_non_decreasing(run, x):
    """PROPERTY: output values must be non-decreasing with k."""
    out = run(x)
    values = list(map(int, out.strip().split()))
    for i in range(1, len(values)):
        assert values[i] >= values[i - 1], f"Result for k={i+1} less than for k={i}: {values}"