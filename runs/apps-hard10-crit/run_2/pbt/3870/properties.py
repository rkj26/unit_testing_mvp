def prop_output_is_integer_and_nonnegative(run, x):
    """PROPERTY: Output is a valid integer >= 0."""
    out = run(x)
    val = int(out.strip())
    assert val >= 0, f"Output must be non-negative, got {val}"

def prop_permuting_ciel_cards_does_not_change_answer(run, x):
    """PROPERTY: Permuting Ciel's card order does not affect maximal damage."""
    lines = x.strip().split('\n')
    n, m = map(int, lines[0].split())
    jiro_part = lines[1:1+n]
    ciel_part = lines[1+n:1+n+m]
    import random
    rng = random.Random(42)
    shuffled_ciel = ciel_part[:]
    rng.shuffle(shuffled_ciel)
    new_input = '\n'.join([f"{n} {m}"] + jiro_part + shuffled_ciel)
    orig_out = int(run(x).strip())
    new_out = int(run(new_input).strip())
    assert orig_out == new_out, f"Permuting Ciel's cards changed damage: {orig_out} vs {new_out}"