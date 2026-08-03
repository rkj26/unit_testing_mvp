def prop_bounds(run, x):
    """PROPERTY: Output is an integer between 0 and n*a inclusive."""
    lines = x.strip().splitlines()
    first = list(map(int, lines[0].split()))
    n, a, b, k, f = first
    out = run(x)
    val = int(out.strip())
    # Since each trip costs at most a, total without cards is at most n*a.
    # With cards we can only reduce or stay the same, so val <= n*a.
    # Cost cannot be negative because all costs are positive and cards cost positive.
    assert 0 <= val <= n * a, f"Output {val} outside [0, {n*a}]"

def prop_monotone_k(run, x):
    """PROPERTY: Increasing k does not increase the minimal cost."""
    lines = x.strip().splitlines()
    parts = list(map(int, lines[0].split()))
    n, a, b, k, f = parts
    if k >= 300:
        # Cannot increase k within constraints, skip test.
        return
    # Original output
    out1 = int(run(x).strip())
    # Modified input with k+1
    new_first = f"{n} {a} {b} {k+1} {f}"
    new_lines = [new_first] + lines[1:]
    new_x = "\n".join(new_lines)
    out2 = int(run(new_x).strip())
    assert out2 <= out1, f"Cost increased from {out1} to {out2} when k increased from {k} to {k+1}"

def prop_monotone_f(run, x):
    """PROPERTY: Increasing f does not decrease the minimal cost."""
    lines = x.strip().splitlines()
    parts = list(map(int, lines[0].split()))
    n, a, b, k, f = parts
    if f >= 1000:
        # Cannot increase f within constraints, skip test.
        return
    out1 = int(run(x).strip())
    # Modified input with f+1
    new_first = f"{n} {a} {b} {k} {f+1}"
    new_lines = [new_first] + lines[1:]
    new_x = "\n".join(new_lines)
    out2 = int(run(new_x).strip())
    assert out2 >= out1, f"Cost decreased from {out1} to {out2} when f increased from {f} to {f+1}"

def prop_k_zero_base_cost(run, x):
    """PROPERTY: When k=0, output equals the base cost (sum of a/b per trip)."""
    lines = x.strip().splitlines()
    parts = list(map(int, lines[0].split()))
    n, a, b, k, f = parts
    # Compute base cost from trips
    trips = []
    for i in range(1, n+1):
        start, finish = lines[i].split()
        trips.append((start, finish))
    base_cost = 0
    prev_finish = None
    for start, finish in trips:
        if prev_finish is None or start != prev_finish:
            base_cost += a
        else:
            base_cost += b
        prev_finish = finish
    # Create input with k=0
    new_first = f"{n} {a} {b} 0 {f}"
    new_lines = [new_first] + lines[1:]
    new_x = "\n".join(new_lines)
    out = int(run(new_x).strip())
    assert out == base_cost, f"With k=0 expected base cost {base_cost}, got {out}"

def prop_rename_stops(run, x):
    """PROPERTY: Renaming stops consistently does not change the answer."""
    lines = x.strip().splitlines()
    parts = list(map(int, lines[0].split()))
    n, a, b, k, f = parts
    trips = []
    for i in range(1, n+1):
        start, finish = lines[i].split()
        trips.append((start, finish))
    # Collect distinct stop names
    stops = set()
    for s, f in trips:
        stops.add(s)
        stops.add(f)
    stops = list(sorted(stops))  # deterministic order
    # Create a bijection by reversing the list
    mapping = {}
    for i, s in enumerate(stops):
        mapping[s] = stops[-1 - i]
    # Apply mapping to trips
    new_trips = []
    for start, finish in trips:
        new_trips.append((mapping[start], mapping[finish]))
    # Build new input
    new_first = f"{n} {a} {b} {k} {f}"
    new_lines = [new_first] + [f"{s} {f}" for s, f in new_trips]
    new_x = "\n".join(new_lines)
    out1 = int(run(x).strip())
    out2 = int(run(new_x).strip())
    assert out1 == out2, f"Output changed after renaming: {out1} vs {out2}"