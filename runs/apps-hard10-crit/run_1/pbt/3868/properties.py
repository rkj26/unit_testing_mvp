def prop_output_format(run, x):
    """PROPERTY: Output must be a single integer possibly -1, followed by newline."""
    out = run(x)
    lines = out.strip().split('\n')
    assert len(lines) == 1, "Output must be exactly one line"
    val = lines[0].strip()
    assert val.lstrip('-').isdigit(), "Output must be an integer"
    return True

def prop_cost_nonnegative_or_minus_one(run, x):
    """PROPERTY: If answer is not -1, it must be positive (costs are positive)."""
    out = run(x)
    lines = out.strip().split('\n')
    val = lines[0].strip()
    if val == '-1':
        return True
    num = int(val)
    assert num >= 0, "If not -1, total cost must be nonnegative"
    # All ticket costs are positive, and we need at least 2 flights per juror if possible, so cost > 0 if n>0
    # But we can't guarantee >0 if n=0? n>=1 per spec (1 ≤ n). So at least 2 flights per juror, cost >= 2.
    # However, flights may be missing, so answer could be -1, but if not -1, cost >= 2*n.
    # Let's check: if answer is not -1, cost must be positive.
    assert num > 0, "If not -1, total cost must be positive (at least one flight cost)"
    return True

def prop_metamorphic_permute_flight_order(run, x):
    """PROPERTY: Permuting flight lines arbitrarily does not change correct output."""
    lines = x.strip().split('\n')
    header = lines[0]
    flight_lines = lines[1:]
    import random
    rng = random.Random(42)  # deterministic
    shuffled = flight_lines[:]
    rng.shuffle(shuffled)
    new_x = header + '\n' + '\n'.join(shuffled) if shuffled else header + '\n'
    out1 = run(x).strip()
    out2 = run(new_x).strip()
    # If either is '-1', both must be '-1' because same multiset of flights.
    # But careful: if input ends with newline, preserve. We'll compare stripped.
    if out1 == '-1' or out2 == '-1':
        assert out1 == out2, "Permuting flight lines should not change feasibility"
    else:
        # Both are numbers, must be equal
        assert int(out1) == int(out2), "Permuting flight lines should not change minimal cost"
    return True