import random

def prop_format(run, x):
    """PROPERTY: Output must be exactly 'sjfnb\\n' or 'cslnb\\n'."""
    out = run(x)
    assert out in ("sjfnb\n", "cslnb\n"), f"Invalid output: {repr(out)}"

def prop_permutation_invariant(run, x):
    """PROPERTY: Permuting the pile sizes does not change the outcome."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return  # malformed input, but property holds vacuously
    n = int(lines[0].strip())
    a = list(map(int, lines[1].split()))
    if n <= 1:
        return  # permutation trivial
    # Use reversal as a simple nontrivial permutation (if not palindrome)
    rev_a = a[::-1]
    if rev_a == a:
        # if symmetric, still a permutation, but output must match itself
        pass
    # Build new input with reversed list
    new_x = f"{n}\n" + " ".join(map(str, rev_a)) + "\n"
    out1 = run(x)
    out2 = run(new_x)
    assert out1 == out2, f"Output differs after permutation: {out1} vs {out2}"

def prop_n1_parity(run, x):
    """PROPERTY: For n=1, first player wins iff a1 is odd."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n = int(lines[0].strip())
    if n != 1:
        return
    a = list(map(int, lines[1].split()))
    if len(a) != 1:
        return
    a1 = a[0]
    expected = "sjfnb\n" if a1 % 2 == 1 else "cslnb\n"
    out = run(x)
    assert out == expected, f"For n=1, a1={a1}, expected {expected.strip()} got {out.strip()}"

def prop_all_zeros_lose(run, x):
    """PROPERTY: If all piles are zero, first player loses (cslnb)."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    a = list(map(int, lines[1].split()))
    if all(v == 0 for v in a):
        out = run(x)
        assert out == "cslnb\n", f"All zeros should output cslnb, got {out.strip()}"

def prop_n2_consecutive_lose(run, x):
    """PROPERTY: For n=2, if the two piles differ by 1, first player loses."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n = int(lines[0].strip())
    if n != 2:
        return
    a = list(map(int, lines[1].split()))
    if len(a) != 2:
        return
    s = sorted(a)
    if s[1] - s[0] == 1:
        out = run(x)
        assert out == "cslnb\n", f"For n=2, piles {a} differ by 1, expected cslnb, got {out.strip()}"