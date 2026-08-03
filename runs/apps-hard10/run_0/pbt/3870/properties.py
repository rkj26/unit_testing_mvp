def prop_output_is_integer(run, x):
    """PROPERTY: Output is a single integer line."""
    out = run(x)
    lines = out.strip().split('\n')
    assert len(lines) == 1, "Output must be exactly one line"
    val = lines[0]
    assert val.strip() != '', "Output line must not be empty"
    # Must be integer (possibly negative)
    try:
        int(val)
    except ValueError:
        assert False, "Output must be an integer"

def prop_damage_nonnegative(run, x):
    """PROPERTY: Damage is nonnegative (can be zero)."""
    out = run(x)
    val = int(out.strip())
    assert val >= 0, "Damage must be nonnegative"

def prop_no_cards_no_damage(run, x):
    """PROPERTY: If Ciel has no cards, damage is zero."""
    # Parse input to see if m == 0
    lines = x.strip().split('\n')
    n, m = map(int, lines[0].split())
    if m == 0:
        out = run(x)
        val = int(out.strip())
        assert val == 0, "With no Ciel cards, damage must be 0"

def prop_permute_ciel_cards(run, x):
    """PROPERTY: Permuting Ciel's card list does not change optimal damage."""
    lines = x.strip().split('\n')
    first = lines[0]
    rest = lines[1:]
    n, m = map(int, first.split())
    if m <= 1:
        return  # No permutation possible
    jiro_part = rest[:n]
    ciel_part = rest[n:]
    import random
    perm = random.Random(42).sample(ciel_part, len(ciel_part))
    new_input = first + '\n' + '\n'.join(jiro_part + perm) + '\n'
    out1 = int(run(x).strip())
    out2 = int(run(new_input).strip())
    assert out1 == out2, "Permuting Ciel's cards should not change damage"

def prop_duplicate_all_strengths(run, x):
    """PROPERTY: Doubling all strengths doubles the damage (when feasible)."""
    lines = x.strip().split('\n')
    first = lines[0]
    rest = lines[1:]
    n, m = map(int, first.split())
    # Build doubled input
    new_lines = [first]
    for line in rest:
        if line.startswith('ATK ') or line.startswith('DEF '):
            pos, val = line.split()
            new_lines.append(f"{pos} {2*int(val)}")
        else:
            new_lines.append(str(2*int(line)))
    new_input = '\n'.join(new_lines) + '\n'
    out1 = int(run(x).strip())
    out2 = int(run(new_input).strip())
    # If original answer is zero, doubled is also zero
    if out1 == 0:
        assert out2 == 0, "Zero damage should stay zero after doubling strengths"
    else:
        # In correct strategy, scaling all strengths by 2 scales damage by 2
        # because constraints (≥, >) are preserved and damage differences double.
        assert out2 == 2 * out1, "Doubling all strengths should double damage"