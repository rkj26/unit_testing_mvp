def prop_output_format_and_modulo(run, x):
    """PROPERTY: Output must be a single integer within [0, 10^9+6]."""
    out = run(x).strip()
    # Must be a single integer (no extra whitespace allowed except newline)
    assert out == out.strip()
    val = int(out)
    assert 0 <= val < 10**9 + 7

def prop_permutation_invariance(run, x):
    """PROPERTY: Reordering coordinates does not change the answer."""
    lines = x.strip().split('\n')
    n = int(lines[0])
    if n == 1:
        return  # trivial case, no permutation possible
    coords = list(map(int, lines[1].split()))
    # Random but deterministic permutation
    import random
    rng = random.Random(42)
    permuted = coords[:]
    rng.shuffle(permuted)
    new_input = f"{n}\n" + " ".join(map(str, permuted)) + "\n"
    out_orig = run(x).strip()
    out_perm = run(new_input).strip()
    assert out_orig == out_perm

def prop_single_computer_case(run, x):
    """PROPERTY: For n=1, answer must be 0 (only non-empty subset {x1}, max distance = 0)."""
    # Construct a trivial input with n=1
    import random
    rng = random.Random(123)
    coord = rng.randint(1, 10**9)
    inp = f"1\n{coord}\n"
    out = run(inp).strip()
    assert out == "0"

def prop_duplicate_coordinates_forbidden_implicit(run, x):
    """PROPERTY: If we duplicate a coordinate (invalid per spec), the program may reject or compute something, but we only test that output is still an integer mod M."""
    # This is a *metamorphic* test: we modify the input to contain duplicates (which violates spec's guarantee).
    # The spec says coordinates are distinct, but a correct program might still handle duplicates (or crash).
    # We only check that if it outputs, it's a valid integer mod M.
    lines = x.strip().split('\n')
    n = int(lines[0])
    coords = list(map(int, lines[1].split()))
    if n == 1:
        return  # can't duplicate meaningfully
    # Make first two coordinates equal
    coords[1] = coords[0]
    new_input = f"{n}\n" + " ".join(map(str, coords)) + "\n"
    out = run(new_input).strip()
    # If it runs without error, output must be integer in [0, M-1]
    val = int(out)
    assert 0 <= val < 10**9 + 7

def prop_reverse_coordinates_same_answer(run, x):
    """PROPERTY: Reversing the order of coordinates (same multiset) yields same answer."""
    lines = x.strip().split('\n')
    n = int(lines[0])
    if n == 1:
        return
    coords = list(map(int, lines[1].split()))
    reversed_coords = list(reversed(coords))
    new_input = f"{n}\n" + " ".join(map(str, reversed_coords)) + "\n"
    out_orig = run(x).strip()
    out_rev = run(new_input).strip()
    assert out_orig == out_rev