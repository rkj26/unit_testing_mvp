def prop_output_format(run, x):
    """PROPERTY: Output must be a single integer modulo 1e9+7."""
    out = run(x).strip()
    # Must be non-empty, only digits, possibly with leading/trailing whitespace
    assert out != "", "Empty output"
    # Check it's a valid integer
    val = int(out)
    # Modulo 1e9+7 is not required to be explicitly printed, but we can check it's in range 0..MOD-1
    # Actually spec says "modulo 10^9+7", so output must be in [0, MOD-1]
    MOD = 10**9 + 7
    assert 0 <= val < MOD, f"Output {val} not in range [0, {MOD-1}]"
    # Also ensure no extra characters
    lines = out.splitlines()
    assert len(lines) == 1, "More than one line in output"

def prop_permutation_invariant(run, x):
    """PROPERTY: Permuting computer indices does not change answer."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return  # too small to permute meaningfully
    n = int(lines[0])
    if n <= 1:
        return  # permutation trivial
    coords = list(map(int, lines[1].split()))
    # Permute indices by shuffling coordinates
    import random
    rng = random.Random(42)  # fixed seed for determinism
    permuted = coords.copy()
    rng.shuffle(permuted)
    new_input = f"{n}\n" + " ".join(map(str, permuted)) + "\n"
    out1 = int(run(x).strip())
    out2 = int(run(new_input).strip())
    assert out1 == out2, f"Permutation changed output: {out1} vs {out2}"

def prop_linear_translation(run, x):
    """PROPERTY: Adding constant to all coordinates does not change distances, so output unchanged."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n = int(lines[0])
    coords = list(map(int, lines[1].split()))
    # Add a fixed constant
    delta = 100
    translated = [c + delta for c in coords]
    new_input = f"{n}\n" + " ".join(map(str, translated)) + "\n"
    out1 = int(run(x).strip())
    out2 = int(run(new_input).strip())
    assert out1 == out2, f"Translation changed output: {out1} vs {out2}"

def prop_single_computer_case(run, x):
    """PROPERTY: For n=1, answer must be 0 (only non-empty subset is single computer, max distance=0)."""
    # Construct a fresh input with n=1
    import random
    coord = random.randint(1, 10**9)
    inp = f"1\n{coord}\n"
    out = run(inp).strip()
    val = int(out)
    assert val == 0, f"For n=1, expected 0, got {val}"