import random
import re

def prop_output_format_and_bounds(run, x):
    """PROPERTY: Output is a single integer possibly followed by newline."""
    out = run(x).strip()
    # Must be a valid integer
    assert out == '' or out.lstrip('-').isdigit(), f"Output must be integer, got '{out}'"
    if out:
        val = int(out)
        # Upper bound: worst case all Ciel cards used directly (no Jiro cards), sum strengths <= 100*8000 = 800000
        # Also could be negative? No, damage is non-negative because (X strength - Y strength) >=0 when attacking ATK,
        # and direct attacks give non-negative damage. Minimum is 0.
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
        return  # No permutation possible
    jiro_lines = rest[:n]
    ciel_lines = rest[n:]
    # Permute Ciel's cards
    import random
    perm = list(range(m))
    random.shuffle(perm)
    new_ciel = [ciel_lines[i] for i in perm]
    new_input = first + '\n' + '\n'.join(jiro_lines + new_ciel) + '\n'
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    assert out1 == out2, f"Permuting Ciel's cards changed output: {out1} vs {out2}"

def prop_monotonic_add_ciel_card(run, x):
    """PROPERTY: Adding a Ciel card (strength >=0) cannot decrease maximal damage."""
    lines = x.strip().split('\n')
    first = lines[0]
    rest = lines[1:]
    n_m = list(map(int, first.split()))
    n, m = n_m[0], n_m[1]
    if m >= 100:
        return  # Cannot add because m ≤ 100 constraint
    jiro_lines = rest[:n]
    ciel_lines = rest[n:]
    # Add a new Ciel card with strength 0 (weakest possible)
    new_strength = 0
    new_first = f"{n} {m+1}"
    new_input = new_first + '\n' + '\n'.join(jiro_lines + ciel_lines + [str(new_strength)]) + '\n'
    out_orig = run(x).strip()
    out_new = run(new_input).strip()
    if out_orig and out_new:
        assert int(out_new) >= int(out_orig), f"Adding a Ciel card decreased damage: {out_orig} -> {out_new}"