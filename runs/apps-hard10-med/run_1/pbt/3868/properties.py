def prop_output_bounds(run, x):
    """PROPERTY: Output is integer -1 or >=2*n."""
    lines = x.strip().splitlines()
    if not lines:
        raise ValueError("Empty input")
    first = lines[0].split()
    n = int(first[0])
    out = run(x).strip()
    assert out, "Output is empty"
    if out == "-1":
        return
    try:
        val = int(out)
    except ValueError:
        raise AssertionError(f"Output is not an integer: {out}")
    assert val >= 2 * n, f"Output {val} < 2*n = {2*n}"

def prop_time_reversal_symmetry(run, x):
    """PROPERTY: Swapping directions and reversing days yields same cost."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m, k = map(int, first)
    flights = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        d, f, t, c = map(int, parts)
        flights.append((d, f, t, c))
    MAX = 10**6 + 1
    new_flights = []
    for d, f, t, c in flights:
        new_d = MAX - d
        new_f, new_t = t, f  # swap
        new_flights.append((new_d, new_f, new_t, c))
    new_lines = [f"{n} {m} {k}"]
    for d, f, t, c in new_flights:
        new_lines.append(f"{d} {f} {t} {c}")
    new_input = "\n".join(new_lines)
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    assert out1 == out2, f"Time reversal symmetry violated: {out1} vs {out2}"

def prop_duplicate_flights(run, x):
    """PROPERTY: Duplicating all flights does not change answer."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m, k = map(int, first)
    flights = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        d, f, t, c = map(int, parts)
        flights.append((d, f, t, c))
    new_m = 2 * m
    new_flights = flights + flights  # duplicate
    new_lines = [f"{n} {new_m} {k}"]
    for d, f, t, c in new_flights:
        new_lines.append(f"{d} {f} {t} {c}")
    new_input = "\n".join(new_lines)
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    assert out1 == out2, f"Duplicate flights changed answer: {out1} vs {out2}"

def prop_cost_shift(run, x):
    """PROPERTY: Adding 1 to all flight costs increases total cost by 2*n (if possible)."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m, k = map(int, first)
    flights = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        d, f, t, c = map(int, parts)
        flights.append((d, f, t, c))
    C = 1
    new_flights = [(d, f, t, c + C) for d, f, t, c in flights]
    new_lines = [f"{n} {m} {k}"]
    for d, f, t, c in new_flights:
        new_lines.append(f"{d} {f} {t} {c}")
    new_input = "\n".join(new_lines)
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    if out1 == "-1":
        assert out2 == "-1", f"Originally impossible became possible after cost shift: {out2}"
    else:
        val1 = int(out1)
        val2 = int(out2)
        expected = val1 + 2 * n * C
        assert val2 == expected, f"Cost shift mismatch: {val2} vs expected {expected}"

def prop_city_permutation(run, x):
    """PROPERTY: Permuting city labels (reverse order) does not change answer."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m, k = map(int, first)
    flights = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        d, f, t, c = map(int, parts)
        flights.append((d, f, t, c))
    # permutation: city i -> n+1-i for i=1..n, 0 remains 0
    def perm(city):
        if city == 0:
            return 0
        return n + 1 - city
    new_flights = []
    for d, f, t, c in flights:
        new_f = perm(f)
        new_t = perm(t)
        new_flights.append((d, new_f, new_t, c))
    new_lines = [f"{n} {m} {k}"]
    for d, f, t, c in new_flights:
        new_lines.append(f"{d} {f} {t} {c}")
    new_input = "\n".join(new_lines)
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    assert out1 == out2, f"City permutation changed answer: {out1} vs {out2}"