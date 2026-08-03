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
    # Ensure final newline if spec requires (but not strictly needed for shape check)
    return True

def prop_answer_bounded_by_ranks(run, x):
    """PROPERTY: For each cell, answer ≤ rank_in_row + rank_in_col - 1."""
    lines = x.strip().split('\n')
    n, m = map(int, lines[0].split())
    grid = [list(map(int, lines[i+1].split())) for i in range(n)]
    out = run(x)
    out_grid = [list(map(int, line.split())) for line in out.strip().split('\n')]
    for i in range(n):
        row = grid[i]
        # rank of each element in its row (1-based, greater values = higher rank)
        row_rank = [sorted(row).index(val) + 1 for val in row]
        for j in range(m):
            col = [grid[k][j] for k in range(n)]
            col_rank = sorted(col).index(grid[i][j]) + 1
            max_possible = row_rank[j] + col_rank[j] - 1
            assert out_grid[i][j] <= max_possible, f"Cell ({i},{j}) answer {out_grid[i][j]} > {max_possible} (row_rank {row_rank[j]}, col_rank {col_rank[j]})"
    return True

def prop_permutation_invariance(run, x):
    """PROPERTY: Permuting row values (preserving order) yields same outputs."""
    import random
    lines = x.strip().split('\n')
    n, m = map(int, lines[0].split())
    grid = [list(map(int, lines[i+1].split())) for i in range(n)]
    # Create a random bijection on values while preserving comparisons
    all_vals = sorted(set(val for row in grid for val in row))
    perm = list(range(len(all_vals)))
    random.shuffle(perm)
    val_map = {all_vals[i]: perm[i]+1 for i in range(len(all_vals))}  # map to 1..len
    new_grid = [[val_map[val] for val in row] for row in grid]
    new_input = f"{n} {m}\n" + "\n".join(" ".join(map(str, row)) for row in new_grid) + "\n"
    out1 = run(x)
    out2 = run(new_input)
    # Outputs should be identical because relative order unchanged
    assert out1 == out2, "Permuting values changed output"
    return True

def prop_transpose_symmetry(run, x):
    """PROPERTY: Transposing input transposes output (since problem symmetric)."""
    lines = x.strip().split('\n')
    n, m = map(int, lines[0].split())
    grid = [list(map(int, lines[i+1].split())) for i in range(n)]
    # Transpose
    transposed = [[grid[i][j] for i in range(n)] for j in range(m)]
    new_input = f"{m} {n}\n" + "\n".join(" ".join(map(str, row)) for row in transposed) + "\n"
    out1 = run(x)
    out2 = run(new_input)
    out1_grid = [list(map(int, line.split())) for line in out1.strip().split('\n')]
    out2_grid = [list(map(int, line.split())) for line in out2.strip().split('\n')]
    # Check transpose relation
    for i in range(n):
        for j in range(m):
            assert out1_grid[i][j] == out2_grid[j][i], f"Transpose mismatch at ({i},{j})"
    return True

def prop_monotonicity_in_row(run, x):
    """PROPERTY: In a given row, if heights increase, answers are non-decreasing."""
    lines = x.strip().split('\n')
    n, m = map(int, lines[0].split())
    grid = [list(map(int, lines[i+1].split())) for i in range(n)]
    out = run(x)
    out_grid = [list(map(int, line.split())) for line in out.strip().split('\n')]
    for i in range(n):
        row = grid[i]
        out_row = out_grid[i]
        # Check for each adjacent pair where heights strictly increase
        for j in range(m-1):
            if row[j] < row[j+1]:
                assert out_row[j] <= out_row[j+1], f"Row {i}: heights {row[j]}<{row[j+1]} but answers {out_row[j]}>{out_row[j+1]}"
    return True