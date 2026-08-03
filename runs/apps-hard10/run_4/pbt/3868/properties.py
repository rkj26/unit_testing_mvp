import random
import math

def prop_output_format(run, x):
    """PROPERTY: Output must be a single integer or -1."""
    out = run(x).strip()
    # Must be a single line
    lines = out.splitlines()
    assert len(lines) == 1, "Output must be exactly one line"
    val = lines[0]
    assert val in ("-1",) or (val.isdigit() and int(val) >= 0), \
        "Output must be non‑negative integer or -1"

def prop_empty_flights_impossible(run, x):
    """PROPERTY: If m=0 and n>0, output must be -1."""
    # Parse n, m, k from first line
    lines = x.strip().splitlines()
    if not lines:
        return
    parts = lines[0].split()
    if len(parts) < 3:
        return
    n, m, k = map(int, parts)
    if m == 0 and n > 0:
        out = run(x).strip()
        assert out == "-1", f"With m=0, n={n}>0, impossible => -1, got {out}"

def prop_all_zero_cost_flights_possible(run, x):
    """PROPERTY: If all flights cost 0 and flights cover all cities both ways, output is 0."""
    # Build input where each city 1..n has at least one flight to 0 before day D
    # and at least one flight from 0 back after day D+k, all cost 0.
    lines = x.strip().splitlines()
    if not lines:
        return
    first = lines[0].split()
    if len(first) < 3:
        return
    n, m, k = map(int, first)
    # We'll only apply if we can detect the property from given input.
    # Instead, we construct a new input that satisfies the property.
    # Choose days: arrivals before day 100, departures after day 100+k
    D = 100
    new_lines = [f"{n} {2*n} {k}"]
    city = 1
    while city <= n:
        new_lines.append(f"{D-10} {city} 0 0")   # to Metropolis
        new_lines.append(f"{D+k+10} 0 {city} 0") # from Metropolis
        city += 1
    new_input = "\n".join(new_lines)
    out = run(new_input).strip()
    # Since cost is 0, minimal possible cost is 0
    assert out == "0", f"All zero‑cost flights covering all cities => cost 0, got {out}"

def prop_duplicate_flights_same_cost(run, x):
    """PROPERTY: Duplicating all flights (same day, cities, cost) yields same output."""
    out1 = run(x).strip()
    # Duplicate each flight line
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    header = lines[0]
    rest = lines[1:]
    new_rest = []
    for line in rest:
        new_rest.append(line)
        new_rest.append(line)  # duplicate
    n, m_orig, k = map(int, header.split())
    new_header = f"{n} {2*m_orig} {k}"
    new_input = "\n".join([new_header] + new_rest)
    out2 = run(new_input).strip()
    # Adding exact duplicate flights cannot change optimal cost
    assert out1 == out2, f"Duplicating flights changed output: {out1} vs {out2}"

def prop_permute_city_ids(run, x):
    """PROPERTY: Permuting city IDs 1..n (keeping 0 fixed) yields same output."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    header = lines[0].split()
    n, m, k = map(int, header[:3])
    if n <= 1:
        return  # permutation trivial
    # Generate a random permutation of 1..n
    perm = list(range(1, n+1))
    random.seed(12345)  # deterministic for testing
    random.shuffle(perm)
    perm_map = {0:0}
    for idx, val in enumerate(perm, start=1):
        perm_map[idx] = val
    inv_map = {v:k for k,v in perm_map.items()}
    new_lines = [f"{n} {m} {k}"]
    for line in lines[1:]:
        parts = line.split()
        d, f, t, c = map(int, parts)
        f_new = perm_map.get(f, f)
        t_new = perm_map.get(t, t)
        new_lines.append(f"{d} {f_new} {t_new} {c}")
    new_input = "\n".join(new_lines)
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    # Permuting city labels does not change the combinatorial problem
    assert out1 == out2, f"Permuting city IDs changed output: {out1} vs {out2}"