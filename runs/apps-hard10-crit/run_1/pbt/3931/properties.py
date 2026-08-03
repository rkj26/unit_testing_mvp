def prop_output_integer_bounds(run, x):
    """PROPERTY: Output is a single integer within plausible bounds."""
    out = run(x).strip()
    assert out != "", "Output must not be empty"
    value = int(out)
    assert value >= 0, "Output must be non‑negative"

def prop_no_cards_does_not_increase_cost(run, x):
    """PROPERTY: Setting k=0 gives same or higher cost than original k (monotonicity in k)."""
    lines = x.strip().split('\n')
    header = lines[0].split()
    n, a, b, k, f = map(int, header[:5])
    if k == 0:
        return  # No change possible
    # Construct new input with k=0
    new_header = f"{n} {a} {b} 0 {f}"
    new_x = new_header + '\n' + '\n'.join(lines[1:])
    out_original = int(run(x).strip())
    out_zero = int(run(new_x).strip())
    assert out_zero >= out_original, "Cost with k=0 must not be less than with original k"

def prop_route_symmetry(run, x):
    """PROPERTY: Reversing each trip does not change the optimal total cost."""
    lines = x.strip().split('\n')
    header = lines[0]
    trips = lines[1:]
    reversed_trips = []
    for trip in trips:
        s, t = trip.split()
        reversed_trips.append(f"{t} {s}")
    new_x = header + '\n' + '\n'.join(reversed_trips)
    out_orig = int(run(x).strip())
    out_rev = int(run(new_x).strip())
    assert out_orig == out_rev, "Reversing each trip must not change total cost"