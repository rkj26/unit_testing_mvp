import sys

def parse_input(x):
    """Parse input string into (n, m, jiro_cards, ciel_cards)."""
    lines = x.strip().splitlines()
    if not lines:
        return None
    first = lines[0].strip()
    n_m = list(map(int, first.split()))
    if len(n_m) != 2:
        return None
    n, m = n_m[0], n_m[1]
    jiro_cards = []
    idx = 1
    for _ in range(n):
        if idx >= len(lines):
            break
        parts = lines[idx].strip().split()
        # parts: [position, strength]
        if len(parts) >= 2:
            pos = parts[0]
            strength = int(parts[1])
            jiro_cards.append((pos, strength))
        idx += 1
    ciel_cards = []
    for _ in range(m):
        if idx >= len(lines):
            break
        strength = int(lines[idx].strip())
        ciel_cards.append(strength)
        idx += 1
    return n, m, jiro_cards, ciel_cards

def build_input(n, m, jiro_cards, ciel_cards):
    """Rebuild input string from components."""
    lines = [f"{n} {m}"]
    for pos, s in jiro_cards:
        lines.append(f"{pos} {s}")
    for s in ciel_cards:
        lines.append(str(s))
    return "\n".join(lines)

def greedy_atk_damage(jiro_cards, ciel_cards):
    """Compute damage from greedily matching ATK cards with smallest sufficient Ciel cards."""
    atk_strengths = [s for pos, s in jiro_cards if pos == "ATK"]
    c_sorted = sorted(ciel_cards)
    a_sorted = sorted(atk_strengths)
    i = j = damage = 0
    while i < len(c_sorted) and j < len(a_sorted):
        if c_sorted[i] >= a_sorted[j]:
            damage += c_sorted[i] - a_sorted[j]
            i += 1
            j += 1
        else:
            i += 1
    return damage

def prop_bounds(run, x):
    """PROPERTY: Output is integer between 0 and sum of Ciel's card strengths."""
    data = parse_input(x)
    if data is None:
        return True
    n, m, jiro_cards, ciel_cards = data
    sum_ciel = sum(ciel_cards)
    out = run(x)
    out_val = int(out.strip())
    assert 0 <= out_val <= sum_ciel, f"Output {out_val} not in [0, {sum_ciel}]"
    return True

def prop_symmetry(run, x):
    """PROPERTY: Output invariant under reordering of Jiro's and Ciel's cards."""
    data = parse_input(x)
    if data is None:
        return True
    n, m, jiro_cards, ciel_cards = data
    jiro_sorted = sorted(jiro_cards, key=lambda c: (c[0], c[1]))
    ciel_sorted = sorted(ciel_cards)
    x_sorted = build_input(n, m, jiro_sorted, ciel_sorted)
    out_orig = int(run(x).strip())
    out_sorted = int(run(x_sorted).strip())
    assert out_orig == out_sorted, "Output differs after sorting cards"
    return True

def prop_monotone_ciel(run, x):
    """PROPERTY: Increasing a Ciel card strength does not decrease damage; decreasing does not increase damage."""
    data = parse_input(x)
    if data is None:
        return True
    n, m, jiro_cards, ciel_cards = data
    if m == 0:
        return True
    first_strength = ciel_cards[0]
    if first_strength < 8000:
        ciel_mod = ciel_cards.copy()
        ciel_mod[0] = first_strength + 1
        x_mod = build_input(n, m, jiro_cards, ciel_mod)
        out_orig = int(run(x).strip())
        out_mod = int(run(x_mod).strip())
        assert out_mod >= out_orig, f"Increasing Ciel strength decreased output"
    else:
        # first_strength == 8000, decrease by 1 (must be >0)
        ciel_mod = ciel_cards.copy()
        ciel_mod[0] = first_strength - 1
        x_mod = build_input(n, m, jiro_cards, ciel_mod)
        out_orig = int(run(x).strip())
        out_mod = int(run(x_mod).strip())
        assert out_mod <= out_orig, f"Decreasing Ciel strength increased output"
    return True

def prop_monotone_jiro_atk(run, x):
    """PROPERTY: Decreasing a Jiro ATK card strength does not decrease damage; increasing does not increase damage."""
    data = parse_input(x)
    if data is None:
        return True
    n, m, jiro_cards, ciel_cards = data
    atk_idx = next((i for i, (pos, _) in enumerate(jiro_cards) if pos == "ATK"), -1)
    if atk_idx == -1:
        return True
    pos, strength = jiro_cards[atk_idx]
    if strength > 0:
        jiro_mod = jiro_cards.copy()
        jiro_mod[atk_idx] = (pos, strength - 1)
        x_mod = build_input(n, m, jiro_mod, ciel_cards)
        out_orig = int(run(x).strip())
        out_mod = int(run(x_mod).strip())
        assert out_mod >= out_orig, f"Decreasing Jiro ATK strength decreased output"
    else:
        jiro_mod = jiro_cards.copy()
        jiro_mod[atk_idx] = (pos, strength + 1)
        x_mod = build_input(n, m, jiro_mod, ciel_cards)
        out_orig = int(run(x).strip())
        out_mod = int(run(x_mod).strip())
        assert out_mod <= out_orig, f"Increasing Jiro ATK strength increased output"
    return True

def prop_lower_bound_greedy_atk(run, x):
    """PROPERTY: Output is at least the damage from greedily matching ATK cards with smallest sufficient Ciel cards."""
    data = parse_input(x)
    if data is None:
        return True
    n, m, jiro_cards, ciel_cards = data
    lower = greedy_atk_damage(jiro_cards, ciel_cards)
    out_val = int(run(x).strip())
    assert out_val >= lower, f"Output {out_val} < greedy lower bound {lower}"
    return True