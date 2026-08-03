import math

def prop_format(run, x):
    """PROPERTY: Output contains exactly ceil(n/2) non-negative integers."""
    lines = x.strip().splitlines()
    n = int(lines[0])
    m = (n + 1) // 2  # ceil(n/2)
    out = run(x)
    # Split by whitespace, ignore empty strings
    parts = out.strip().split()
    # Should have exactly m parts
    assert len(parts) == m, f"Expected {m} numbers, got {len(parts)}"
    nums = []
    for p in parts:
        num = int(p)
        assert num >= 0, f"Negative output value {num}"
        nums.append(num)
    # Optionally, check no extra characters besides spaces/newline
    # (already covered by split)

def prop_non_decreasing(run, x):
    """PROPERTY: Output sequence is non-decreasing."""
    out = run(x)
    nums = list(map(int, out.strip().split()))
    for i in range(len(nums) - 1):
        assert nums[i] <= nums[i + 1], f"Output not non-decreasing at index {i}: {nums[i]} > {nums[i+1]}"

def prop_k1_min(run, x):
    """PROPERTY: First output equals minimum cost to make a single peak."""
    lines = x.strip().splitlines()
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    out = run(x)
    nums = list(map(int, out.strip().split()))
    # Compute min cost for a single peak
    best = float('inf')
    for i in range(n):
        if n == 1:
            cost = 0
        elif i == 0:
            cost = max(0, a[1] - (a[0] - 1))
        elif i == n - 1:
            cost = max(0, a[n-2] - (a[n-1] - 1))
        else:
            left = max(0, a[i-1] - (a[i] - 1))
            right = max(0, a[i+1] - (a[i] - 1))
            cost = left + right
        if cost < best:
            best = cost
    assert nums[0] == best, f"First output {nums[0]} does not equal min single-peak cost {best}"

def prop_reversal(run, x):
    """PROPERTY: Reversing the input yields same output."""
    lines = x.strip().splitlines()
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    out1 = run(x)
    nums1 = list(map(int, out1.strip().split()))
    # Build reversed input
    rev_a = a[::-1]
    rev_input = f"{n}\n" + " ".join(map(str, rev_a)) + "\n"
    out2 = run(rev_input)
    nums2 = list(map(int, out2.strip().split()))
    assert nums1 == nums2, f"Outputs differ after reversal: {nums1} vs {nums2}"

def prop_shift_invariant(run, x):
    """PROPERTY: Adding a constant to all heights (within bounds) does not change output."""
    lines = x.strip().splitlines()
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    lo = min(a)
    hi = max(a)
    delta = 0
    if hi < 100000:
        delta = 1
    elif lo > 1:
        delta = -1
    # else delta stays 0 (cannot shift without violating constraints)
    if delta != 0:
        shifted = [x + delta for x in a]
        # Verify shifted are within [1, 100000] (by construction)
        assert all(1 <= v <= 100000 for v in shifted)
        shifted_input = f"{n}\n" + " ".join(map(str, shifted)) + "\n"
        out1 = run(x)
        nums1 = list(map(int, out1.strip().split()))
        out2 = run(shifted_input)
        nums2 = list(map(int, out2.strip().split()))
        assert nums1 == nums2, f"Outputs differ after shifting by {delta}: {nums1} vs {nums2}"
    # If delta == 0, the property holds trivially