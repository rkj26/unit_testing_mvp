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