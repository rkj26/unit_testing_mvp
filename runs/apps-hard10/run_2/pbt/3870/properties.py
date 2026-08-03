def prop_output_is_integer_and_nonnegative(run, x):
    """PROPERTY: Output is a valid integer >= 0."""
    out = run(x)
    # Must be a single integer, possibly with whitespace
    val = int(out.strip())
    assert val >= 0, f"Output must be non-negative, got {val}"

def prop_adding_useless_card_does_not_decrease_damage(run, x):
    """PROPERTY: Adding a Ciel card with strength 0 cannot reduce max damage."""
    lines = x.strip().split('\n')
    n, m = map(int, lines[0].split())
    new_lines = [f"{n} {m+1}"] + lines[1:] + ["0"]  # add a zero-strength card
    new_input = '\n'.join(new_lines)
    orig_out = int(run(x).strip())
    new_out = int(run(new_input).strip())
    assert new_out >= orig_out, f"Adding a zero-strength card decreased damage from {orig_out} to {new_out}"

def prop_duplicating_all_cards_doubles_damage_or_more(run, x):
    """PROPERTY: Duplicating all cards (Jiro and Ciel) cannot reduce total damage, and can at least double it."""
    lines = x.strip().split('\n')
    n, m = map(int, lines[0].split())
    # Duplicate Jiro's cards
    jiro_cards = lines[1:1+n]
    # Duplicate Ciel's cards
    ciel_cards = lines[1+n:1+n+m]
    new_n = 2*n
    new_m = 2*m
    new_lines = [f"{new_n} {new_m}"] + jiro_cards + jiro_cards + ciel_cards + ciel_cards
    new_input = '\n'.join(new_lines)
    orig_out = int(run(x).strip())
    new_out = int(run(new_input).strip())
    # Using the same strategy twice yields at least 2*orig damage
    assert new_out >= 2 * orig_out, f"Duplicating all cards did not at least double damage: {orig_out} -> {new_out}"

def prop_permuting_ciel_cards_does_not_change_answer(run, x):
    """PROPERTY: Permuting Ciel's card order does not affect maximal damage."""
    lines = x.strip().split('\n')
    n, m = map(int, lines[0].split())
    jiro_part = lines[1:1+n]
    ciel_part = lines[1+n:1+n+m]
    import random
    rng = random.Random(42)  # fixed seed for reproducibility
    shuffled_ciel = ciel_part[:]
    rng.shuffle(shuffled_ciel)
    new_input = '\n'.join([f"{n} {m}"] + jiro_part + shuffled_ciel)
    orig_out = int(run(x).strip())
    new_out = int(run(new_input).strip())
    assert orig_out == new_out, f"Permuting Ciel's cards changed damage: {orig_out} vs {new_out}"

def prop_increasing_ciel_strengths_does_not_decrease_damage(run, x):
    """PROPERTY: Increasing strength of any Ciel card cannot reduce maximal damage."""
    lines = x.strip().split('\n')
    n, m = map(int, lines[0].split())
    jiro_part = lines[1:1+n]
    ciel_part = lines[1+n:1+n+m]
    # Increase each Ciel card strength by 1 (if possible)
    new_ciel = []
    for card in ciel_part:
        val = int(card)
        new_ciel.append(str(val + 1))
    new_input = '\n'.join([f"{n} {m}"] + jiro_part + new_ciel)
    orig_out = int(run(x).strip())
    new_out = int(run(new_input).strip())
    assert new_out >= orig_out, f"Increasing Ciel strengths decreased damage: {orig_out} -> {new_out}"