def prop_output_is_integer_modulo(run, x):
    """PROPERTY: Output must be a single integer modulo 10^9+7."""
    out = run(x).strip()
    # Must be a valid integer
    val = int(out)
    # Must be non-negative and less than MOD
    MOD = 10**9 + 7
    assert 0 <= val < MOD

def prop_empty_subsets_ignored(run, x):
    """PROPERTY: Adding a computer with a coordinate equal to an existing one (invalid input) is not allowed, but if we duplicate a coordinate and sort, the answer for n=1 is always 0."""
    # For n=1, any non-empty subset has only one computer, so max distance is 0.
    # We test with a single computer.
    import random
    coord = random.randint(1, 10**9)
    inp = f"1\n{coord}\n"
    out = run(inp).strip()
    assert out == "0"

def prop_permutation_invariance(run, x):
    """PROPERTY: Permuting the order of computers does not change the answer."""
    lines = x.strip().split('\n')
    n = int(lines[0])
    if n <= 1:
        return  # trivial
    coords = list(map(int, lines[1].split()))
    import random
    shuffled = coords[:]
    random.shuffle(shuffled)
    new_inp = f"{n}\n" + " ".join(map(str, shuffled)) + "\n"
    out1 = run(x).strip()
    out2 = run(new_inp).strip()
    assert out1 == out2

def prop_reverse_coordinates(run, x):
    """PROPERTY: Reversing the sorted order of coordinates does not change the answer."""
    lines = x.strip().split('\n')
    n = int(lines[0])
    if n <= 1:
        return
    coords = list(map(int, lines[1].split()))
    sorted_coords = sorted(coords)
    rev_coords = sorted_coords[::-1]
    inp1 = f"{n}\n" + " ".join(map(str, sorted_coords)) + "\n"
    inp2 = f"{n}\n" + " ".join(map(str, rev_coords)) + "\n"
    out1 = run(inp1).strip()
    out2 = run(inp2).strip()
    assert out1 == out2

def prop_linear_translation_invariance(run, x):
    """PROPERTY: Shifting all coordinates by a constant does not change the answer (distances unchanged)."""
    lines = x.strip().split('\n')
    n = int(lines[0])
    if n <= 1:
        return
    coords = list(map(int, lines[1].split()))
    shift = 1000  # arbitrary
    shifted = [c + shift for c in coords]
    inp1 = f"{n}\n" + " ".join(map(str, coords)) + "\n"
    inp2 = f"{n}\n" + " ".join(map(str, shifted)) + "\n"
    out1 = run(inp1).strip()
    out2 = run(inp2).strip()
    assert out1 == out2