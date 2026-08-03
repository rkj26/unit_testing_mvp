def prop_output_length_matches_ceil_n_over_2(run, x):
    """PROPERTY: Output must contain exactly ceil(n/2) numbers."""
    lines = x.strip().splitlines()
    n = int(lines[0])
    output = run(x).strip()
    if not output:
        # No numbers printed — invalid per spec
        assert False, "Empty output"
    out_numbers = output.split()
    expected_len = (n + 1) // 2  # ceil(n/2)
    assert len(out_numbers) == expected_len, f"Expected {expected_len} numbers, got {len(out_numbers)}"

def prop_non_decreasing_sequence(run, x):
    """PROPERTY: Output numbers are non-decreasing in k."""
    output = run(x).strip()
    if not output:
        return
    nums = list(map(int, output.split()))
    for i in range(1, len(nums)):
        assert nums[i] >= nums[i - 1], f"Output not non-decreasing: {nums}"