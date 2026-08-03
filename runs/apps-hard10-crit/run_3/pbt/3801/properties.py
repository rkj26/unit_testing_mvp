def prop_output_format_and_mod_range(run, x):
    """PROPERTY: Output must have n lines, each an integer in [0, 998244353)."""
    out = run(x).strip()
    if out == '':
        return False
    lines = out.splitlines()
    n = int(x.split('\n')[0].split()[0])
    if len(lines) != n:
        return False
    for line in lines:
        val = int(line.strip())
        if not (0 <= val < 998244353):
            return False
    return True

def prop_linearity_for_single_visit(run, x):
    """PROPERTY: For m=1, expected weight = w_i + (like_i - dislike_i) * w_i / S0, computed modulo."""
    lines = x.strip().split('\n')
    n, m = map(int, lines[0].split())
    if m != 1:
        return True
    likes = list(map(int, lines[1].split()))
    weights = list(map(int, lines[2].split()))
    S0 = sum(weights)
    MOD = 998244353
    out = run(x).strip().splitlines()
    for i in range(n):
        a_i = 1 if likes[i] == 1 else -1
        inv_S0 = pow(S0, MOD-2, MOD)
        expected_mod = (weights[i] * (S0 + a_i) * inv_S0) % MOD
        if int(out[i]) != expected_mod:
            return False
    return True