import random

def prop_output_format(run, x):
    """PROPERTY: Output must be exactly 'sjfnb' or 'cslnb', case-sensitive, possibly with newline."""
    out = run(x).strip()
    assert out in {"sjfnb", "cslnb"}, f"Invalid output: {out}"

def prop_sorted_invariant(run, x):
    """PROPERTY: Sorting the pile sizes does not change the outcome."""
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    a = list(map(int, lines[1].split()))
    sorted_a = sorted(a)
    new_x = f"{n}\n{' '.join(map(str, sorted_a))}\n"
    out1 = run(x).strip()
    out2 = run(new_x).strip()
    assert out1 == out2, f"Output differs after sorting: {out1} vs {out2}"

def prop_game_theoretic_consistency(run, x):
    """PROPERTY: If output is 'sjfnb', there exists a legal move to a position with output 'cslnb'; if 'cslnb', all legal moves lead to 'sjfnb'."""
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    a = list(map(int, lines[1].split()))
    out = run(x).strip()
    legal_moves = []
    for i in range(n):
        if a[i] == 0:
            continue
        new_a = a.copy()
        new_a[i] -= 1
        if len(set(new_a)) == n:  # all distinct -> legal move
            legal_moves.append(new_a)
    outcomes = []
    for new_a in legal_moves:
        new_x = f"{n}\n{' '.join(map(str, new_a))}\n"
        new_out = run(new_x).strip()
        outcomes.append(new_out)
    if out == "sjfnb":
        assert any(o == "cslnb" for o in outcomes), f"No winning move found from winning position. Outcomes: {outcomes}"
    else:
        assert all(o == "sjfnb" for o in outcomes), f"Found a move to losing position from losing position. Outcomes: {outcomes}"

def prop_single_pile(run, x):
    """PROPERTY: For n=1, output is 'cslnb' iff a1=0, else 'sjfnb'."""
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    if n != 1:
        return
    a1 = int(lines[1].strip())
    out = run(x).strip()
    if a1 == 0:
        assert out == "cslnb", f"Expected cslnb for single pile of size 0, got {out}"
    else:
        assert out == "sjfnb", f"Expected sjfnb for single pile of size >0, got {out}"

def prop_all_zero(run, x):
    """PROPERTY: If all piles are zero, output must be 'cslnb'."""
    lines = x.strip().splitlines()
    n = int(lines[0].strip())
    a = list(map(int, lines[1].split()))
    if all(v == 0 for v in a):
        out = run(x).strip()
        assert out == "cslnb", f"Expected cslnb for all zero piles, got {out}"