def prop_bounds_and_format(run, x):
    """PROPERTY: Output has correct dimensions and each integer is between 1 and n+m-1."""
    import sys
    # parse input
    lines = x.strip().splitlines()
    first = lines[0].strip().split()
    n, m = map(int, first)
    # run program
    out_str = run(x)
    # parse output
    out_lines = [line.strip() for line in out_str.strip().splitlines() if line.strip() != '']
    assert len(out_lines) == n, f"Expected {n} output lines, got {len(out_lines)}"
    for i, line in enumerate(out_lines):
        parts = line.split()
        assert len(parts) == m, f"Line {i}: expected {m} numbers, got {len(parts)}"
        for j, num_str in enumerate(parts):
            try:
                val = int(num_str)
            except ValueError:
                raise AssertionError(f"Line {i}, entry {j}: not an integer")
            assert 1 <= val <= n + m - 1, f"Line {i}, entry {j}: value {val} out of bounds [1, {n+m-1}]"
    return True

def prop_transpose_invariance(run, x):
    """PROPERTY: Transposing the input transposes the output."""
    # parse original input
    lines = x.strip().splitlines()
    first = lines[0].strip().split()
    n, m = map(int, first)
    mat = [list(map(int, lines[i+1].strip().split())) for i in range(n)]
    # run original
    out_str = run(x)
    out_mat = [list(map(int, line.strip().split())) for line in out_str.strip().splitlines() if line.strip() != '']
    # build transposed input
    n_t, m_t = m, n
    mat_t = [[mat[i][j] for i in range(n)] for j in range(m)]
    inp_t = f"{n_t} {m_t}\n" + "\n".join(" ".join(str(v) for v in row) for row in mat_t) + "\n"
    # run on transposed input
    out_str_t = run(inp_t)
    out_mat_t = [list(map(int, line.strip().split())) for line in out_str_t.strip().splitlines() if line.strip() != '']
    # transpose the transposed output
    out_mat_t_transposed = [[out_mat_t[i][j] for i in range(n_t)] for j in range(m_t)]
    # compare
    assert out_mat == out_mat_t_transposed, "Output not invariant under transpose"
    return True

def prop_monotonic_invariance(run, x):
    """PROPERTY: Applying a strictly increasing linear transformation does not change output."""
    # parse original input
    lines = x.strip().splitlines()
    first = lines[0].strip().split()
    n, m = map(int, first)
    mat = [list(map(int, lines[i+1].strip().split())) for i in range(n)]
    # run original
    out_str = run(x)
    out_mat = [list(map(int, line.strip().split())) for line in out_str.strip().splitlines() if line.strip() != '']
    # apply transformation: a -> 2*a + 1 (strictly increasing)
    mat2 = [[2 * v + 1 for v in row] for row in mat]
    inp2 = f"{n} {m}\n" + "\n".join(" ".join(str(v) for v in row) for row in mat2) + "\n"
    # run on transformed input
    out_str2 = run(inp2)
    out_mat2 = [list(map(int, line.strip().split())) for line in out_str2.strip().splitlines() if line.strip() != '']
    # compare
    assert out_mat == out_mat2, "Output changed under monotonic transformation"
    return True

def prop_row_permutation_invariance(run, x):
    """PROPERTY: Permuting two rows permutes the output rows accordingly."""
    # parse original input
    lines = x.strip().splitlines()
    first = lines[0].strip().split()
    n, m = map(int, first)
    if n < 2:
        return True   # nothing to permute
    mat = [list(map(int, lines[i+1].strip().split())) for i in range(n)]
    # run original
    out_str = run(x)
    out_mat = [list(map(int, line.strip().split())) for line in out_str.strip().splitlines() if line.strip() != '']
    # permute rows 0 and 1
    perm_mat = [mat[1], mat[0]] + mat[2:]
    inp_perm = f"{n} {m}\n" + "\n".join(" ".join(str(v) for v in row) for row in perm_mat) + "\n"
    # run on permuted input
    out_str_perm = run(inp_perm)
    out_mat_perm = [list(map(int, line.strip().split())) for line in out_str_perm.strip().splitlines() if line.strip() != '']
    # permute rows of original output accordingly
    expected_perm = [out_mat[1], out_mat[0]] + out_mat[2:]
    assert out_mat_perm == expected_perm, "Row permutation not reflected in output"
    return True

def prop_column_permutation_invariance(run, x):
    """PROPERTY: Permuting two columns permutes the output columns accordingly."""
    # parse original input
    lines = x.strip().splitlines()
    first = lines[0].strip().split()
    n, m = map(int, first)
    if m < 2:
        return True   # nothing to permute
    mat = [list(map(int, lines[i+1].strip().split())) for i in range(n)]
    # run original
    out_str = run(x)
    out_mat = [list(map(int, line.strip().split())) for line in out_str.strip().splitlines() if line.strip() != '']
    # permute columns 0 and 1 in input
    perm_mat = [[row[1], row[0]] + row[2:] for row in mat]
    inp_perm = f"{n} {m}\n" + "\n".join(" ".join(str(v) for v in row) for row in perm_mat) + "\n"
    # run on permuted input
    out_str_perm = run(inp_perm)
    out_mat_perm = [list(map(int, line.strip().split())) for line in out_str_perm.strip().splitlines() if line.strip() != '']
    # permute columns of original output accordingly
    expected_perm = [[row[1], row[0]] + row[2:] for row in out_mat]
    assert out_mat_perm == expected_perm, "Column permutation not reflected in output"
    return True