def prop_output_format_and_bounds(run, x):
    """PROPERTY: Output is either a single integer or -1, nothing else."""
    out = run(x).strip()
    # Must be non-empty
    assert out, "Output is empty"
    lines = out.splitlines()
    assert len(lines) == 1, "More than one line of output"
    value = lines[0]
    # Must be integer
    try:
        int_val = int(value)
    except ValueError:
        raise AssertionError("Output is not an integer")
    # If not -1, must be >= n (since each juror needs at least one arrival and one departure flight,
    # but cost per flight >=1, so minimal total cost >= 2*n if possible).
    # We'll just check that if int_val != -1, it's >= 0.
    assert int_val == -1 or int_val >= 0, "Non-negative cost expected when not -1"

def prop_impossible_if_no_flight_for_some_city(run, x):
    """PROPERTY: If for some city i (1..n) there is no incoming or outgoing flight, answer must be -1."""
    lines = x.strip().splitlines()
    if not lines:
        return
    n, m, k = map(int, lines[0].split())
    if m == 0:
        # No flights at all → impossible
        out = run(x).strip()
        assert out == "-1", f"Expected -1 when m=0, got {out}"
        return
    # Build sets of cities with incoming (to 0) and outgoing (from 0) flights
    incoming_cities = set()
    outgoing_cities = set()
    for line in lines[1:]:
        parts = list(map(int, line.split()))
        if len(parts) < 4:
            continue
        d, f, t, c = parts
        if f == 0:
            outgoing_cities.add(t)
        elif t == 0:
            incoming_cities.add(f)
    # If any city missing either direction → impossible
    for i in range(1, n+1):
        if i not in incoming_cities or i not in outgoing_cities:
            out = run(x).strip()
            assert out == "-1", f"City {i} missing a flight direction but output not -1"
            return

def prop_cost_monotonic_with_flight_cost(run, x):
    """PROPERTY: Increasing cost of any flight cannot decrease total minimal cost."""
    lines = x.strip().splitlines()
    if not lines:
        return
    # Parse
    header = lines[0]
    flights = [list(map(int, line.split())) for line in lines[1:]]
    # Get original output
    orig_out = run(x).strip()
    if orig_out == "-1":
        # If impossible, increasing costs won't make it possible, so output stays -1
        # Actually, it could become possible? No, increasing costs doesn't add flights.
        # So impossible remains impossible.
        # We'll just skip this test if impossible, because monotonicity in cost not defined.
        return
    orig_cost = int(orig_out)
    # Increase cost of first flight by 1
    if flights:
        flights[0][3] += 1
        new_input = header + "\n" + "\n".join(" ".join(map(str, f)) for f in flights)
        new_out = run(new_input).strip()
        if new_out != "-1":
            new_cost = int(new_out)
            assert new_cost >= orig_cost, "Increasing flight cost decreased total cost"

def prop_symmetry_city_relabeling(run, x):
    """PROPERTY: Relabeling cities 1..n (permuting) should not affect answer if flight days/costs permuted accordingly."""
    import random
    random.seed(12345)  # deterministic
    lines = x.strip().splitlines()
    if not lines:
        return
    n, m, k = map(int, lines[0].split())
    if n <= 1:
        return  # trivial symmetry
    # Build flights
    flights = [list(map(int, line.split())) for line in lines[1:]]
    # Generate a random permutation of cities 1..n
    perm = list(range(1, n+1))
    random.shuffle(perm)
    perm_map = {0: 0}
    for i in range(1, n+1):
        perm_map[i] = perm[i-1]
    # Apply permutation to flights
    new_flights = []
    for d, f, t, c in flights:
        new_f = perm_map[f]
        new_t = perm_map[t]
        new_flights.append((d, new_f, new_t, c))
    # Build new input
    new_input = f"{n} {m} {k}\n" + "\n".join(f"{d} {f} {t} {c}" for d, f, t, c in new_flights)
    # Run both
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    assert out1 == out2, f"City relabeling changed output: {out1} vs {out2}"

def prop_metamorphic_duplicate_flight_same_day(run, x):
    """PROPERTY: Adding a duplicate flight (same day, cities, cost) does not change minimal cost."""
    lines = x.strip().splitlines()
    if not lines:
        return
    header = lines[0]
    flights = [list(map(int, line.split())) for line in lines[1:]]
    if not flights:
        return
    # Duplicate first flight
    dup_flights = flights + [flights[0]]
    new_input = header + "\n" + "\n".join(" ".join(map(str, f)) for f in dup_flights)
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    assert out1 == out2, f"Duplicate flight changed output: {out1} vs {out2}"