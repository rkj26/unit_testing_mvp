def prop_output_format_and_winning_names(run, x):
    """PROPERTY: The output must be exactly 'sjfnb' or 'cslnb' followed by a newline."""
    out = run(x)
    assert out in {"sjfnb\n", "cslnb\n"}, f"Invalid output: {repr(out)}"

def prop_single_pile_zero(run, x):
    """PROPERTY: For n=1, a1=0, CSL wins (cslnb)."""
    out = run("1\n0\n")
    assert out == "cslnb\n", f"Expected 'cslnb\\n' for input '1\\n0\\n', got {repr(out)}"