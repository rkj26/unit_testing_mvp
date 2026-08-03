def prop_output_is_integer(run, x):
    """PROPERTY: Output is a non-negative integer followed by newline."""
    out = run(x).strip()
    val = int(out)
    assert val >= 0
    assert out == str(val)

def prop_k_zero_means_no_cards(run, x):
    """PROPERTY: If k=0, answer equals sum of trip costs without cards."""
    lines = x.strip().splitlines()
    n, a, b, k, f = map(int, lines[0].split())
    if k != 0:
        return
    trips = [line.split() for line in lines[1:1+n]]
    total = 0
    prev_end = None
    for start, end in trips:
        if prev_end == start:
            total += b
        else:
            total += a
        prev_end = end
    out = int(run(x).strip())
    assert out == total

def prop_monotonic_in_k(run, x):
    """PROPERTY: Increasing k cannot increase the minimal total cost."""
    lines = x.strip().splitlines()
    n, a, b, k, f = map(int, lines[0].split())
    if k == 0:
        return
    new_header = f"{n} {a} {b} {k-1} {f}"
    new_input = new_header + "\n" + "\n".join(lines[1:]) + "\n"
    out_full = int(run(x).strip())
    out_reduced = int(run(new_input).strip())
    assert out_full <= out_reduced