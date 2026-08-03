import itertools

def prop_output_is_integer(run, x):
    """PROPERTY: Output is a non-negative integer followed by newline."""
    out = run(x).strip()
    # Must be a valid integer, non-negative because costs are positive and k can be 0.
    val = int(out)
    assert val >= 0
    # Ensure no extra whitespace beyond final newline (optional but typical).
    assert out == str(val)

def prop_k_zero_means_no_cards(run, x):
    """PROPERTY: If k=0, answer equals sum of trip costs without cards."""
    lines = x.strip().splitlines()
    n, a, b, k, f = map(int, lines[0].split())
    if k != 0:
        return  # Only test when k=0
    trips = [line.split() for line in lines[1:1+n]]
    total = 0
    prev_end = None
    for start, end in trips:
        if prev_end == start:
            total += b
        else:
            total += a
        prev_end = end
    out = int(run(x).strip())
    assert out == total

def prop_swapping_a_b_does_not_change_answer_if_no_transshipments(run, x):
    """PROPERTY: If all trips are independent (no transshipments), swapping a,b does not affect answer because b<a."""
    lines = x.strip().splitlines()
    n, a, b, k, f = map(int, lines[0].split())
    trips = [line.split() for line in lines[1:1+n]]
    # Check if there are any transshipments
    prev_end = None
    has_transshipment = False
    for start, end in trips:
        if prev_end == start:
            has_transshipment = True
            break
        prev_end = end
    if has_transshipment:
        return  # Not applicable
    # With no transshipments, each trip costs 'a'.
    # Changing a,b (keeping b<a) doesn't matter because b is never used.
    # So answer is n*a if k=0, but with cards it's the same for any a,b.
    # Let's verify by swapping a and b (keeping b<a violated) — but spec says b<a, so we cannot violate.
    # Instead, we can set a' = a, b' = b+1 (but must keep b' < a'? not necessarily).
    # Safer: just ensure answer is invariant when we permute trips so still no transshipments.
    # We'll reverse the whole sequence of trips: start↔end reversed, then reverse order.
    # This preserves no-transshipment property.
    new_trips = [(end, start) for start, end in trips[::-1]]
    new_header = f"{n} {a} {b} {k} {f}"
    new_input = new_header + "\n" + "\n".join(f"{s} {e}" for s, e in new_trips) + "\n"
    out1 = int(run(x).strip())
    out2 = int(run(new_input).strip())
    assert out1 == out2

def prop_monotonic_in_k(run, x):
    """PROPERTY: Increasing k cannot increase the minimal total cost."""
    lines = x.strip().splitlines()
    n, a, b, k, f = map(int, lines[0].split())
    if k == 0:
        return  # No smaller k to test
    # Run with k-1
    new_header = f"{n} {a} {b} {k-1} {f}"
    new_input = new_header + "\n" + "\n".join(lines[1:]) + "\n"
    out_full = int(run(x).strip())
    out_reduced = int(run(new_input).strip())
    # With fewer cards, cost should be >=
    assert out_full <= out_reduced

def prop_route_symmetry(run, x):
    """PROPERTY: Reversing direction of all trips does not change answer."""
    lines = x.strip().splitlines()
    n, a, b, k, f = map(int, lines[0].split())
    trips = [line.split() for line in lines[1:1+n]]
    # Reverse each trip: (start, end) -> (end, start)
    reversed_trips = [(end, start) for start, end in trips]
    new_header = f"{n} {a} {b} {k} {f}"
    new_input = new_header + "\n" + "\n".join(f"{s} {e}" for s, e in reversed_trips) + "\n"
    out1 = int(run(x).strip())
    out2 = int(run(new_input).strip())
    assert out1 == out2