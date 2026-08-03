def prop_output_format_and_lower_bound(run, x):
    """PROPERTY: Output is integer; if -1, some city may lack flights; else cost >= sum of per-city minimum flight costs."""
    out = run(x).strip()
    # Must be convertible to int
    try:
        val = int(out)
    except ValueError:
        raise AssertionError(f"Output is not an integer: {out!r}")

    # Parse input
    lines = x.strip().splitlines()
    if not lines:
        raise AssertionError("Empty input")
    n, m, k = map(int, lines[0].split())
    min_in = [None] * (n + 1)   # 1‑based
    min_out = [None] * (n + 1)
    has_in = [False] * (n + 1)
    has_out = [False] * (n + 1)

    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 4:
            continue
        d, f, t, c = map(int, parts)
        if t == 0:          # flight to Metropolis (inbound)
            city = f
            if min_in[city] is None or c < min_in[city]:
                min_in[city] = c
            has_in[city] = True
        else:               # f == 0, flight from Metropolis (outbound)
            city = t
            if min_out[city] is None or c < min_out[city]:
                min_out[city] = c
            has_out[city] = True

    impossible_by_missing = False
    for i in range(1, n + 1):
        if not has_in[i] or not has_out[i]:
            impossible_by_missing = True
            break

    if impossible_by_missing:
        # If a city lacks any required flight, answer must be -1
        if val != -1:
            raise AssertionError(f"City missing flight but output is {val}, not -1")
        return True

    # All cities have at least one inbound and one outbound flight
    if val != -1:
        # Compute sum of minima
        sum_min = 0
        for i in range(1, n + 1):
            sum_min += min_in[i] + min_out[i]
        if val < sum_min:
            raise AssertionError(f"Output {val} < sum of per‑city minima {sum_min}")
        if val < 0:
            raise AssertionError(f"Negative output {val} for feasible instance")
    return True


def permute_cities(lines, perm):
    """Apply permutation perm (dict old -> new) to flights, keep city 0 fixed."""
    new_lines = []
    for line in lines:
        parts = line.split()
        if len(parts) == 4:
            d, f, t, c = map(int, parts)
            f_new = perm.get(f, f)
            t_new = perm.get(t, t)
            new_lines.append(f"{d} {f_new} {t_new} {c}")
        else:
            new_lines.append(line)   # first line unchanged
    return "\n".join(new_lines)


def prop_city_permutation_invariance(run, x):
    """PROPERTY: Permuting city indices (1..n) does not change the answer."""
    lines = x.strip().splitlines()
    if not lines:
        return True
    first = lines[0].split()
    n = int(first[0])
    # Fixed permutation: reverse order
    perm = {i: n + 1 - i for i in range(1, n + 1)}
    modified = permute_cities(lines, perm)
    out1 = run(x).strip()
    out2 = run(modified).strip()
    if out1 != out2:
        raise AssertionError(f"Outputs differ after permutation: {out1} vs {out2}")
    return True


def prop_day_shift_invariance(run, x):
    """PROPERTY: Shifting all flight days by a constant (within bounds) does not change the answer."""
    lines = x.strip().splitlines()
    if not lines:
        return True
    # Parse flights to find min and max day
    min_day = float('inf')
    max_day = 0
    flight_lines = []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) == 4:
            d, f, t, c = map(int, parts)
            if d < min_day:
                min_day = d
            if d > max_day:
                max_day = d
            flight_lines.append((d, f, t, c))
    # Choose a safe shift
    delta = 0
    if min_day > 1:
        delta = -1
    elif max_day < 10**6:
        delta = 1
    if delta == 0:
        return True   # cannot shift without violating constraints
    # Build shifted input
    new_flights = []
    for d, f, t, c in flight_lines:
        new_flights.append(f"{d + delta} {f} {t} {c}")
    n, m, k = map(int, lines[0].split())
    new_input = f"{n} {m} {k}\n" + "\n".join(new_flights)
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    if out1 != out2:
        raise AssertionError(f"Outputs differ after day shift: {out1} vs {out2}")
    return True


def prop_monotonic_in_k(run, x):
    """PROPERTY: Increasing k cannot decrease cost (if still feasible)."""
    lines = x.strip().splitlines()
    if not lines:
        return True
    n, m, k = map(int, lines[0].split())
    # Choose a neighbouring k value that stays within [1, 10^6]
    if k < 10**6:
        k2 = k + 1
        direction = 1   # increased
    elif k > 1:
        k2 = k - 1
        direction = -1  # decreased
    else:
        return True     # k=1 and cannot decrease, k=10^6 and cannot increase
    # Build modified input
    new_first = f"{n} {m} {k2}"
    new_input = new_first + "\n" + "\n".join(lines[1:])
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    try:
        c1 = int(out1) if out1 != "-1" else None
        c2 = int(out2) if out2 != "-1" else None
    except ValueError:
        raise AssertionError("Output not integer or -1")
    if direction == 1:   # k increased
        if c1 is None:   # originally impossible
            if c2 is not None:
                raise AssertionError(f"Originally impossible (k={k}) became possible (k={k2})")
        else:            # originally possible
            if c2 is None:
                raise AssertionError(f"Originally possible (k={k}) became impossible (k={k2})")
            if c2 < c1:
                raise AssertionError(f"Cost decreased from {c1} to {c2} when k increased from {k} to {k2}")
    else:                # k decreased
        if c2 is not None and c1 is not None:
            if c1 < c2:
                raise AssertionError(f"Cost increased from {c2} to {c1} when k decreased from {k} to {k2}")
    return True


def prop_adding_flight_does_not_increase_cost(run, x):
    """PROPERTY: Adding an extra flight (duplicate of an existing one) cannot increase the minimal cost."""
    lines = x.strip().splitlines()
    if not lines:
        return True
    n, m, k = map(int, lines[0].split())
    if m == 0:
        return True   # no flight to duplicate
    # Duplicate the first flight line
    dup_line = lines[1].strip()
    if not dup_line:
        # skip empty lines
        for line in lines[2:]:
            if line.strip():
                dup_line = line.strip()
                break
    if not dup_line:
        return True
    new_flights = lines[1:] + [dup_line]
    new_input = f"{n} {m+1} {k}\n" + "\n".join(new_flights)
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    try:
        c1 = int(out1) if out1 != "-1" else None
        c2 = int(out2) if out2 != "-1" else None
    except ValueError:
        raise AssertionError("Output not integer or -1")
    if c1 is not None:   # originally possible
        if c2 is None:
            raise AssertionError("Originally possible became impossible after adding a flight")
        if c2 > c1:
            raise AssertionError(f"Cost increased from {c1} to {c2} after adding a flight")
    return True