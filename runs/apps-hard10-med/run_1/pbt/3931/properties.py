def prop_output_format(run, x):
    """PROPERTY: Output is a non-negative integer."""
    out = run(x)
    # strip whitespace, especially newline
    s = out.strip()
    # must be an integer
    val = int(s)
    # must be non-negative
    assert val >= 0, f"Output {val} is negative"
    # optional: ensure no extra characters besides optional newline
    assert s == str(val), f"Output contains extra characters: {repr(out)}"

def prop_renaming(run, x):
    """PROPERTY: Renaming all stops bijectively does not change the answer."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n = int(first[0])
    # collect all stop names from trip lines
    trips = [line.split() for line in lines[1:1+n]]
    all_names = []
    for s, t in trips:
        all_names.append(s)
        all_names.append(t)
    distinct = sorted(set(all_names))
    # create deterministic mapping: name -> "R_" + str(index)
    mapping = {name: f"R_{i}" for i, name in enumerate(distinct)}
    # rename trips
    new_trips = []
    for s, t in trips:
        new_trips.append(f"{mapping[s]} {mapping[t]}")
    # rebuild input
    new_first = ' '.join(first)  # same numbers
    new_x = new_first + '\n' + '\n'.join(new_trips) + '\n'
    out_orig = run(x)
    out_new = run(new_x)
    # compare integer values
    val_orig = int(out_orig.strip())
    val_new = int(out_new.strip())
    assert val_orig == val_new, f"Renaming changed output: {val_orig} vs {val_new}"

def prop_monotonic_k(run, x):
    """PROPERTY: Increasing k does not increase the minimal cost."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, a, b, k, f = map(int, first)
    # increase k by 1, but cap at 300 (spec limit)
    k_new = min(k + 1, 300)
    if k_new == k:
        # cannot increase, skip by returning early (no assertion needed)
        return
    new_first = f"{n} {a} {b} {k_new} {f}"
    new_x = new_first + '\n' + '\n'.join(lines[1:]) + '\n'
    out_orig = int(run(x).strip())
    out_new = int(run(new_x).strip())
    assert out_orig >= out_new, f"Cost increased when k increased: {out_orig} -> {out_new}"

def prop_monotonic_f(run, x):
    """PROPERTY: Increasing f does not decrease the minimal cost."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, a, b, k, f = map(int, first)
    # increase f by 1, cap at 1000 (spec limit)
    f_new = min(f + 1, 1000)
    if f_new == f:
        return
    new_first = f"{n} {a} {b} {k} {f_new}"
    new_x = new_first + '\n' + '\n'.join(lines[1:]) + '\n'
    out_orig = int(run(x).strip())
    out_new = int(run(new_x).strip())
    assert out_orig <= out_new, f"Cost decreased when f increased: {out_orig} -> {out_new}"

def prop_bounds(run, x):
    """PROPERTY: Output lies between base_cost - max_saving and base_cost."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, a, b, k, f = map(int, first)
    trips = [line.split() for line in lines[1:1+n]]
    # compute base cost and route costs
    base = 0
    prev_end = None
    route_costs = {}
    for s, t in trips:
        # cost of this trip without cards
        if prev_end is not None and s == prev_end:
            cost = b
        else:
            cost = a
        base += cost
        # unordered route key
        route = tuple(sorted((s, t)))
        route_costs[route] = route_costs.get(route, 0) + cost
        prev_end = t
    # maximum possible saving by buying up to k cards
    savings = []
    for total in route_costs.values():
        if total > f:
            savings.append(total - f)
    savings.sort(reverse=True)
    max_saving = sum(savings[:k])  # top min(k, len(savings)) savings
    lower = base - max_saving
    upper = base
    out = int(run(x).strip())
    assert lower <= out <= upper, f"Output {out} not in [{lower}, {upper}]"