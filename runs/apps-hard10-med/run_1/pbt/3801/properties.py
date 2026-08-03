import math

MOD = 998244353

def prop_examples(run, x):
    """PROPERTY: The program must produce the correct outputs for the three given examples."""
    example_inputs = [
        "2 1\n0 1\n2 1\n",
        "1 2\n1\n1\n",
        "3 3\n0 1 1\n4 3 5\n"
    ]
    expected_outputs = [
        ["332748119", "332748119"],
        ["3"],
        ["160955686", "185138929", "974061117"]
    ]
    for inp, exp in zip(example_inputs, expected_outputs):
        out = run(inp).strip()
        got = out.split()
        assert got == exp, f"Example failed: input {inp!r} got {got} expected {exp}"

def prop_single_liked(run, x):
    """PROPERTY: If there is exactly one picture and it is liked, the output must be (w1 + m) mod MOD."""
    lines = x.strip().splitlines()
    if len(lines) < 3:
        return
    first = list(map(int, lines[0].split()))
    if len(first) != 2:
        return
    n, m = first
    if n != 1:
        return
    a = list(map(int, lines[1].split()))
    w = list(map(int, lines[2].split()))
    if len(a) != 1 or len(w) != 1:
        return
    if a[0] != 1:
        return
    out = run(x).strip()
    out_vals = list(map(int, out.split()))
    if len(out_vals) != 1:
        assert False, "Output should have exactly one number"
    expected = (w[0] + m) % MOD
    assert out_vals[0] == expected, f"Single liked: expected {expected}, got {out_vals[0]}"

def prop_all_liked(run, x):
    """PROPERTY: If all pictures are liked, the sum of outputs modulo MOD must equal (sum(w) + m) mod MOD."""
    lines = x.strip().splitlines()
    if len(lines) < 3:
        return
    n, m = map(int, lines[0].split())
    a = list(map(int, lines[1].split()))
    w = list(map(int, lines[2].split()))
    if not all(ai == 1 for ai in a):
        return
    out = run(x).strip()
    out_vals = list(map(int, out.split()))
    if len(out_vals) != n:
        assert False, "Output length mismatch"
    total_w = sum(w)
    expected_sum = (total_w + m) % MOD
    got_sum = sum(out_vals) % MOD
    assert got_sum == expected_sum, f"All liked: sum expected {expected_sum}, got {got_sum}"

def prop_symmetry(run, x):
    """PROPERTY: Permuting the order of pictures permutes the outputs accordingly."""
    lines = x.strip().splitlines()
    if len(lines) < 3:
        return
    n, m = map(int, lines[0].split())
    a = list(map(int, lines[1].split()))
    w = list(map(int, lines[2].split()))
    if len(a) != n or len(w) != n:
        return
    out_orig = run(x).strip()
    orig_vals = list(map(int, out_orig.split()))
    if len(orig_vals) != n:
        assert False, "Original output length mismatch"
    # Reverse the order of pictures
    a_rev = a[::-1]
    w_rev = w[::-1]
    new_input = f"{n} {m}\n" + " ".join(map(str, a_rev)) + "\n" + " ".join(map(str, w_rev)) + "\n"
    out_perm = run(new_input).strip()
    perm_vals = list(map(int, out_perm.split()))
    if len(perm_vals) != n:
        assert False, "Permuted output length mismatch"
    for i in range(n):
        if orig_vals[i] != perm_vals[n-1-i]:
            assert False, (f"Symmetry failed: at index {i}, original {orig_vals[i]} "
                           f"!= permuted reversed {perm_vals[n-1-i]}")

def prop_m1(run, x):
    """PROPERTY: When m=1, the output must match the exact formula for expected weights."""
    lines = x.strip().splitlines()
    if len(lines) < 3:
        return
    n, m = map(int, lines[0].split())
    if m != 1:
        return
    a = list(map(int, lines[1].split()))
    w = list(map(int, lines[2].split()))
    out = run(x).strip()
    out_vals = list(map(int, out.split()))
    if len(out_vals) != n:
        assert False, "Output length mismatch"
    S = sum(w)
    for i in range(n):
        numer = w[i] * (S + 2*a[i] - 1)
        denom = S
        g = math.gcd(numer, denom)
        numer //= g
        denom //= g
        r = (numer * pow(denom, MOD-2, MOD)) % MOD
        assert out_vals[i] == r, f"m=1: picture {i}: expected {r}, got {out_vals[i]}"