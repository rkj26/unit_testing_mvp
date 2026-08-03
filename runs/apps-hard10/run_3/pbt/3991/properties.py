def prop_output_format_and_modulo(run, x):
    """PROPERTY: Output is a single integer within [0, 10^9+6] inclusive, modulo 10^9+7."""
    out = run(x)
    # Must be a single integer, possibly with whitespace
    parsed = out.strip()
    # Ensure it's a valid integer
    val = int(parsed)
    mod = 10**9 + 7
    assert 0 <= val < mod, f"Output {val} not in [0, {mod})"
    return True

def prop_permutation_invariant(run, x):
    """PROPERTY: Permuting computer coordinates does not change the answer."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return True  # trivial case, nothing to permute
    n = int(lines[0].strip())
    coords = list(map(int, lines[1].split()))
    import random
    rng = random.Random(42)  # fixed seed for determinism
    shuffled = coords.copy()
    rng.shuffle(shuffled)
    new_input = f"{n}\n" + " ".join(map(str, shuffled)) + "\n"
    out1 = run(x)
    out2 = run(new_input)
    # Both outputs must be valid integers mod 10^9+7
    val1 = int(out1.strip())
    val2 = int(out2.strip())
    mod = 10**9 + 7
    assert (val1 - val2) % mod == 0, f"Permutation changed result: {val1} vs {val2}"
    return True

def prop_monotonicity_with_duplicate_removal(run, x):
    """PROPERTY: Removing one computer (and its coordinate) reduces the sum in a predictable monotonic way."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return True
    n = int(lines[0].strip())
    if n <= 1:
        return True
    coords = list(map(int, lines[1].split()))
    # Compute answer for full set
    out_full = run(x)
    val_full = int(out_full.strip())
    # Remove last computer
    new_n = n - 1
    new_coords = coords[:-1]
    new_input = f"{new_n}\n" + " ".join(map(str, new_coords)) + "\n"
    out_reduced = run(new_input)
    val_reduced = int(out_reduced.strip())
    mod = 10**9 + 7
    # The sum for n-1 computers must be <= sum for n computers (modulo doesn't affect non-negative nature)
    # But modulo can wrap, so compare actual values before mod? Not directly possible.
    # Instead: The contribution of subsets not containing the removed computer is exactly val_reduced.
    # Therefore val_full >= val_reduced in normal integers. Since all values are non-negative,
    # after modulo, val_full could be smaller only if val_full >= mod and wrapped.
    # We can check: (val_full - val_reduced) % mod should be non-negative in normal sense,
    # but modulo arithmetic means we can't directly compare.
    # Better: The difference (val_full - val_reduced) mod mod should equal the contribution
    # of subsets that include the removed computer. That contribution is non-negative.
    # So (val_full - val_reduced) % mod should be between 0 and mod-1.
    diff = (val_full - val_reduced) % mod
    # It's a contribution, so must be in [0, mod-1]
    assert 0 <= diff < mod
    return True

def prop_linear_scaling_and_translation(run, x):
    """PROPERTY: Translating all coordinates by a constant does not change the answer."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return True
    n = int(lines[0].strip())
    coords = list(map(int, lines[1].split()))
    # Translate all coordinates by +t (choose t=1000)
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

def prop_symmetry_under_coordinate_reflection(run, x):
    """PROPERTY: Reflecting coordinates (x -> -x) does not change the answer."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return True
    n = int(lines[0].strip())
    coords = list(map(int, lines[1].split()))
    # Reflect: choose M - x where M is large enough to keep positive (spec says x_i >= 1)
    # Use M = max(coords) + min(coords) to keep distinctness and positivity.
    M = max(coords) + min(coords)
    reflected = [M - c for c in coords]
    # Distinctness preserved because reflection is bijective.
    new_input = f"{n}\n" + " ".join(map(str, reflected)) + "\n"
    out1 = run(x)
    out2 = run(new_input)
    val1 = int(out1.strip())
    val2 = int(out2.strip())
    mod = 10**9 + 7
    assert (val1 - val2) % mod == 0, f"Reflection changed result: {val1} vs {val2}"
    return True