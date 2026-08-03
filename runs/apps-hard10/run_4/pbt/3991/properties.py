def prop_output_modulo(run, x):
    """PROPERTY: Output must be an integer in [0, 10^9+6] inclusive."""
    out = run(x).strip()
    assert out.isdigit() or (out.startswith('-') and out[1:].isdigit()), "Output must be an integer"
    val = int(out)
    assert 0 <= val < 10**9 + 7, "Output must be modulo 10^9+7 (0..10^9+6)"

def prop_permutation_invariance(run, x):
    """PROPERTY: Permuting coordinates does not change the answer."""
    lines = x.strip().split('\n')
    if len(lines) < 2:
        return
    n = int(lines[0])
    coords = list(map(int, lines[1].split()))
    import random
    perm = coords[:]
    random.shuffle(perm)
    new_x = f"{n}\n" + " ".join(map(str, perm)) + "\n"
    out1 = run(x).strip()
    out2 = run(new_x).strip()
    assert out1 == out2, "Permuting coordinates must give same output"

def prop_single_computer_zero(run, x):
    """PROPERTY: For n=1, output must be 0 (only subset {x1} gives F=0)."""
    lines = x.strip().split('\n')
    if len(lines) < 2:
        return
    n = int(lines[0])
    if n == 1:
        out = run(x).strip()
        assert out == "0", "For n=1, answer must be 0"

def prop_scale_and_translate_invariance(run, x):
    """PROPERTY: Adding constant to all coordinates does not change answer."""
    lines = x.strip().split('\n')
    if len(lines) < 2:
        return
    n = int(lines[0])
    coords = list(map(int, lines[1].split()))
    if n <= 1:
        return
    shift = 1000
    shifted = [c + shift for c in coords]
    new_x = f"{n}\n" + " ".join(map(str, shifted)) + "\n"
    out1 = run(x).strip()
    out2 = run(new_x).strip()
    assert out1 == out2, "Adding constant to all coordinates must give same output"

def prop_reverse_order_invariance(run, x):
    """PROPERTY: Reversing coordinate order does not change answer."""
    lines = x.strip().split('\n')
    if len(lines) < 2:
        return
    n = int(lines[0])
    coords = list(map(int, lines[1].split()))
    rev = coords[::-1]
    new_x = f"{n}\n" + " ".join(map(str, rev)) + "\n"
    out1 = run(x).strip()
    out2 = run(new_x).strip()
    assert out1 == out2, "Reversing coordinate order must give same output"