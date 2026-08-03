def prop_output_format_and_bounds(run, x):
    """PROPERTY: Output is either '-1' or a positive integer within reasonable bounds."""
    out = run(x).strip()
    if out == '-1':
        return True
    # Must be a non-negative integer
    try:
        val = int(out)
    except ValueError:
        return False
    # Upper bound: worst case each jury uses most expensive flights both ways,
    # flights cost up to 1e6, up to 1e5 jurors, so total <= 2 * 1e5 * 1e6 = 2e11.
    # We'll allow a bit more for safety.
    return 0 <= val <= 10**15

def prop_no_flights_impossible_case(run, x):
    """PROPERTY: If there are no flights at all (m=0) and n>=1, output must be -1."""
    lines = x.strip().splitlines()
    if not lines:
        return True
    first_line = lines[0].split()
    if len(first_line) < 3:
        return True
    n, m, k = map(int, first_line[:3])
    if m == 0 and n >= 1:
        out = run(x).strip()
        return out == '-1'
    return True

def prop_permute_cities(run, x):
    """PROPERTY: Permuting city labels (except city 0) yields same total cost."""
    import random
    lines = x.strip().splitlines()
    if not lines:
        return True
    header = lines[0].split()
    if len(header) < 3:
        return True
    n, m, k = map(int, header[:3])
    if n <= 1:
        return True  # trivial permutation
    # Build permutation of cities 1..n
    perm = list(range(1, n + 1))
    random.shuffle(perm)
    city_map = {0: 0}
    for i, city in enumerate(perm, start=1):
        city_map[i] = city
    # Apply permutation to flights
    new_lines = [f"{n} {m} {k}"]
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        d, f, t, c = map(int, parts[:4])
        f_new = city_map[f]
        t_new = city_map[t]
        new_lines.append(f"{d} {f_new} {t_new} {c}")
    new_input = "\n".join(new_lines) + ("\n" if x.endswith("\n") else "")
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    # Both must be -1 or same integer
    return out1 == out2

def prop_duplicate_flights_cheaper(run, x):
    """PROPERTY: Adding a cheaper duplicate flight cannot increase minimal cost."""
    lines = x.strip().splitlines()
    if not lines:
        return True
    header = lines[0].split()
    if len(header) < 3:
        return True
    n, m, k = map(int, header[:3])
    # Pick a random flight to duplicate with lower cost
    if m == 0:
        return True
    import random
    flight_line = random.choice(lines[1:])
    parts = flight_line.split()
    if len(parts) < 4:
        return True
    d, f, t, c = map(int, parts[:4])
    new_cost = max(1, c - 1)  # cheaper duplicate
    # Build new input with extra flight
    new_lines = [f"{n} {m+1} {k}"] + lines[1:] + [f"{d} {f} {t} {new_cost}"]
    new_input = "\n".join(new_lines) + ("\n" if x.endswith("\n") else "")
    out_orig = run(x).strip()
    out_new = run(new_input).strip()
    if out_orig == '-1':
        # Original impossible, new might be possible or still impossible
        return True
    # Original possible, new must be <= original
    return int(out_new) <= int(out_orig)

def prop_time_reversal_symmetry(run, x):
    """PROPERTY: Reversing time (days -> -days) and swapping f/t should give same cost."""
    lines = x.strip().splitlines()
    if not lines:
        return True
    header = lines[0].split()
    if len(header) < 3:
        return True
    n, m, k = map(int, header[:3])
    max_day = 0
    flights = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        d, f, t, c = map(int, parts[:4])
        max_day = max(max_day, d)
        flights.append((d, f, t, c))
    # Transform: new_day = max_day - d + 1, swap f and t (0 remains 0)
    new_flights = []
    for d, f, t, c in flights:
        new_d = max_day - d + 1
        new_f, new_t = t, f
        new_flights.append((new_d, new_f, new_t, c))
    # Build new input
    new_lines = [f"{n} {m} {k}"]
    for nd, nf, nt, nc in sorted(new_flights, key=lambda x: x[0]):
        new_lines.append(f"{nd} {nf} {nt} {nc}")
    new_input = "\n".join(new_lines) + ("\n" if x.endswith("\n") else "")
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    return out1 == out2