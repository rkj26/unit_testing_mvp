def prop_output_format_and_bounds(run, x):
    """PROPERTY: Output has n lines with m integers each, each integer between 1 and n+m-1 inclusive."""
    out = run(x)
    lines = out.strip().splitlines()
    lines = [line.strip() for line in lines if line.strip() != ""]
    first_line = x.strip().splitlines()[0]
    n, m = map(int, first_line.split())
    assert len(lines) == n, f"Expected {n} output lines, got {len(lines)}"
    for i, line in enumerate(lines):
        parts = line.split()
        assert len(parts) == m, f"Line {i}: expected {m} numbers, got {len(parts)}"
        for num_str in parts:
            val = int(num_str)
            assert 1 <= val <= n + m - 1, f"Value {val} out of [1, {n+m-1}]"

def prop_transpose_invariance(run, x):
    """PROPERTY: Swapping n↔m and transposing matrix yields transposed output."""
    lines_in = x.strip().splitlines()
    first = lines_in[0].split()
    n_orig, m_orig = map(int, first)
    if n_orig == m_orig:
        data_lines = lines_in[1:]
        matrix = [list(map(int, line.split())) for line in data_lines]
        transposed = [[matrix[i][j] for i in range(n_orig)] for j in range(m_orig)]
        new_input = f"{m_orig} {n_orig}\n" + "\n".join(
            " ".join(map(str, row)) for row in transposed
        )
        out_orig = run(x)
        out_trans = run(new_input)
        orig_matrix = [list(map(int, line.split())) for line in out_orig.strip().splitlines()]
        trans_matrix = [list(map(int, line.split())) for line in out_trans.strip().splitlines()]
        for i in range(n_orig):
            for j in range(m_orig):
                assert orig_matrix[i][j] == trans_matrix[j][i], f"Mismatch at ({i},{j}) after transpose"

def prop_permute_rows_and_columns(run, x):
    """PROPERTY: Permuting rows and columns permutes output accordingly."""
    import random
    random.seed(12345)
    lines_in = x.strip().splitlines()
    first = lines_in[0].split()
    n, m = map(int, first)
    if n < 2 and m < 2:
        return
    data = [list(map(int, line.split())) for line in lines_in[1:]]
    perm_rows = list(range(n))
    perm_cols = list(range(m))
    random.shuffle(perm_rows)
    random.shuffle(perm_cols)
    perm_data = [[data[perm_rows[i]][perm_cols[j]] for j in range(m)] for i in range(n)]
    new_input = f"{n} {m}\n" + "\n".join(" ".join(map(str, row)) for row in perm_data)
    out_orig = run(x)
    out_perm = run(new_input)
    orig_mat = [list(map(int, line.split())) for line in out_orig.strip().splitlines()]
    perm_mat = [list(map(int, line.split())) for line in out_perm.strip().splitlines()]
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