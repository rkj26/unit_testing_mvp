def prop_output_format_and_bounds(run, x):
    """PROPERTY: Output must be a single integer, either -1 or a positive integer within possible total cost bounds."""
    out = run(x).strip()
    # Must be a single token
    tokens = out.split()
    assert len(tokens) == 1, "Output must be a single integer"
    val = tokens[0]
    # Must be valid integer
    try:
        n = int(val)
    except ValueError:
        assert False, "Output must be an integer"
    # If not -1, must be ≥ 0 (costs are positive, sum of positive costs is positive)
    if n != -1:
        assert n >= 0, "If not -1, output must be non‑negative"

def prop_permute_city_ids(run, x):
    """PROPERTY: Permuting non‑zero city IDs (1..n) in input yields same output (cost unchanged)."""
    lines = x.strip().split('\n')
    header = lines[0].split()
    n, m, k = map(int, header[:3])
    if n <= 1:
        return  # Permutation trivial
    # Build permutation of 1..n
    import random
    perm = list(range(1, n+1))
    random.shuffle(perm)
    # city 0 stays 0
    perm_map = {0:0}
    for i in range(1, n+1):
        perm_map[i] = perm[i-1]
    # Process flights
    new_lines = [f"{n} {m} {k}"]
    for line in lines[1:]:
        if not line.strip():
            continue
        d, f, t, c = map(int, line.split())
        fnew = perm_map[f]
        tnew = perm_map[t]
        new_lines.append(f"{d} {fnew} {tnew} {c}")
    new_input = '\n'.join(new_lines)
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    assert out1 == out2, "Permuting non‑zero city IDs should not change answer"

def prop_duplicate_flight_does_not_improve(run, x):
    """PROPERTY: Duplicating a flight (same day, cities, cost) yields same minimal cost."""
    lines = x.strip().split('\n')
    header = lines[0].split()
    n, m, k = map(int, header[:3])
    if m == 0:
        return
    # Pick first flight to duplicate
    first_flight_line = lines[1]
    # Build new input with one extra duplicate flight
    new_header = f"{n} {m+1} {k}"
    new_lines = [new_header] + lines[1:] + [first_flight_line]
    new_input = '\n'.join(new_lines)
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    assert out1 == out2, "Duplicating a flight should not change minimal cost"