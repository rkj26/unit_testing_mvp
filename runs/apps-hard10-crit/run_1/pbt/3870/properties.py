import random

def prop_output_format_and_bounds(run, x):
    """PROPERTY: Output is a single integer possibly followed by newline."""
    out = run(x).strip()
    assert out == '' or out.lstrip('-').isdigit(), f"Output must be integer, got '{out}'"
    if out:
        val = int(out)
        assert 0 <= val <= 100 * 8000, f"Output {val} out of plausible bounds"

def prop_damage_nonnegative(run, x):
    """PROPERTY: Damage is non-negative for any input."""
    out = run(x).strip()
    if out:
        val = int(out)
        assert val >= 0, f"Damage negative: {val}"

def prop_empty_ciel_cards_zero_damage(run, x):
    """PROPERTY: If Ciel has no cards (m=0), damage must be 0."""
    lines = x.strip().split('\n')
    n_m = list(map(int, lines[0].split()))
    n, m = n_m[0], n_m[1]
    if m == 0:
        out = run(x).strip()
        assert out == '0', f"With m=0, damage must be 0, got {out}"

def prop_metamorphic_permute_ciel_cards(run, x):
    """PROPERTY: Permuting Ciel's card order does not change maximal damage."""
    lines = x.strip().split('\n')
    first = lines[0]
    rest = lines[1:]
    n_m = list(map(int, first.split()))
    n, m = n_m[0], n_m[1]
    if m <= 1:
        return
    jiro_lines = rest[:n]
    ciel_lines = rest[n:]
    perm = list(range(m))
    random.shuffle(perm)
    new_ciel = [ciel_lines[i] for i in perm]
    new_input = first + '\n' + '\n'.join(jiro_lines + new_ciel) + '\n'
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    assert out1 == out2, f"Permuting Ciel's cards changed output: {out1} vs {out2}"