def prop_output_modulo(run, x):
    """PROPERTY: Output must be an integer in [0, 10^9+6] inclusive."""
    out = run(x).strip()
    assert out.isdigit() or (out.startswith('-') and out[1:].isdigit()), "Output must be an integer"
    val = int(out)
    assert 0 <= val < 10**9 + 7, "Output must be modulo 10^9+7 (0..10^9+6)"

def prop_single_computer_zero(run, x):
    """PROPERTY: For n=1, output must be 0 (only subset {x1} gives F=0)."""
    lines = x.strip().split('\n')
    if len(lines) < 2:
        return
    n = int(lines[0])
    if n == 1:
        out = run(x).strip()
        assert out == "0", "For n=1, answer must be 0"