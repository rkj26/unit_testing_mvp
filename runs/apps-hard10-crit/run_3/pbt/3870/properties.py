def prop_output_is_integer(run, x):
    """PROPERTY: Output must be a single integer."""
    out = run(x).strip()
    int(out)
    lines = out.splitlines()
    assert len(lines) == 1
    return True

def prop_damage_nonnegative(run, x):
    """PROPERTY: Maximal damage is nonnegative."""
    out = run(x).strip()
    dmg = int(out)
    assert dmg >= 0
    return True