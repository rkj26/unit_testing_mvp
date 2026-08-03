def prop_output_format(run, x):
    """PROPERTY: Output must be exactly 'sjfnb' or 'cslnb' followed by a newline."""
    out = run(x)
    assert out in ("sjfnb\n", "cslnb\n"), f"Invalid output: {repr(out)}"

def prop_swap_two_piles(run, x):
    """PROPERTY: Swapping any two piles does not change the winner."""
    lines = x.strip().split("\n")
    if len(lines) < 2:
        return
    n = int(lines[0])
    if n < 2:
        return
    a = list(map(int, lines[1].split()))
    # swap first two piles
    b = a.copy()
    b[0], b[1] = b[1], b[0]
    new_x = f"{n}\n" + " ".join(map(str, b)) + "\n"
    out1 = run(x).strip()
    out2 = run(new_x).strip()
    assert out1 == out2, f"Swapping piles changed output: {out1} vs {out2}"

def prop_duplicate_all_zeros(run, x):
    """PROPERTY: Adding a zero to all piles (i.e., shifting all values up by same constant) preserves winner."""
    lines = x.strip().split("\n")
    if len(lines) < 2:
        return
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    # add 1 to all piles
    b = [v + 1 for v in a]
    new_x = f"{n}\n" + " ".join(map(str, b)) + "\n"
    out1 = run(x).strip()
    out2 = run(new_x).strip()
    assert out1 == out2, f"Adding 1 to all piles changed output: {out1} vs {out2}"

def prop_single_pile_zero(run, x):
    """PROPERTY: If n=1 and pile is 0, winner must be cslnb."""
    lines = x.strip().split("\n")
    if len(lines) < 2:
        return
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    if n == 1 and a[0] == 0:
        out = run(x).strip()
        assert out == "cslnb", f"Single empty pile should lose, got {out}"

def prop_two_piles_same_nonzero(run, x):
    """PROPERTY: If n=2 and piles are equal nonzero, winner must be sjfnb."""
    lines = x.strip().split("\n")
    if len(lines) < 2:
        return
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    if n == 2 and a[0] == a[1] and a[0] > 0:
        out = run(x).strip()
        assert out == "sjfnb", f"Two equal nonzero piles should win, got {out}"