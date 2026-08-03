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
    # swap first two piles
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

def prop_adding_zero_pile(run, x):
    """PROPERTY: Adding one extra pile with 0 stones when n=1 flips the winner (since starting condition changes)."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n = int(lines[0].strip())
    if n != 1:
        return
    a0 = int(lines[1].strip())
    # new input with two piles: a0 and 0
    new_input = f"2\n{a0} 0\n"
    out_orig = run(x).strip()
    out_new = run(new_input).strip()
    # In the known examples, for n=1, a=[0] -> cslnb; adding a 0 pile makes n=2, [0,0] -> cslnb still (both lose immediately).
    # But for a0>0, e.g., n=1, a=[1] -> sjfnb (since Toki can take stone and win), but n=2, [1,0] -> cslnb (example 2).
    # So the winner should flip unless a0=0.
    if a0 == 0:
        assert out_orig == out_new == "cslnb", f"Both should be cslnb for zero pile, got {out_orig} and {out_new}"
    else:
        assert out_orig != out_new, f"Winner should flip when adding a zero pile to single non-zero pile, but got {out_orig} both times"

def prop_shift_all_up_by_one(run, x):
    """PROPERTY: Increasing every pile by 1 does not change the winner (game is invariant under adding a constant to all piles)."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n = int(lines[0].strip())
    a = list(map(int, lines[1].split()))
    # Shift all up by 1
    a_shifted = [ai + 1 for ai in a]
    shifted_input = f"{n}\n{' '.join(map(str, a_shifted))}\n"
    out_orig = run(x).strip()
    out_shifted = run(shifted_input).strip()
    assert out_orig == out_shifted, f"Winner changed after shifting all piles up by 1: {out_orig} vs {out_shifted}"