def prop_output_length_matches_ceil_n_over_2(run, x):
    """PROPERTY: Output must contain exactly ceil(n/2) numbers."""
    lines = x.strip().splitlines()
    n = int(lines[0])
    k_out = (n + 1) // 2  # ceil(n/2)
    out = run(x)
    nums = list(map(int, out.strip().split()))
    assert len(nums) == k_out, f"Expected {k_out} numbers, got {len(nums)}"

def prop_monotonic_non_decreasing_output(run, x):
    """PROPERTY: Output sequence must be non-decreasing (more houses cannot cost fewer hours)."""
    out = run(x)
    nums = list(map(int, out.strip().split()))
    for i in range(1, len(nums)):
        assert nums[i] >= nums[i - 1], f"Output not non-decreasing at index {i}: {nums}"