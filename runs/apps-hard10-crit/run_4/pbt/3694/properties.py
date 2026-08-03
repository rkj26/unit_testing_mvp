def prop_output_format(run, x):
    """PROPERTY: Output must be exactly 'sjfnb' or 'cslnb' followed by a newline."""
    out = run(x)
    assert out in {"sjfnb\n", "cslnb\n"}, f"Invalid output: {repr(out)}"

def prop_swap_piles_symmetry(run, x):
    """PROPERTY: Swapping any two piles in input does not change the winner."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n = int(lines[0].strip())
    if n <= 1:
        return
    a = list(map(int, lines[1].split()))
    a[0], a[1] = a[1], a[0]
    swapped_input = f"{n}\n{' '.join(map(str, a))}\n"
    out_orig = run(x).strip()
    out_swapped = run(swapped_input).strip()
    assert out_orig == out_swapped, f"Winner changed after swapping piles: {out_orig} vs {out_swapped}"

def prop_sort_invariance(run, x):
    """PROPERTY: Sorting the pile sizes does not change the winner."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n = int(lines[0].strip())
    a = list(map(int, lines[1].split()))
    a_sorted = sorted(a)
    if a == a_sorted:
        return
    sorted_input = f"{n}\n{' '.join(map(str, a_sorted))}\n"
    out_orig = run(x).strip()
    out_sorted = run(sorted_input).strip()
    assert out_orig == out_sorted, f"Winner changed after sorting piles: {out_orig} vs {out_sorted}"