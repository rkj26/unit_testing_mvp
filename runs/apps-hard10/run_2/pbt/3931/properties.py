def prop_output_is_integer(run, x):
    """PROPERTY: The output must be a single integer."""
    out = run(x)
    lines = out.strip().splitlines()
    assert len(lines) == 1, f"Expected exactly one output line, got {len(lines)}"
    value = lines[0].strip()
    assert value.lstrip('-').isdigit(), f"Output must be an integer, got '{value}'"

def prop_no_cards_cost_is_base_sum(run, x):
    """PROPERTY: If k=0, total cost equals sum of trip costs without cards."""
    # Parse input
    lines = x.strip().splitlines()
    n, a, b, k, f = map(int, lines[0].split())
    if k != 0:
        return  # only test when k=0
    trips = [line.split() for line in lines[1:]]
    # Compute base cost without cards
    total = 0
    prev_finish = None
    for start, finish in trips:
        if start == prev_finish:
            total += b
        else:
            total += a
        prev_finish = finish
    out = run(x)
    result = int(out.strip())
    assert result == total, f"k=0: expected {total}, got {result}"

def prop_swap_directions_invariant(run, x):
    """PROPERTY: Reversing all trips (swap start/end of each) yields same cost."""
    lines = x.strip().splitlines()
    header = lines[0]
    trips = [line.split() for line in lines[1:]]
    # Build reversed input
    reversed_trips = [f"{finish} {start}" for start, finish in trips]
    x2 = header + '\n' + '\n'.join(reversed_trips)
    out1 = int(run(x).strip())
    out2 = int(run(x2).strip())
    assert out1 == out2, f"Reversing trips changed cost: {out1} vs {out2}"

def prop_monotonic_in_k(run, x):
    """PROPERTY: Increasing k cannot increase total cost."""
    lines = x.strip().splitlines()
    n, a, b, k, f = map(int, lines[0].split())
    if k == 0:
        return  # no larger k to compare
    # Build input with k-1
    header2 = f"{n} {a} {b} {k-1} {f}"
    x2 = header2 + '\n' + '\n'.join(lines[1:])
    out_k = int(run(x).strip())
    out_km1 = int(run(x2).strip())
    assert out_k <= out_km1, f"Cost increased when k went from {k-1} to {k}: {out_km1} -> {out_k}"

def prop_rename_stops_preserves_cost(run, x):
    """PROPERTY: Bijective renaming of all stop names preserves total cost."""
    import random
    random.seed(0)  # deterministic
    lines = x.strip().splitlines()
    header = lines[0]
    trips = [line.split() for line in lines[1:]]
    # Collect all unique stop names
    stops = set()
    for start, finish in trips:
        stops.add(start)
        stops.add(finish)
    # Create a random permutation
    stop_list = list(stops)
    perm = stop_list[:]
    random.shuffle(perm)
    mapping = dict(zip(stop_list, perm))
    # Build renamed input
    renamed_trips = [f"{mapping[start]} {mapping[finish]}" for start, finish in trips]
    x2 = header + '\n' + '\n'.join(renamed_trips)
    out1 = int(run(x).strip())
    out2 = int(run(x2).strip())
    assert out1 == out2, f"Renaming stops changed cost: {out1} vs {out2}"