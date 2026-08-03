def prop_output_is_integer_and_within_bounds(run, x):
    """PROPERTY: Output is a single integer within plausible bounds."""
    out = run(x).strip()
    lines = out.splitlines()
    assert len(lines) == 1, "Output must be exactly one line"
    val = int(lines[0])
    assert val >= 0, "Total cost cannot be negative"
    lines_in = x.strip().splitlines()
    first = list(map(int, lines_in[0].split()))
    n, a, _, k, f = first[:5]
    max_possible = n * a + k * f
    assert val <= max_possible, f"Cost {val} exceeds trivial upper bound {max_possible}"

def prop_monotonic_in_k(run, x):
    """PROPERTY: Increasing k (max cards allowed) cannot increase total cost."""
    lines_in = x.strip().splitlines()
    first = list(map(int, lines_in[0].split()))
    n, a, b, k, f = first[:5]
    if k == 300:
        return
    new_first = f"{n} {a} {b} {k+1} {f}"
    new_x = new_first + "\n" + "\n".join(lines_in[1:])
    out1 = int(run(x).strip())
    out2 = int(run(new_x).strip())
    assert out2 <= out1, f"Cost should not increase when k increases: {out2} > {out1}"