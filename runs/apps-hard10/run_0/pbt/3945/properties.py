def prop_output_format_and_bounds(run, x):
    """PROPERTY: Output has n lines with m integers each, each integer between 1 and n+m-1 inclusive."""
    out = run(x)
    lines = out.strip().splitlines()
    # If output ends with newline, last line may be empty; filter.
    lines = [line.strip() for line in lines if line.strip() != ""]
    # First line of input gives n, m.
    first_line = x.strip().splitlines()[0]
    n, m = map(int, first_line.split())
    assert len(lines) == n, f"Expected {n} output lines, got {len(lines)}"
    for i, line in enumerate(lines):
        parts = line.split()
        assert len(parts) == m, f"Line {i}: expected {m} numbers, got {len(parts)}"
        for num_str in parts:
            val = int(num_str)
            # Upper bound: in worst case, all heights in row+col are distinct -> need at most n+m-1 labels.
            # Lower bound: at least 1.
            assert 1 <= val <= n + m - 1, f"Value {val} out of [1, {n+m-1}]"

def prop_transpose_invariance(run, x):
    """PROPERTY: Swapping n↔m and transposing matrix yields transposed output."""
    lines_in = x.strip().splitlines()
    first = lines_in[0].split()
    n_orig, m_orig = map(int, first)
    if n_orig == m_orig:
        # If square, transposition should swap indices accordingly.
        # Build transposed input.
        data_lines = lines_in[1:]
        matrix = [list(map(int, line.split())) for line in data_lines]
        # Transpose matrix
        transposed = [[matrix[i][j] for i in range(n_orig)] for j in range(m_orig)]
        new_input = f"{m_orig} {n_orig}\n" + "\n".join(
            " ".join(map(str, row)) for row in transposed
        )
        out_orig = run(x)
        out_trans = run(new_input)
        orig_matrix = [list(map(int, line.split())) for line in out_orig.strip().splitlines()]
        trans_matrix = [list(map(int, line.split())) for line in out_trans.strip().splitlines()]
        # orig_matrix[i][j] should equal trans_matrix[j][i]
        for i in range(n_orig):
            for j in range(m_orig):
                assert orig_matrix[i][j] == trans_matrix[j][i], f"Mismatch at ({i},{j}) after transpose"

def prop_permute_rows_and_columns(run, x):
    """PROPERTY: Permuting rows and columns permutes output accordingly."""
    import random
    random.seed(12345)  # deterministic
    lines_in = x.strip().splitlines()
    first = lines_in[0].split()
    n, m = map(int, first)
    if n < 2 and m < 2:
        return  # No permutation possible
    data = [list(map(int, line.split())) for line in lines_in[1:]]
    # Choose random permutations
    perm_rows = list(range(n))
    perm_cols = list(range(m))
    random.shuffle(perm_rows)
    random.shuffle(perm_cols)
    # Build permuted input
    perm_data = [[data[perm_rows[i]][perm_cols[j]] for j in range(m)] for i in range(n)]
    new_input = f"{n} {m}\n" + "\n".join(" ".join(map(str, row)) for row in perm_data)
    out_orig = run(x)
    out_perm = run(new_input)
    orig_mat = [list(map(int, line.split())) for line in out_orig.strip().splitlines()]
    perm_mat = [list(map(int, line.split())) for line in out_perm.strip().splitlines()]
    # orig_mat[i][j] should equal perm_mat[inv_perm_rows(i)][inv_perm_cols(j)]? Wait carefully.
    # Actually: orig_mat[perm_rows[i]][perm_cols[j]] corresponds to perm_mat[i][j]
    inv_rows = [0] * n
    inv_cols = [0] * m
    for i in range(n):
        inv_rows[perm_rows[i]] = i
    for j in range(m):
        inv_cols[perm_cols[j]] = j
    for i in range(n):
        for j in range(m):
            expected = orig_mat[perm_rows[i]][perm_cols[j]]
            got = perm_mat[i][j]
            assert expected == got, f"Permutation mismatch at ({i},{j})"

def prop_monotonicity_with_duplicate_heights(run, x):
    """PROPERTY: If we replace a height with a duplicate of another existing height in its row/col, answer doesn't increase."""
    lines_in = x.strip().splitlines()
    first = lines_in[0].split()
    n, m = map(int, first)
    if n * m == 0:
        return
    data = [list(map(int, line.split())) for line in lines_in[1:]]
    # Pick a random cell (i0,j0)
    import random
    random.seed(67890)
    i0, j0 = random.randrange(n), random.randrange(m)
    # Find a height in the same row that equals some height in the same column (or just pick any duplicate scenario)
    # Simpler: make a copy of data, change (i0,j0) to equal some other cell in same row.
    # Choose another column j1 in same row.
    j1 = random.randrange(m)
    while j1 == j0 and m > 1:
        j1 = random.randrange(m)
    new_val = data[i0][j1]
    modified = [row[:] for row in data]
    modified[i0][j0] = new_val
    new_input = f"{n} {m}\n" + "\n".join(" ".join(map(str, row)) for row in modified)
    out_orig = run(x)
    out_mod = run(new_input)
    orig_mat = [list(map(int, line.split())) for line in out_orig.strip().splitlines()]
    mod_mat = [list(map(int, line.split())) for line in out_mod.strip().splitlines()]
    # The answer for (i0,j0) should not increase (could stay same or decrease).
    assert mod_mat[i0][j0] <= orig_mat[i0][j0], f"Answer increased after making height equal to another in same row"

def prop_identical_rows_produce_identical_output_rows(run, x):
    """PROPERTY: If two rows have identical height sequences, their output rows are identical."""
    lines_in = x.strip().splitlines()
    first = lines_in[0].split()
    n, m = map(int, first)
    if n < 2:
        return
    data = [list(map(int, line.split())) for line in lines_in[1:]]
    # Find pair of identical rows
    identical_pair = None
    for i1 in range(n):
        for i2 in range(i1 + 1, n):
            if data[i1] == data[i2]:
                identical_pair = (i1, i2)
                break
        if identical_pair:
            break
    if not identical_pair:
        return  # No identical rows, skip
    i1, i2 = identical_pair
    out = run(x)
    out_mat = [list(map(int, line.split())) for line in out.strip().splitlines()]
    # The output rows i1 and i2 must be identical
    assert out_mat[i1] == out_mat[i2], f"Identical input rows {i1},{i2} produced different output rows"