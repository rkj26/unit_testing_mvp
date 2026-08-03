def prop_output_length_matches_ceil_n_over_2(run, x):
    """PROPERTY: Output must contain exactly ceil(n/2) numbers."""
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    expected_len = (n + 1) // 2
    out = run(x)
    nums = list(map(int, out.strip().split()))
    assert len(nums) == expected_len, f"Expected {expected_len} numbers, got {len(nums)}"

def prop_non_decreasing_output_sequence(run, x):
    """PROPERTY: Output numbers must be non-decreasing (more houses require at least as many hours)."""
    out = run(x)
    nums = list(map(int, out.strip().split()))
    for i in range(1, len(nums)):
        assert nums[i] >= nums[i - 1], f"Output not non-decreasing at index {i}: {nums}"