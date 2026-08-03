def prop_format(run, x):
    """PROPERTY: Output consists of exactly n non-negative integers, space-separated, ending with newline."""
    out = run(x)
    # Check ends with newline (optional but typical)
    assert out.endswith('\n'), "Output must end with newline"
    parts = out.strip().split()
    # Parse n from input
    n = int(x.split('\n')[0].split()[0])
    assert len(parts) == n, f"Expected {n} numbers, got {len(parts)}"
    nums = []
    for p in parts:
        num = int(p)  # raises if not integer
        assert num >= 0, f"Time cannot be negative, got {num}"
        nums.append(num)

def prop_rotation(run, x):
    """PROPERTY: Shifting all station numbers by 1 (mod n) rotates the output by -1."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n = int(first[0])
    m = int(first[1])
    # Parse candies
    candies = []
    for line in lines[1:]:
        if not line.strip():
            continue
        a, b = map(int, line.split())
        candies.append((a, b))
    # Original output
    out1_str = run(x)
    out1 = list(map(int, out1_str.strip().split()))
    # Build shifted input
    shifted_lines = [f"{n} {m}"]
    for a, b in candies:
        new_a = (a % n) + 1
        new_b = (b % n) + 1
        shifted_lines.append(f"{new_a} {new_b}")
    shifted_input = '\n'.join(shifted_lines) + '\n'
    out2_str = run(shifted_input)
    out2 = list(map(int, out2_str.strip().split()))
    # Check rotation: out1[i] == out2[(i+1) % n]
    for i in range(n):
        assert out1[i] == out2[(i + 1) % n], f"Rotation mismatch at index {i}"

def prop_monotonicity(run, x):
    """PROPERTY: Adding a duplicate candy does not decrease the required time for any start station."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n = int(first[0])
    m = int(first[1])
    # At least one candy guaranteed by constraints
    candies = []
    for line in lines[1:]:
        if not line.strip():
            continue
        a, b = map(int, line.split())
        candies.append((a, b))
    # Original output
    out1_str = run(x)
    out1 = list(map(int, out1_str.strip().split()))
    # Add duplicate of first candy
    new_candies = candies + [candies[0]]
    new_lines = [f"{n} {m+1}"] + [f"{a} {b}" for a, b in new_candies]
    new_input = '\n'.join(new_lines) + '\n'
    out2_str = run(new_input)
    out2 = list(map(int, out2_str.strip().split()))
    # Check monotonicity
    for i in range(n):
        assert out2[i] >= out1[i], f"Time decreased at station {i+1} after adding a candy"

def prop_lower_bound(run, x):
    """PROPERTY: For each start station s, the time is at least max_i (dist(s,a_i)+dist(a_i,b_i))."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n = int(first[0])
    m = int(first[1])
    candies = []
    for line in lines[1:]:
        if not line.strip():
            continue
        a, b = map(int, line.split())
        candies.append((a, b))
    # Helper: clockwise distance from x to y (1-indexed)
    def dist(x, y):
        if x <= y:
            return y - x
        else:
            return n - (x - y)
    # Compute lower bound for each s
    lb = [0] * n
    for s in range(1, n+1):
        max_val = 0
        for a, b in candies:
            d = dist(s, a) + dist(a, b)
            if d > max_val:
                max_val = d
        lb[s-1] = max_val
    # Actual output
    out_str = run(x)
    out = list(map(int, out_str.strip().split()))
    for s in range(1, n+1):
        assert out[s-1] >= lb[s-1], f"Lower bound violated at station {s}: {out[s-1]} < {lb[s-1]}"

def prop_difference_bound(run, x):
    """PROPERTY: The difference between maximum and minimum output times is at most n-1."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n = int(first[0])
    out_str = run(x)
    out = list(map(int, out_str.strip().split()))
    diff = max(out) - min(out)
    assert diff <= n - 1, f"Max-min difference {diff} exceeds n-1 = {n-1}"