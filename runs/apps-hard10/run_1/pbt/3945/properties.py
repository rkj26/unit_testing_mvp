import itertools

def prop_output_shape_and_bounds(run, x):
    """PROPERTY: Output has n lines, each with m space-separated integers between 1 and n+m-1."""
    out = run(x).strip()
    lines = out.splitlines()
    if not lines:
        raise AssertionError("Empty output")
    n_str, m_str = x.strip().split()[:2]
    n, m = int(n_str), int(m_str)
    assert len(lines) == n, f"Expected {n} lines, got {len(lines)}"
    for i, line in enumerate(lines):
        parts = line.strip().split()
        assert len(parts) == m, f"Line {i}: expected {m} numbers, got {len(parts)}"
        for j, part in enumerate(parts):
            val = int(part)
            assert 1 <= val <= n + m - 1, f"Value {val} at ({i},{j}) out of range"

def prop_identical_rows_preserve_answers(run, x):
    """PROPERTY: If two rows have identical heights, their output rows are identical."""
    lines = x.strip().splitlines()
    header = lines[0]
    data_lines = lines[1:]
    n_str, m_str = header.split()
    n, m = int(n_str), int(m_str)
    if n <= 1:
        return  # nothing to compare
    # Find two rows with identical values
    for i1 in range(n):
        for i2 in range(i1 + 1, n):
            if data_lines[i1].strip() == data_lines[i2].strip():
                out = run(x).strip().splitlines()
                assert out[i1].strip() == out[i2].strip(), f"Rows {i1} and {i2} identical in input but not in output"

def prop_transpose_invariance(run, x):
    """PROPERTY: Transposing input transposes output (since problem is symmetric)."""
    lines = x.strip().splitlines()
    header = lines[0]
    data_lines = lines[1:]
    n_str, m_str = header.split()
    n, m = int(n_str), int(m_str)
    # Build transposed input
    transposed_lines = [f"{m} {n}"]
    for j in range(m):
        row = []
        for i in range(n):
            row.append(data_lines[i].split()[j])
        transposed_lines.append(" ".join(row))
    transposed_input = "\n".join(transposed_lines)
    out1 = run(x).strip()
    out2 = run(transposed_input).strip()
    # Parse outputs
    mat1 = [list(map(int, line.split())) for line in out1.splitlines()]
    mat2 = [list(map(int, line.split())) for line in out2.splitlines()]
    # Check transpose relationship
    for i in range(n):
        for j in range(m):
            assert mat1[i][j] == mat2[j][i], f"Transpose mismatch at ({i},{j})"

def prop_monotonicity_wrt_row_sorting(run, x):
    """PROPERTY: Sorting a row in ascending order does not decrease any entry in that row of output."""
    import copy
    lines = x.strip().splitlines()
    header = lines[0]
    data_lines = lines[1:]
    n_str, m_str = header.split()
    n, m = int(n_str), int(m_str)
    if m <= 1:
        return  # nothing to sort
    # Pick a random row to sort
    for row_idx in range(n):
        orig_row = list(map(int, data_lines[row_idx].split()))
        sorted_row = sorted(orig_row)
        if orig_row == sorted_row:
            continue
        # Build modified input
        new_data = copy.deepcopy(data_lines)
        new_data[row_idx] = " ".join(map(str, sorted_row))
        new_input = header + "\n" + "\n".join(new_data)
        orig_out = run(x).strip().splitlines()
        new_out = run(new_input).strip().splitlines()
        orig_vals = list(map(int, orig_out[row_idx].split()))
        new_vals = list(map(int, new_out[row_idx].split()))
        for col in range(m):
            assert new_vals[col] >= orig_vals[col], f"Row {row_idx}, col {col}: {new_vals[col]} < {orig_vals[col]} after sorting row"

def prop_constant_matrix(run, x):
    """PROPERTY: If all heights are equal, output is all 1's."""
    lines = x.strip().splitlines()
    header = lines[0]
    data_lines = lines[1:]
    n_str, m_str = header.split()
    n, m = int(n_str), int(m_str)
    first_val = None
    all_same = True
    for line in data_lines:
        vals = line.split()
        for v in vals:
            if first_val is None:
                first_val = v
            elif v != first_val:
                all_same = False
                break
        if not all_same:
            break
    if all_same:
        out = run(x).strip()
        for line in out.splitlines():
            vals = list(map(int, line.split()))
            assert all(v == 1 for v in vals), f"Constant input should give all 1's, got {vals}"