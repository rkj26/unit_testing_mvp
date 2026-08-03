import math

def prop_output_format(run, x):
    """PROPERTY: Output has exactly ceil(n/2) non-negative integers, non-decreasing."""
    # Parse input to get n
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    # Run program
    out = run(x)
    # Parse output: split by whitespace, convert to ints
    parts = out.strip().split()
    assert len(parts) == math.ceil(n / 2), f"Expected {math.ceil(n/2)} numbers, got {len(parts)}"
    vals = list(map(int, parts))
    # Check non-negative
    assert all(v >= 0 for v in vals), f"Output contains negative value: {vals}"
    # Check non-decreasing
    assert all(vals[i] <= vals[i+1] for i in range(len(vals)-1)), f"Output not non-decreasing: {vals}"

def prop_k1_min_cost(run, x):
    """PROPERTY: First output equals minimum cost to create a single peak."""
    # Parse input
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    a = list(map(int, lines[1].split()))
    # Compute min cost for one peak
    min_cost = None
    for i in range(n):
        cost = 0
        if i > 0:
            cost += max(0, a[i-1] - a[i] + 1)
        if i < n-1:
            cost += max(0, a[i+1] - a[i] + 1)
        if min_cost is None or cost < min_cost:
            min_cost = cost
    # Run program
    out = run(x)
    parts = out.strip().split()
    vals = list(map(int, parts))
    assert len(vals) >= 1, "No output for k=1"
    assert vals[0] == min_cost, f"First output {vals[0]} != computed min cost {min_cost}"

def prop_shift_invariance(run, x):
    """PROPERTY: Adding a constant to all heights (within bounds) does not change output."""
    # Parse input
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    a = list(map(int, lines[1].split()))
    # Choose a small constant c that keeps heights in [1, 100000]
    max_allowed = 100000
    min_a = min(a)
    max_a = max(a)
    c = 0
    if max_a + 1 <= max_allowed:
        c = 1
    elif min_a - 1 >= 1:
        c = -1  # but we need to keep all >=1; if min_a > 1 we can subtract
        if min_a + c >= 1:
            pass
        else:
            c = 0
    if c == 0:
        # No shift possible, trivial pass
        return
    a_shifted = [h + c for h in a]
    # Build new input string
    new_input = f"{n}\n" + " ".join(map(str, a_shifted)) + "\n"
    # Run original and shifted
    out1 = run(x)
    out2 = run(new_input)
    vals1 = list(map(int, out1.strip().split()))
    vals2 = list(map(int, out2.strip().split()))
    assert vals1 == vals2, f"Output differs after shifting by {c}: {vals1} vs {vals2}"

def prop_reversal_invariance(run, x):
    """PROPERTY: Reversing the sequence of hills does not change output."""
    # Parse input
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    a = list(map(int, lines[1].split()))
    # Reverse
    a_rev = list(reversed(a))
    new_input = f"{n}\n" + " ".join(map(str, a_rev)) + "\n"
    # Run both
    out1 = run(x)
    out2 = run(new_input)
    vals1 = list(map(int, out1.strip().split()))
    vals2 = list(map(int, out2.strip().split()))
    assert vals1 == vals2, f"Output differs after reversal: {vals1} vs {vals2}"

def prop_upper_bound_naive(run, x):
    """PROPERTY: For each k, output[k-1] ≤ cost of making peaks at indices 0,2,4,..."""
    # Parse input
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    a = list(map(int, lines[1].split()))
    # Run program
    out = run(x)
    vals = list(map(int, out.strip().split()))
    K = len(vals)
    assert K == math.ceil(n / 2)
    # Precompute cost for each index to be a peak (ignoring interactions)
    cost_per_index = []
    for i in range(n):
        c = 0
        if i > 0:
            c += max(0, a[i-1] - a[i] + 1)
        if i < n-1:
            c += max(0, a[i+1] - a[i] + 1)
        cost_per_index.append(c)
    # For each k from 1 to K, take indices 0,2,...,2*(k-1)
    for k in range(1, K+1):
        # indices: 0,2,4,...,2*(k-1)
        indices = [2*j for j in range(k) if 2*j < n]
        # This should hold because k ≤ ceil(n/2)
        total = sum(cost_per_index[i] for i in indices)
        assert vals[k-1] <= total, f"For k={k}, output {vals[k-1]} > naive upper bound {total}"