def prop_output_shape_matches_input(run, x):
    """PROPERTY: Output must have n lines, each with m integers, ending with newline."""
    lines = x.strip().split('\n')
    n, m = map(int, lines[0].split())
    out = run(x)
    out_lines = out.strip().split('\n')
    assert len(out_lines) == n, f"Expected {n} output lines, got {len(out_lines)}"
    for i, line in enumerate(out_lines):
        nums = line.strip().split()
        assert len(nums) == m, f"Line {i}: expected {m} numbers, got {len(nums)}"
        for token in nums:
            assert token.isdigit() or (token[0] == '-' and token[1:].isdigit()), f"Non-integer output: {token}"
    return True

def prop_permutation_invariance(run, x):
    """PROPERTY: Permuting row values (preserving order) yields same outputs."""
    import random
    lines = x.strip().split('\n')
    n, m = map(int, lines[0].split())
    grid = [list(map(int, lines[i+1].split())) for i in range(n)]
    all_vals = sorted(set(val for row in grid for val in row))
    perm = list(range(len(all_vals)))
    random.shuffle(perm)
    val_map = {all_vals[i]: perm[i]+1 for i in range(len(all_vals))}
    new_grid = [[val_map[val] for val in row] for row in grid]
    new_input = f"{n} {m}\n" + "\n".join(" ".join(map(str, row)) for row in new_grid) + "\n"
    out1 = run(x)
    out2 = run(new_input)
    assert out1 == out2, "Permuting values changed output"
    return True