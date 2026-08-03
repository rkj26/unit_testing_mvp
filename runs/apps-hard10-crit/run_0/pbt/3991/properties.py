def prop_output_format_and_modulo(run, x):
    """PROPERTY: Output must be a single integer within [0, 10^9+6]."""
    out = run(x).strip()
    # Must be a single integer (no extra whitespace allowed except newline)
    assert out == out.strip()
    val = int(out)
    assert 0 <= val < 10**9 + 7

def prop_single_computer_case(run, x):
    """PROPERTY: For n=1, answer must be 0 (only non-empty subset {x1}, max distance = 0)."""
    import random
    rng = random.Random(123)
    coord = rng.randint(1, 10**9)
    inp = f"1\n{coord}\n"
    out = run(inp).strip()
    assert out == "0"