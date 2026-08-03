def prop_output_format_and_modulo(run, x):
    """PROPERTY: Output is a single integer within [0, 10^9+6] inclusive, modulo 10^9+7."""
    out = run(x)
    parsed = out.strip()
    val = int(parsed)
    mod = 10**9 + 7
    assert 0 <= val < mod, f"Output {val} not in [0, {mod})"
    return True

def prop_permutation_invariant(run, x):
    """PROPERTY: Permuting computer coordinates does not change the answer."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return True
    n = int(lines[0].strip())
    coords = list(map(int, lines[1].split()))
    import random
    rng = random.Random(42)
    shuffled = coords.copy()
    rng.shuffle(shuffled)
    new_input = f"{n}\n" + " ".join(map(str, shuffled)) + "\n"
    out1 = run(x)
    out2 = run(new_input)
    val1 = int(out1.strip())
    val2 = int(out2.strip())
    mod = 10**9 + 7
    assert (val1 - val2) % mod == 0, f"Permutation changed result: {val1} vs {val2}"
    return True

def prop_linear_scaling_and_translation(run, x):
    """PROPERTY: Translating all coordinates by a constant does not change the answer."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return True
    n = int(lines[0].strip())
    coords = list(map(int, lines[1].split()))
    t = 1000
    translated = [c + t for c in coords]
    new_input = f"{n}\n" + " ".join(map(str, translated)) + "\n"
    out1 = run(x)
    out2 = run(new_input)
    val1 = int(out1.strip())
    val2 = int(out2.strip())
    mod = 10**9 + 7
    assert (val1 - val2) % mod == 0, f"Translation changed result: {val1} vs {val2}"
    return True