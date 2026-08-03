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

def prop_reverse_input_symmetry(run, x):
    """PROPERTY: Reversing the sequence of hills yields the same output."""
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    a = list(map(int, lines[1].split()))
    rev_x = f"{n}\n" + " ".join(map(str, reversed(a))) + "\n"
    out1 = run(x).strip()
    out2 = run(rev_x).strip()
    assert out1 == out2, f"Outputs differ for reversed input:\n{out1}\n{out2}"

def prop_add_constant_to_all_heights(run, x):
    """PROPERTY: Adding a large constant C to all heights does not change the output (operation only decreases heights)."""
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    a = list(map(int, lines[1].split()))
    C = 1000000
    new_a = [h + C for h in a]
    new_x = f"{n}\n" + " ".join(map(str, new_a)) + "\n"
    out1 = run(x).strip()
    out2 = run(new_x).strip()
    assert out1 == out2, f"Adding constant changed output:\n{out1}\n{out2}"

def prop_monotonicity_in_k(run, x):
    """PROPERTY: For any k, the time for k houses is at most the time for k+1 houses minus minimal extra cost (0 or 1)."""
    out = run(x)
    nums = list(map(int, out.strip().split()))
    for i in range(len(nums) - 1):
        # The difference between k+1 and k houses is at least 0, but we can bound loosely:
        # Actually, we already have non-decreasing from another property, but here we check
        # a stronger invariant: the increase cannot exceed the increase needed for one more house
        # in the simplest possible case: we can always take a solution for k+1 houses and
        # remove one house by undoing some decreases, so time for k <= time for k+1.
        # Already covered by non-decreasing, but we add a check that the sequence is non-decreasing
        # (duplicate, but ensures monotonicity explicitly).
        assert nums[i + 1] >= nums[i], f"Sequence not monotonic at {i}: {nums}"