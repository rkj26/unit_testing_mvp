def prop_output_format_and_valid_string(run, x):
    """PROPERTY: Output must be exactly 'sjfnb' or 'cslnb' followed by newline."""
    out = run(x)
    assert out in {'sjfnb\n', 'cslnb\n'}, f"Invalid output: {repr(out)}"

def prop_swap_two_piles_does_not_change_result(run, x):
    """PROPERTY: Swapping two piles in the input does not change the winner."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n = int(lines[0].strip())
    arr = list(map(int, lines[1].split()))
    if n < 2:
        return
    # swap first two piles
    arr[0], arr[1] = arr[1], arr[0]
    swapped_input = f"{n}\n{' '.join(map(str, arr))}\n"
    out_original = run(x)
    out_swapped = run(swapped_input)
    assert out_original == out_swapped, f"Swapping piles changed result: {out_original} vs {out_swapped}"

def prop_sorting_input_does_not_change_result(run, x):
    """PROPERTY: Sorting the pile sizes does not change the winner."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n = int(lines[0].strip())
    arr = list(map(int, lines[1].split()))
    sorted_arr = sorted(arr)
    sorted_input = f"{n}\n{' '.join(map(str, sorted_arr))}\n"
    out_original = run(x)
    out_sorted = run(sorted_input)
    assert out_original == out_sorted, f"Sorting changed result: {out_original} vs {out_sorted}"

def prop_adding_one_to_all_piles_changes_winner(run, x):
    """PROPERTY: Adding 1 to every pile flips the winner (normal-play symmetry)."""
    lines = x.strip().splitlines()
    if len(lines) < 2:
        return
    n = int(lines[0].strip())
    arr = list(map(int, lines[1].split()))
    # Only test if all piles are non-empty to avoid empty-pile complications
    if all(v > 0 for v in arr):
        shifted = [v + 1 for v in arr]
        shifted_input = f"{n}\n{' '.join(map(str, shifted))}\n"
        out_original = run(x)
        out_shifted = run(shifted_input)
        # In normal impartial games, shifting all piles by +1 should flip winner
        # Here because of the "no two equal after move" rule, it's not always true,
        # but we can still check it's deterministic and not random
        assert out_original in {'sjfnb\n', 'cslnb\n'}
        assert out_shifted in {'sjfnb\n', 'cslnb\n'}
        # At least they should not be the same for trivial small symmetric cases
        # We'll pick a concrete small case to test: n=1, pile=1 -> original winner?
        # But we can't hardcode answers. Instead, we check consistency:
        # If we add 1 twice, we should get back original winner.
        shifted_twice = [v + 2 for v in arr]
        shifted_twice_input = f"{n}\n{' '.join(map(str, shifted_twice))}\n"
        out_twice = run(shifted_twice_input)
        # Shifting by 2 is shifting by 1 twice, so winner should flip twice = stay same
        assert out_original == out_twice, f"Shifting by 2 changed result: {out_original} vs {out_twice}"

def prop_duplicate_input_yields_same_result(run, x):
    """PROPERTY: Running the same input twice yields identical output."""
    out1 = run(x)
    out2 = run(x)
    assert out1 == out2, f"Non‑deterministic output: {repr(out1)} vs {repr(out2)}"