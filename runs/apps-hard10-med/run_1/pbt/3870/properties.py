def prop_bounds(run, x):
    """PROPERTY: output is integer between 0 and sum of Ciel's strengths."""
    out = run(x)
    damage = int(out.strip())
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m = map(int, first[:2])
    # skip Jiro's cards (n lines)
    idx = 1 + n
    total_ciel = 0
    for i in range(m):
        if idx < len(lines):
            s = lines[idx].strip()
            if s:
                total_ciel += int(s)
        idx += 1
    assert 0 <= damage <= total_ciel, f"Damage {damage} not in [0, {total_ciel}]"

def prop_symmetry_ciel(run, x):
    """PROPERTY: permuting Ciel's cards does not change maximal damage."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m = map(int, first[:2])
    # Build input with reversed Ciel strengths
    new_lines = [f"{n} {m}"]
    new_lines.extend(lines[1:1+n])  # Jiro's cards unchanged
    ciel_lines = lines[1+n:1+n+m]
    new_lines.extend(reversed(ciel_lines))  # reverse order
    new_x = "\n".join(new_lines)
    out1 = run(x).strip()
    out2 = run(new_x).strip()
    assert out1 == out2, f"Outputs differ: {out1} vs {out2}"

def prop_monotonic_ciel_strength(run, x):
    """PROPERTY: increasing a Ciel card's strength does not decrease maximal damage."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m = map(int, first[:2])
    ciel_start = 1 + n
    new_lines = lines[:]  # mutable copy
    modified = False
    for i in range(m):
        idx = ciel_start + i
        s = int(lines[idx].strip())
        if s < 8000:
            new_lines[idx] = str(s + 1)
            modified = True
            break
    if not modified:
        return True  # no card could be increased, skip test
    new_x = "\n".join(new_lines)
    out1 = int(run(x).strip())
    out2 = int(run(new_x).strip())
    assert out2 >= out1, f"Damage decreased from {out1} to {out2} after increasing Ciel strength"

def prop_monotonic_jiro_atk_strength(run, x):
    """PROPERTY: increasing a Jiro ATK card's strength does not increase maximal damage."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m = map(int, first[:2])
    new_lines = lines[:]
    modified = False
    for i in range(n):
        idx = 1 + i
        parts = lines[idx].split()
        pos = parts[0]
        if pos == "ATK":
            s = int(parts[1])
            if s < 8000:
                new_lines[idx] = f"ATK {s + 1}"
                modified = True
                break
    if not modified:
        return True  # no ATK card could be increased, skip test
    new_x = "\n".join(new_lines)
    out1 = int(run(x).strip())
    out2 = int(run(new_x).strip())
    assert out2 <= out1, f"Damage increased from {out1} to {out2} after increasing Jiro ATK strength"

def prop_add_zero_card(run, x):
    """PROPERTY: adding an extra Ciel card with strength 0 does not decrease maximal damage."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m = map(int, first[:2])
    if m >= 100:
        return True  # cannot add another card without violating constraints
    new_first = f"{n} {m+1}"
    new_lines = [new_first] + lines[1:] + ["0"]
    new_x = "\n".join(new_lines)
    out1 = int(run(x).strip())
    out2 = int(run(new_x).strip())
    assert out2 >= out1, f"Damage decreased from {out1} to {out2} after adding a zero card"