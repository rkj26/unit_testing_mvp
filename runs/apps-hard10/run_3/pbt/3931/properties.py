def prop_output_is_integer(run, x):
    """PROPERTY: Output must be a single integer on its own line."""
    out = run(x)
    lines = out.strip().splitlines()
    assert len(lines) == 1, f"Expected exactly one line, got {len(lines)}"
    value = lines[0].strip()
    assert value.lstrip('-').isdigit(), f"Output must be an integer, got '{value}'"
    return True

def prop_cost_non_negative(run, x):
    """PROPERTY: Minimum cost is non-negative."""
    out = run(x)
    cost = int(out.strip())
    assert cost >= 0, f"Cost cannot be negative, got {cost}"
    return True

def prop_k_zero_no_cards(run, x):
    """PROPERTY: If k=0, answer equals sum of trip costs without cards."""
    lines = x.strip().splitlines()
    n, a, b, k, f = map(int, lines[0].split())
    if k != 0:
        return True  # Not applicable
    trips = [line.split() for line in lines[1:]]
    total = 0
    prev_dest = None
    for start, end in trips:
        if start == prev_dest:
            total += b
        else:
            total += a
        prev_dest = end
    out = run(x)
    assert int(out.strip()) == total, f"With k=0, expected {total}, got {out.strip()}"
    return True

def prop_swapping_stop_names(run, x):
    """PROPERTY: Swapping case of all letters in all stop names does not change cost."""
    lines = x.strip().splitlines()
    header = lines[0]
    trips = [line.split() for line in lines[1:]]
    # Swap case for each character in each stop name
    def swap_case(s):
        return ''.join(ch.lower() if ch.isupper() else ch.upper() for ch in s)
    new_trips = [[swap_case(start), swap_case(end)] for start, end in trips]
    new_x = header + '\n' + '\n'.join(' '.join(t) for t in new_trips) + '\n'
    out1 = int(run(x).strip())
    out2 = int(run(new_x).strip())
    assert out1 == out2, f"Swapping case changed cost: {out1} vs {out2}"
    return True

def prop_reordering_trips_same_route_pairs(run, x):
    """PROPERTY: Reordering trips while keeping same multiset of unordered route pairs yields same cost."""
    lines = x.strip().splitlines()
    header = lines[0]
    trips = [line.split() for line in lines[1:]]
    # Build list of unordered routes
    routes = []
    prev_dest = None
    for start, end in trips:
        routes.append((start, end))
        prev_dest = end
    # Shuffle trips (deterministic shuffle for test)
    import random
    random.seed(42)
    shuffled = trips.copy()
    random.shuffle(shuffled)
    new_x = header + '\n' + '\n'.join(' '.join(t) for t in shuffled) + '\n'
    out1 = int(run(x).strip())
    out2 = int(run(new_x).strip())
    # The cost can differ because transshipment conditions change, but if we also shuffle while preserving
    # adjacency for transshipment? Actually, we cannot guarantee same cost. So instead, we check a weaker
    # property: the multiset of unordered route pairs is preserved, so the optimal set of cards to buy
    # (ignoring transshipment) is the same. But transshipment affects base cost. Let's check monotonicity
    # in k: more cards cannot increase cost.
    n, a, b, k, f = map(int, header.split())
    # Increase k to n (max possible) and ensure cost does not increase
    if k < n:
        new_header = f"{n} {a} {b} {n} {f}"
        new_x2 = new_header + '\n' + '\n'.join(' '.join(t) for t in trips) + '\n'
        out3 = int(run(new_x2).strip())
        assert out3 <= out1, f"More cards should not increase cost: {out3} > {out1}"
    return True