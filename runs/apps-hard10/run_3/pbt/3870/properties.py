def prop_output_is_integer(run, x):
    """PROPERTY: Output must be a single integer."""
    out = run(x).strip()
    # Must be able to parse as integer
    int(out)  # raises ValueError if not
    # No extra whitespace or newlines besides optional trailing newline
    lines = out.splitlines()
    assert len(lines) == 1
    return True

def prop_damage_nonnegative(run, x):
    """PROPERTY: Maximal damage is nonnegative."""
    out = run(x).strip()
    dmg = int(out)
    assert dmg >= 0
    return True

def prop_monotonic_in_ciel_strengths(run, x):
    """PROPERTY: Increasing a Ciel card's strength cannot decrease max damage."""
    # Parse input
    lines = x.strip().splitlines()
    if not lines:
        return True
    n_m = list(map(int, lines[0].split()))
    n, m = n_m[0], n_m[1]
    # Skip Jiro's cards
    idx = 1
    for _ in range(n):
        idx += 1
    # Ciel's strengths start at idx
    strengths = []
    for i in range(m):
        strengths.append(int(lines[idx + i]))
    # Modify: increase first Ciel strength by 1 (if possible)
    if m > 0 and strengths[0] < 8000:
        new_strengths = strengths.copy()
        new_strengths[0] += 1
        # Rebuild input
        new_lines = lines[:idx] + [str(s) for s in new_strengths]
        new_x = '\n'.join(new_lines) + ('\n' if x.endswith('\n') else '')
        out_orig = int(run(x).strip())
        out_new = int(run(new_x).strip())
        assert out_new >= out_orig
    return True

def prop_adding_useless_ciel_card_does_not_decrease_damage(run, x):
    """PROPERTY: Adding a Ciel card with strength 0 cannot reduce max damage."""
    # Parse
    lines = x.strip().splitlines()
    if not lines:
        return True
    parts = list(map(int, lines[0].split()))
    n, m = parts[0], parts[1]
    # Build new input: increase m by 1, append a 0 strength card
    new_first_line = f"{n} {m+1}"
    new_lines = [new_first_line] + lines[1:] + ["0"]
    new_x = '\n'.join(new_lines) + ('\n' if x.endswith('\n') else '')
    out_orig = int(run(x).strip())
    out_new = int(run(new_x).strip())
    assert out_new >= out_orig
    return True

def prop_permuting_ciel_cards_unchanged(run, x):
    """PROPERTY: Permuting Ciel's card strengths leaves max damage unchanged."""
    import random
    lines = x.strip().splitlines()
    if not lines:
        return True
    n_m = list(map(int, lines[0].split()))
    n, m = n_m[0], n_m[1]
    if m <= 1:
        return True
    idx = 1 + n  # after Jiro's cards
    # Extract Ciel strengths
    strengths = []
    for i in range(m):
        strengths.append(int(lines[idx + i]))
    # Permute
    permuted = strengths.copy()
    random.shuffle(permuted)
    # Build new input
    new_lines = lines[:idx] + [str(s) for s in permuted]
    new_x = '\n'.join(new_lines) + ('\n' if x.endswith('\n') else '')
    out_orig = int(run(x).strip())
    out_new = int(run(new_x).strip())
    assert out_orig == out_new
    return True