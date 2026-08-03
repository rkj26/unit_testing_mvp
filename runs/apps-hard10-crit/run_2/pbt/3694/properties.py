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

def prop_duplicate_input_yields_same_result(run, x):
    """PROPERTY: Running the same input twice yields identical output."""
    out1 = run(x)
    out2 = run(x)
    assert out1 == out2, f"Non‑deterministic output: {repr(out1)} vs {repr(out2)}"