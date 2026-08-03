def prop_format(run, x):
    """PROPERTY: Output has exactly n integers, non-negative, separated by spaces, ending with newline."""
    first_line = x.strip().split('\n')[0]
    n = int(first_line.split()[0])
    out = run(x)
    assert out.endswith('\n'), "Output must end with newline"
    lines = out.strip().split('\n')
    assert len(lines) == 1, "Output should be one line"
    tokens = lines[0].strip().split()
    assert len(tokens) == n, f"Expected {n} integers, got {len(tokens)}"
    for t in tokens:
        v = int(t)
        assert v >= 0, f"Negative time {v}"

def prop_cyclic_shift(run, x):
    """PROPERTY: Shifting all stations by 1 cyclically rotates output by 1."""
    lines = x.strip().split('\n')
    first = lines[0].split()
    n = int(first[0])
    m = int(first[1])
    candies = []
    for line in lines[1:1+m]:
        if line.strip():
            a, b = map(int, line.split())
            candies.append((a, b))
    out1 = run(x)
    vals1 = list(map(int, out1.strip().split()))
    assert len(vals1) == n
    d = 1
    new_candies = [(((a-1+d)%n)+1, ((b-1+d)%n)+1) for a, b in candies]
    new_x = f"{n} {m}\n" + "\n".join(f"{a} {b}" for a, b in new_candies) + "\n"
    out2 = run(new_x)
    vals2 = list(map(int, out2.strip().split()))
    assert len(vals2) == n
    rotated = vals2[d:] + vals2[:d]
    assert rotated == vals1, f"Cyclic shift invariance failed: rotated {rotated} != original {vals1}"

def prop_monotonic_add(run, x):
    """PROPERTY: Adding a candy (1,2) does not decrease delivery times."""
    lines = x.strip().split('\n')
    first = lines[0].split()
    n = int(first[0])
    m = int(first[1])
    if m >= 200:
        return  # cannot add more candies within constraints
    candies = []
    for line in lines[1:1+m]:
        if line.strip():
            a, b = map(int, line.split())
            candies.append((a, b))
    out1 = run(x)
    vals1 = list(map(int, out1.strip().split()))
    new_candies = candies + [(1, 2)]
    new_m = m + 1
    new_x = f"{n} {new_m}\n" + "\n".join(f"{a} {b}" for a, b in new_candies) + "\n"
    out2 = run(new_x)
    vals2 = list(map(int, out2.strip().split()))
    assert len(vals2) == n
    for i in range(n):
        assert vals2[i] >= vals1[i], f"Time decreased at station {i+1}: {vals1[i]} -> {vals2[i]}"

def prop_permute_candies(run, x):
    """PROPERTY: Reversing order of candy lines does not change output."""
    lines = x.strip().split('\n')
    first = lines[0].split()
    n = int(first[0])
    m = int(first[1])
    candies = []
    for line in lines[1:1+m]:
        if line.strip():
            a, b = map(int, line.split())
            candies.append((a, b))
    out1 = run(x)
    vals1 = list(map(int, out1.strip().split()))
    reversed_candies = list(reversed(candies))
    new_x = f"{n} {m}\n" + "\n".join(f"{a} {b}" for a, b in reversed_candies) + "\n"
    out2 = run(new_x)
    vals2 = list(map(int, out2.strip().split()))
    assert vals2 == vals1, "Output changed after reversing candy order"

def prop_lower_bound(run, x):
    """PROPERTY: For each start station, time >= max_i (dist(s,a_i)+dist(a_i,b_i))."""
    lines = x.strip().split('\n')
    first = lines[0].split()
    n = int(first[0])
    m = int(first[1])
    candies = []
    for line in lines[1:1+m]:
        if line.strip():
            a, b = map(int, line.split())
            candies.append((a, b))
    out = run(x)
    vals = list(map(int, out.strip().split()))
    for s in range(1, n+1):
        max_lower = 0
        for a, b in candies:
            dist_sa = (a - s) % n
            dist_ab = (b - a) % n
            lower = dist_sa + dist_ab
            if lower > max_lower:
                max_lower = lower
        assert vals[s-1] >= max_lower, f"Station {s}: time {vals[s-1]} < lower bound {max_lower}"