def prop_output_format_and_winning_names(run, x):
    """PROPERTY: The output must be exactly 'sjfnb' or 'cslnb' followed by a newline."""
    out = run(x)
    assert out in {"sjfnb\n", "cslnb\n"}, f"Invalid output: {repr(out)}"

def prop_single_pile_zero(run, x):
    """PROPERTY: For n=1, a1=0, CSL wins (cslnb)."""
    out = run("1\n0\n")
    assert out == "cslnb\n", f"Expected 'cslnb\\n' for input '1\\n0\\n', got {repr(out)}"

def prop_permutation_invariance(run, x):
    """PROPERTY: Permuting the pile sizes does not change the winner."""
    import random
    lines = x.strip().split("\n")
    if len(lines) < 2:
        return  # Not enough lines to permute
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    if len(a) != n:
        return  # malformed input, skip
    random.shuffle(a)
    x_perm = f"{n}\n" + " ".join(map(str, a)) + "\n"
    out1 = run(x)
    out2 = run(x_perm)
    assert out1 == out2, f"Permutation changed output: {out1} vs {out2}"

def prop_adding_one_to_all_preserves_winner(run, x):
    """PROPERTY: Adding the same constant to all piles preserves the winner."""
    lines = x.strip().split("\n")
    if len(lines) < 2:
        return
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    if len(a) != n:
        return
    # Avoid overflow by not adding if any a_i > 10^9 - 1
    if any(ai > 10**9 - 1 for ai in a):
        return
    a2 = [ai + 1 for ai in a]
    x2 = f"{n}\n" + " ".join(map(str, a2)) + "\n"
    out1 = run(x)
    out2 = run(x2)
    assert out1 == out2, f"Adding 1 to all changed output: {out1} vs {out2}"

def prop_swap_two_equal_piles(run, x):
    """PROPERTY: Swapping two piles with same size does not change winner."""
    lines = x.strip().split("\n")
    if len(lines) < 2:
        return
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    if len(a) != n:
        return
    # Find two indices with same value
    from collections import defaultdict
    val_to_indices = defaultdict(list)
    for i, val in enumerate(a):
        val_to_indices[val].append(i)
    for indices in val_to_indices.values():
        if len(indices) >= 2:
            i, j = indices[0], indices[1]
            # swapping identical values leaves array unchanged, so skip
            # Actually we can still test by constructing same array
            # but the property is trivial if values equal.
            # Instead, test that identical arrays produce same output.
            x_same = f"{n}\n" + " ".join(map(str, a)) + "\n"
            out1 = run(x)
            out2 = run(x_same)
            assert out1 == out2, f"Same array gave different output"
            break  # test done
    # If no duplicates, property holds vacuously