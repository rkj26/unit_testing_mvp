def prop_output_format(run, x):
    """PROPERTY: Output must be exactly 'sjfnb' or 'cslnb' followed by newline."""
    out = run(x)
    assert out in ("sjfnb\n", "cslnb\n"), f"Invalid output: {repr(out)}"

def prop_permutation_invariance(run, x):
    """PROPERTY: Permuting pile sizes does not change the winner."""
    lines = x.strip().split('\n')
    if len(lines) < 2:
        return
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    if len(a) != n:
        return
    import random
    random.seed(42)  # deterministic
    perm = a[:]
    random.shuffle(perm)
    x2 = f"{n}\n" + " ".join(map(str, perm)) + "\n"
    out1 = run(x)
    out2 = run(x2)
    assert out1 == out2, f"Winner changed after permutation: {out1} vs {out2}"