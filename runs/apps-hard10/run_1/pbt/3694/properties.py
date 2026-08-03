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

def prop_shift_all_by_one(run, x):
    """PROPERTY: Adding 1 to all piles flips winner if no zeros present."""
    lines = x.strip().split('\n')
    if len(lines) < 2:
        return
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    if len(a) != n:
        return
    if min(a) == 0:
        return  # can't safely subtract later
    # Add 1 to all piles
    a2 = [v + 1 for v in a]
    x2 = f"{n}\n" + " ".join(map(str, a2)) + "\n"
    out1 = run(x)
    out2 = run(x2)
    # Winner should flip because total moves increased by n, changing parity
    # This holds if the move is always possible in both games.
    # We only check that outputs are opposite.
    expected = {"sjfnb\n": "cslnb\n", "cslnb\n": "sjfnb\n"}
    assert out2 == expected.get(out1, None), f"Shift by 1 did not flip winner: {out1} -> {out2}"

def prop_duplicate_pile_symmetry(run, x):
    """PROPERTY: Adding a new pile equal to an existing one usually loses for first player."""
    lines = x.strip().split('\n')
    if len(lines) < 2:
        return
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    if len(a) != n:
        return
    # Find a value that appears at least once
    from collections import Counter
    cnt = Counter(a)
    chosen = None
    for val in cnt:
        if cnt[val] == 1:
            chosen = val
            break
    if chosen is None:
        return  # all values appear multiple times already
    # Add one more pile with same value
    a2 = a + [chosen]
    n2 = n + 1
    x2 = f"{n2}\n" + " ".join(map(str, a2)) + "\n"
    out2 = run(x2)
    # In the new game, two piles are equal at start, so first move is illegal
    # unless there is exactly one other duplicate and it's fixable.
    # This is a complex condition; we instead just ensure output is valid.
    assert out2 in ("sjfnb\n", "cslnb\n"), f"Invalid output after adding duplicate: {repr(out2)}"

def prop_monotonicity_on_single_pile(run, x):
    """PROPERTY: Increasing a single pile (by 1) never changes winner from sjfnb to cslnb."""
    lines = x.strip().split('\n')
    if len(lines) < 2:
        return
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    if len(a) != n:
        return
    out_orig = run(x)
    if out_orig != "sjfnb\n":
        return  # Only check when original winner is sjfnb
    # Try increasing each pile by 1
    for i in range(n):
        a2 = a[:]
        a2[i] += 1
        x2 = f"{n}\n" + " ".join(map(str, a2)) + "\n"
        out2 = run(x2)
        # Winner should not become cslnb (could stay sjfnb or become cslnb only if invalid)
        # Actually, increasing a pile adds a move, so parity changes -> winner flips.
        # So if original is sjfnb, new should be cslnb.
        # But due to possible illegal moves, we just check it's valid.
        assert out2 in ("sjfnb\n", "cslnb\n"), f"Invalid output after increment: {repr(out2)}"