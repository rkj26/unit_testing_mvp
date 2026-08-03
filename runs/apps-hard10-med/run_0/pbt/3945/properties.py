def prop_bounds_format(run, x):
    """PROPERTY: Output has correct shape and each value is between 1 and n+m-1."""
    lines = x.strip().splitlines()
    if not lines:
        return
    first = lines[0].split()
    n, m = map(int, first[:2])
    out = run(x)
    # Parse output lines, ignoring empty lines
    out_lines = [line.strip() for line in out.strip().splitlines() if line.strip() != '']
    # Flatten all integers
    nums = []
    for line in out_lines:
        parts = line.split()
        nums.extend(map(int, parts))
    assert len(nums) == n * m, f"Expected {n*m} numbers, got {len(nums)}"
    max_allowed = n + m - 1
    for val in nums:
        assert 1 <= val <= max_allowed, f"Value {val} out of bounds [1, {max_allowed}]"

def prop_transpose_invariance(run, x):
    """PROPERTY: Transposing input transposes output."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m = map(int, first[:2])
    # Parse matrix A
    A = []
    for i in range(n):
        row = list(map(int, lines[i+1].split()))
        assert len(row) == m
        A.append(row)
    # Run original
    out1_str = run(x)
    out1_lines = [line.strip() for line in out1_str.strip().splitlines() if line.strip() != '']
    out1 = []
    for line in out1_lines:
        out1.append(list(map(int, line.split())))
    assert len(out1) == n and all(len(row) == m for row in out1)
    # Build transposed input
    trans_lines = [f"{m} {n}"]
    for j in range(m):
        col = [A[i][j] for i in range(n)]
        trans_lines.append(" ".join(map(str, col)))
    trans_input = "\n".join(trans_lines)
    # Run transposed
    out2_str = run(trans_input)
    out2_lines = [line.strip() for line in out2_str.strip().splitlines() if line.strip() != '']
    out2 = []
    for line in out2_lines:
        out2.append(list(map(int, line.split())))
    assert len(out2) == m and all(len(row) == n for row in out2)
    # Check that out1[i][j] == out2[j][i]
    for i in range(n):
        for j in range(m):
            assert out1[i][j] == out2[j][i], f"Mismatch at ({i},{j}): {out1[i][j]} vs {out2[j][i]}"

def prop_rank_invariance(run, x):
    """PROPERTY: Replacing heights by their order rank does not change output."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m = map(int, first[:2])
    A = []
    all_vals = []
    for i in range(n):
        row = list(map(int, lines[i+1].split()))
        A.append(row)
        all_vals.extend(row)
    # Compute rank mapping
    unique = sorted(set(all_vals))
    rank = {v: i+1 for i, v in enumerate(unique)}  # ranks start at 1
    # Build transformed input
    trans_lines = [f"{n} {m}"]
    for i in range(n):
        trans_row = [str(rank[A[i][j]]) for j in range(m)]
        trans_lines.append(" ".join(trans_row))
    trans_input = "\n".join(trans_lines)
    # Run original
    out1_str = run(x)
    out1_lines = [line.strip() for line in out1_str.strip().splitlines() if line.strip() != '']
    out1 = []
    for line in out1_lines:
        out1.append(list(map(int, line.split())))
    # Run transformed
    out2_str = run(trans_input)
    out2_lines = [line.strip() for line in out2_str.strip().splitlines() if line.strip() != '']
    out2 = []
    for line in out2_lines:
        out2.append(list(map(int, line.split())))
    # Compare elementwise
    for i in range(n):
        for j in range(m):
            assert out1[i][j] == out2[i][j], f"Difference at ({i},{j}): {out1[i][j]} vs {out2[i][j]}"

def prop_single_row_or_column(run, x):
    """PROPERTY: For n=1 all answers equal #distinct in row; for m=1 equal #distinct in column."""
    lines = x.strip().splitlines()
    first = lines[0].split()
    n, m = map(int, first[:2])
    if n == 1 and m >= 1:
        row = list(map(int, lines[1].split()))
        distinct = len(set(row))
        out = run(x)
        nums = list(map(int, out.split()))
        assert all(v == distinct for v in nums), f"All outputs should be {distinct}, got {nums}"
    if m == 1 and n >= 1:
        col = [int(lines[i+1].split()[0]) for i in range(n)]
        distinct = len(set(col))
        out = run(x)
        # parse n lines, each with one number
        out_lines = [line.strip() for line in out.strip().splitlines() if line.strip() != '']
        nums = []
        for line in out_lines:
            nums.append(int(line.split()[0]))
        assert all(v == distinct for v in nums), f"All outputs should be {distinct}, got {nums}"

def prop_symmetric_output_for_symmetric_input(run, _):
    """PROPERTY: For a fixed symmetric input, the output matrix is symmetric."""
    # Use a fixed symmetric 3x3 input
    sym_input = """3 3
1 2 3
2 4 5
3 5 6
"""
    out_str = run(sym_input)
    lines = [line.strip() for line in out_str.strip().splitlines() if line.strip() != '']
    out = []
    for line in lines:
        out.append(list(map(int, line.split())))
    assert len(out) == 3 and all(len(row) == 3 for row in out)
    for i in range(3):
        for j in range(3):
            assert out[i][j] == out[j][i], f"Output not symmetric at ({i},{j}): {out[i][j]} != {out[j][i]}"