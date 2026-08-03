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