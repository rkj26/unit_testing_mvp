def prop_output_integer_bounds(run, x):
    """PROPERTY: Output is a single integer within plausible bounds."""
    out = run(x).strip()
    assert out != "", "Output must not be empty"
    value = int(out)
    # Lower bound: if all trips cost b (best case with transshipments) and we buy 0 cards.
    # Upper bound: if all trips cost a and we buy no cards.
    # Actually, we can't guarantee tighter bounds without solving, so just check it's a non‑negative integer.
    assert value >= 0, "Output must be non‑negative"
    # No upper bound check because it's not fixed by spec.

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

def prop_permute_trips_same_cost(run, x):
    """PROPERTY: Permuting trips arbitrarily changes transshipment opportunities but total without cards is invariant."""
    import random
    random.seed(0)
    lines = x.strip().split('\n')
    header = lines[0].split()
    n, a, b, k, f = map(int, header[:5])
    trips = lines[1:]
    if k > 0:
        # If cards allowed, permutation can affect optimal card choice, so skip.
        return
    # With k=0, only a/b costs matter, and total without cards is fixed for given multiset of trips.
    # Shuffle trips and compute cost without cards (since k=0).
    shuffled = trips.copy()
    random.shuffle(shuffled)
    new_x = f"{n} {a} {b} 0 {f}\n" + '\n'.join(shuffled)
    out_orig = int(run(x).strip())
    out_shuf = int(run(new_x).strip())
    assert out_orig == out_shuf, "With k=0, permuting trips must not change total cost"

def prop_duplicate_trips_increase_cost_at_most_linearly(run, x):
    """PROPERTY: Duplicating all trips (double n) with k doubled yields at most double cost."""
    lines = x.strip().split('\n')
    header = lines[0].split()
    n, a, b, k, f = map(int, header[:5])
    trips = lines[1:]
    # Double the sequence of trips and double k
    new_n = 2 * n
    new_k = 2 * k
    new_trips = trips + trips
    new_x = f"{new_n} {a} {b} {new_k} {f}\n" + '\n'.join(new_trips)
    out_orig = int(run(x).strip())
    out_double = int(run(new_x).strip())
    # Doubling trips and k should at most double cost (could be less due to more transshipments/card reuse)
    assert out_double <= 2 * out_orig, "Doubling trips and k should not more than double cost"