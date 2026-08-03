def prop_output_format_and_bounds(run, x):
    """PROPERTY: Output must have n lines, each parseable as an integer in [0, 998244353)."""
    out = run(x).strip()
    if out == "":
        return False
    lines = out.splitlines()
    # parse n from input
    n = int(x.split()[0])
    if len(lines) != n:
        return False
    mod = 998244353
    for line in lines:
        try:
            val = int(line.strip())
        except ValueError:
            return False
        if not (0 <= val < mod):
            return False
    return True

def prop_permutation_symmetry(run, x):
    """PROPERTY: Permuting pictures with their likes and weights permutes outputs accordingly."""
    import random
    lines = x.strip().splitlines()
    parts = [list(map(int, line.split())) for line in lines]
    n, m = parts[0]
    likes = parts[1]
    weights = parts[2]
    # create a random permutation
    perm = list(range(n))
    random.shuffle(perm)
    # apply permutation to likes and weights
    likes_perm = [likes[i] for i in perm]
    weights_perm = [weights[i] for i in perm]
    # build new input
    new_x = f"{n} {m}\n" + " ".join(map(str, likes_perm)) + "\n" + " ".join(map(str, weights_perm)) + "\n"
    out1 = run(x).strip().splitlines()
    out2 = run(new_x).strip().splitlines()
    # permute out1 according to perm
    out1_perm = [out1[i] for i in perm]
    return out1_perm == out2