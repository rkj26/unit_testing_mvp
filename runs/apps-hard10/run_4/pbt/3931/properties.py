def prop_output_is_integer_and_within_bounds(run, x):
    """PROPERTY: Output is a single integer within plausible bounds."""
    out = run(x).strip()
    # Must be a single integer, possibly with trailing newline
    lines = out.splitlines()
    assert len(lines) == 1, "Output must be exactly one line"
    val = int(lines[0])
    # Lower bound: even if all trips are transshipments (except first) and we buy travel cards,
    # cost cannot be negative.
    assert val >= 0, "Total cost cannot be negative"
    # Upper bound: if no transshipments and no travel cards, cost ≤ n*a.
    # Also travel cards cost ≤ k*f. So total ≤ n*a + k*f.
    # We'll parse n, a, k, f from input to compute bound.
    lines_in = x.strip().splitlines()
    first = list(map(int, lines_in[0].split()))
    n, a, _, k, f = first[:5]
    max_possible = n * a + k * f
    assert val <= max_possible, f"Cost {val} exceeds trivial upper bound {max_possible}"

def prop_cost_with_zero_k_is_fixed(run, x):
    """PROPERTY: If k=0, buying cards is impossible, so cost is sum of trip costs without cards."""
    lines_in = x.strip().splitlines()
    first = list(map(int, lines_in[0].split()))
    n, a, b, k, f = first[:5]
    if k != 0:
        return  # only test when k=0
    # Compute cost without cards: first trip costs a, subsequent trips cost b if start equals previous stop, else a.
    trips = lines_in[1:]
    total_without_cards = 0
    prev_stop = None
    for i, trip in enumerate(trips):
        start, finish = trip.split()
        if i == 0 or start != prev_stop:
            total_without_cards += a
        else:
            total_without_cards += b
        prev_stop = finish
    out = run(x).strip()
    val = int(out)
    assert val == total_without_cards, f"When k=0, cost must be sum without cards: expected {total_without_cards}, got {val}"

def prop_monotonic_in_k(run, x):
    """PROPERTY: Increasing k (max cards allowed) cannot increase total cost."""
    lines_in = x.strip().splitlines()
    first = list(map(int, lines_in[0].split()))
    n, a, b, k, f = first[:5]
    if k == 300:  # max already, cannot increase
        return
    # Create new input with k+1
    new_first = f"{n} {a} {b} {k+1} {f}"
    new_x = new_first + "\n" + "\n".join(lines_in[1:])
    out1 = int(run(x).strip())
    out2 = int(run(new_x).strip())
    assert out2 <= out1, f"Cost should not increase when k increases: {out2} > {out1}"

def prop_symmetric_route_costs(run, x):
    """PROPERTY: Reversing direction of all trips yields same minimal total cost."""
    lines_in = x.strip().splitlines()
    first = lines_in[0]
    trips = lines_in[1:]
    # Reverse each trip: swap start and finish
    reversed_trips = [f"{finish} {start}" for start, finish in (t.split() for t in trips)]
    new_x = first + "\n" + "\n".join(reversed_trips)
    out1 = int(run(x).strip())
    out2 = int(run(new_x).strip())
    assert out1 == out2, f"Reversing all trips should not change cost: {out1} vs {out2}"

def prop_adding_unused_card_does_not_change_cost(run, x):
    """PROPERTY: If f > a and k small, adding an extra unusable card opportunity (increase k by 1) should not change cost."""
    lines_in = x.strip().splitlines()
    first = list(map(int, lines_in[0].split()))
    n, a, b, k, f = first[:5]
    if f <= a:
        return  # card might be useful, skip
    # Compute cost with given k
    out1 = int(run(x).strip())
    # Increase k by 1 (card too expensive to be used)
    new_first = f"{n} {a} {b} {k+1} {f}"
    new_x = new_first + "\n" + "\n".join(lines_in[1:])
    out2 = int(run(new_x).strip())
    assert out2 == out1, f"When f > a, increasing k by 1 should not change cost: {out2} vs {out1}"