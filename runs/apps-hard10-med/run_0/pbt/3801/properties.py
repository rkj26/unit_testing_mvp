MOD = 998244353

def parse_input(x):
    lines = x.strip().splitlines()
    first = lines[0].strip().split()
    n, m = map(int, first)
    a = list(map(int, lines[1].strip().split()))
    w = list(map(int, lines[2].strip().split()))
    return n, m, a, w

def parse_output(out):
    lines = out.strip().split()
    return list(map(int, lines)) if lines else []

def prop_output_format(run, x):
    """PROPERTY: Output consists of n integers each in [0, MOD-1], one per line."""
    n, m, a, w = parse_input(x)
    out = run(x)
    vals = parse_output(out)
    assert len(vals) == n, f"Expected {n} output numbers, got {len(vals)}"
    for v in vals:
        assert 0 <= v < MOD, f"Output value {v} out of range [0, {MOD-1}]"

def prop_permutation_symmetry(run, x):
    """PROPERTY: Permuting pictures permutes outputs accordingly."""
    n, m, a, w = parse_input(x)
    if n < 2:
        return
    # swap indices 0 and 1
    perm = list(range(n))
    perm[0], perm[1] = perm[1], perm[0]
    a_perm = [a[perm[i]] for i in range(n)]
    w_perm = [w[perm[i]] for i in range(n)]
    lines = x.strip().splitlines()
    new_lines = [lines[0], ' '.join(map(str, a_perm)), ' '.join(map(str, w_perm))]
    x_perm = '\n'.join(new_lines)
    out_orig = run(x)
    out_perm = run(x_perm)
    vals_orig = parse_output(out_orig)
    vals_perm = parse_output(out_perm)
    assert len(vals_orig) == n and len(vals_perm) == n
    for i in range(n):
        assert vals_perm[i] == vals_orig[perm[i]], f"Mismatch at permuted index {i}"

def prop_single_liked_picture(run, x):
    """PROPERTY: For n=1 and liked picture, output = (w1 + m) mod MOD."""
    n, m, a, w = parse_input(x)
    if n == 1 and a[0] == 1:
        out = run(x)
        vals = parse_output(out)
        assert len(vals) == 1
        expected = (w[0] + m) % MOD
        assert vals[0] == expected, f"Expected {expected}, got {vals[0]}"

def prop_small_bruteforce(run, x):
    """PROPERTY: For small n,m,w (n<=3, m<=3, max(w)<=3), output matches brute-force computation."""
    n, m, a, w = parse_input(x)
    if n <= 3 and m <= 3 and max(w) <= 3:
        from fractions import Fraction
        from itertools import product
        def brute_expected():
            exp = [Fraction(0,1) for _ in range(n)]
            for seq in product(range(n), repeat=m):
                weights = w[:]
                prob = Fraction(1,1)
                for idx in seq:
                    total = sum(weights)
                    prob *= Fraction(weights[idx], total)
                    if a[idx] == 1:
                        weights[idx] += 1
                    else:
                        weights[idx] -= 1
                for i in range(n):
                    exp[i] += prob * weights[i]
            return exp
        expected = brute_expected()
        out = run(x)
        vals = parse_output(out)
        assert len(vals) == n
        for i in range(n):
            num, den = expected[i].numerator, expected[i].denominator
            r = (num * pow(den, MOD-2, MOD)) % MOD
            assert vals[i] == r, f"Picture {i}: expected {r}, got {vals[i]}"

def prop_m1_explicit(run, x):
    """PROPERTY: For m=1, output matches explicit formula."""
    n, m, a, w = parse_input(x)
    if m == 1:
        from math import gcd
        total = sum(w)
        out = run(x)
        vals = parse_output(out)
        assert len(vals) == n
        for i in range(n):
            num = w[i] * (total + (2*a[i] - 1))
            den = total
            g = gcd(num, den)
            num //= g
            den //= g
            r = (num * pow(den, MOD-2, MOD)) % MOD
            assert vals[i] == r, f"Picture {i}: expected {r}, got {vals[i]}"