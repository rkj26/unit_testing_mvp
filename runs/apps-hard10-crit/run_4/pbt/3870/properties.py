def prop_output_format_and_range(run, x):
    """PROPERTY: Output is a single integer (possibly 0) followed by newline, within valid damage bounds."""
    out = run(x)
    # Must be a single line with an integer
    lines = out.strip().splitlines()
    assert len(lines) == 1, "Output must be exactly one line"
    val_str = lines[0].strip()
    assert val_str.isdigit() or (val_str[0] == '-' and val_str[1:].isdigit()), "Output must be an integer"
    damage = int(val_str)
    # Upper bound: all Ciel cards used to directly attack with no Jiro cards alive,
    # each dealing its full strength.
    # Parse input to compute max possible damage.
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    ciel_cards = []
    idx = 1 + n
    for _ in range(m):
        ciel_cards.append(int(lines[idx].strip()))
        idx += 1
    max_possible = sum(ciel_cards)
    # Lower bound: Ciel could choose to do zero damage.
    assert 0 <= damage <= max_possible, f"Damage {damage} outside possible range [0, {max_possible}]"

def prop_damage_non_decreasing_when_ciel_card_added(run, x):
    """PROPERTY: Adding an extra Ciel card (strength >= 0) cannot decrease max damage."""
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    # Build new input with one extra Ciel card of strength 0 (weakest possible addition).
    new_m = m + 1
    new_first_line = f"{n} {new_m}"
    new_lines = [new_first_line] + lines[1:] + ["0"]  # append a card of strength 0
    new_input = "\n".join(new_lines)
    orig_out = run(x).strip()
    new_out = run(new_input).strip()
    orig_dmg = int(orig_out)
    new_dmg = int(new_out)
    # Extra card can be ignored, so damage should not decrease.
    assert new_dmg >= orig_dmg, f"Adding a Ciel card decreased damage: {orig_dmg} -> {new_dmg}"

def prop_permute_ciel_cards_invariant(run, x):
    """PROPERTY: Permuting Ciel's card strengths does not change maximal damage."""
    import random
    rng = random.Random(42)  # fixed seed for deterministic test
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    if m <= 1:
        return  # permutation trivial
    idx = 1 + n
    pre = lines[:idx]
    ciel = lines[idx:]
    shuffled = ciel[:]
    rng.shuffle(shuffled)
    new_input = "\n".join(pre + shuffled)
    orig_out = run(x).strip()
    new_out = run(new_input).strip()
    assert orig_out == new_out, f"Permuting Ciel cards changed output: {orig_out} vs {new_out}"