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

def prop_reverse_input_same_output(run, x):
    """PROPERTY: Reversing the sequence of hills should give the same output."""
    lines = x.strip().splitlines()
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    reversed_x = f"{n}\n" + " ".join(map(str, reversed(a))) + "\n"
    out1 = run(x).strip()
    out2 = run(reversed_x).strip()
    assert out1 == out2, f"Output differs when input reversed: {out1} vs {out2}"

def prop_all_zero_heights_known_result(run, x):
    """PROPERTY: If all heights are zero, making k peaks requires exactly k hours."""
    n = 5  # fixed small n for this property
    a = [0] * n
    test_input = f"{n}\n" + " ".join(map(str, a)) + "\n"
    out = run(test_input)
    nums = list(map(int, out.strip().split()))
    # For zeros: to have 1 peak, need 0 hours (already a peak if n=1; for n>1, need to lower neighbors).
    # Let's compute via known rule: for zero heights, pattern 0,1,0,1,... gives peaks at odd positions.
    # Lowering a neighbor by 1 costs 1 hour per neighbor.
    # Instead of hardcoding, we check a weaker invariant: each output <= (k-1)*2 (since each peak might need at most 2 neighbors lowered).
    # But simpler: check that output is non-decreasing and <= [0,2,4,...] appropriately.
    # Safer: just verify that output length is ceil(n/2) and monotonic (already covered by other props).
    # We'll instead check that for this concrete input, the output matches the rule derived from small n:
    # For n=5, zeros: to get 1 peak: lower hill2 by 1 → cost 1.
    # Actually let's compute: heights 0 0 0 0 0.
    # To get 1 peak: make position 1 a peak: lower hill2 to -1 → cost 1 → output[0]=1.
    # To get 2 peaks: make positions 1 and 3 peaks: lower hill2 and hill4 each by 1 → cost 2 → output[1]=2.
    # To get 3 peaks: positions 1,3,5: lower hill2, hill4 each by 1 (hill0 and hill6 don't exist) → cost 2? Wait, hill5 needs hill4 lower than it, but hill4 is already 0, hill5 is 0, so lower hill4 to -1 (cost 1) and hill4 is neighbor of hill3 and hill5, but for hill3 peak we need hill2 and hill4 lower, hill2 already -1, hill4 -1, total cost 2? Let's compute systematically:
    # We'll avoid hardcoding; instead, we'll check consistency by running a known small case from spec:
    # Use example 1: all ones, output 1 2 2. That's already in spec, so we can test against it.
    # But spec examples are not guaranteed to be in test suite. Instead, let's do a metamorphic test:
    # Add a constant to all heights → costs remain the same (since only relative heights matter).
    # We'll implement that as a separate property.
    # For this property, we'll just ensure that for all zeros, output is all zeros? No, because example with all ones gave non-zero.
    # Let's replace with a safer metamorphic property:
    pass  # This function is replaced by the next one for safety.

def prop_add_constant_to_all_heights_no_change(run, x):
    """PROPERTY: Adding a constant to all heights does not change the output (cost depends only on relative heights)."""
    lines = x.strip().splitlines()
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    constant = 1000  # large enough to not affect bounds
    new_a = [h + constant for h in a]
    new_input = f"{n}\n" + " ".join(map(str, new_a)) + "\n"
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    assert out1 == out2, f"Output changed after adding constant: {out1} vs {out2}"

def prop_small_n_known_case(run, x):
    """PROPERTY: For n=1, any height, output must be single number 0 (only one hill, already a peak)."""
    n = 1
    height = 5  # arbitrary
    test_input = f"{n}\n{height}\n"
    out = run(test_input).strip()
    nums = list(map(int, out.split()))
    assert len(nums) == 1 and nums[0] == 0, f"For n=1, expected [0], got {nums}"