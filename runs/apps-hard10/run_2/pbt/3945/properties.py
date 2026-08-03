import re
import itertools

def parse_input_output(x, out_str):
    """Parse input x and output out_str into matrices."""
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    a = [list(map(int, line.split())) for line in lines[1:]]
    out_lines = out_str.strip().splitlines()
    out = [list(map(int, line.split())) for line in out_lines[:n]]
    return n, m, a, out

def prop_output_dimensions_match_input(run, x):
    """PROPERTY: Output has exactly n lines, each with m integers."""
    n, m, a, out = parse_input_output(x, run(x))
    assert len(out) == n, f"Output lines: {len(out)} != n={n}"
    for i, row in enumerate(out):
        assert len(row) == m, f"Row {i} length: {len(row)} != m={m}"

def prop_output_values_within_bounds(run, x):
    """PROPERTY: Each output integer is between 1 and n+m (inclusive)."""
    n, m, a, out = parse_input_output(x, run(x))
    max_possible = n + m  # upper bound from problem structure
    for i in range(n):
        for j in range(m):
            assert 1 <= out[i][j] <= max_possible, f"out[{i}][{j}] = {out[i][j]} out of bounds"

def prop_symmetry_under_row_column_permutation(run, x):
    """PROPERTY: Permuting rows and columns permutes output identically."""
    import random
    n, m, a, out = parse_input_output(x, run(x))
    # Create random permutations
    perm_rows = list(range(n))
    perm_cols = list(range(m))
    random.shuffle(perm_rows)
    random.shuffle(perm_cols)
    # Apply permutations to input matrix
    a_perm = [[a[perm_rows[i]][perm_cols[j]] for j in range(m)] for i in range(n)]
    # Build new input string
    new_input = f"{n} {m}\n" + "\n".join(" ".join(map(str, row)) for row in a_perm)
    # Run on permuted input
    n2, m2, a2, out2 = parse_input_output(new_input, run(new_input))
    # Check that outputs are permuted the same way
    for i in range(n):
        for j in range(m):
            assert out[perm_rows[i]][perm_cols[j]] == out2[i][j], \
                f"Permutation mismatch at ({i},{j})"

def prop_monotonicity_wrt_street_values(run, x):
    """PROPERTY: If we increase a single skyscraper height, no answer decreases."""
    n, m, a, out = parse_input_output(x, run(x))
    # Try increasing one element
    for i in range(n):
        for j in range(m):
            new_a = [row[:] for row in a]
            new_a[i][j] = a[i][j] + 1
            new_input = f"{n} {m}\n" + "\n".join(" ".join(map(str, row)) for row in new_a)
            _, _, _, out2 = parse_input_output(new_input, run(new_input))
            # For the changed intersection, answer should not decrease
            assert out2[i][j] >= out[i][j], f"Monotonicity violated at ({i},{j})"
            # For other intersections, no universal monotonicity guaranteed, skip them

def prop_answer_unchanged_by_global_height_remapping(run, x):
    """PROPERTY: Applying a strictly increasing map to all heights leaves output unchanged."""
    n, m, a, out = parse_input_output(x, run(x))
    # Create a strictly increasing mapping: height -> rank in sorted unique heights
    all_heights = sorted(set(v for row in a for v in row))
    rank = {h: i+1 for i, h in enumerate(all_heights)}
    a_remapped = [[rank[v] for v in row] for row in a]
    new_input = f"{n} {m}\n" + "\n".join(" ".join(map(str, row)) for row in a_remapped)
    _, _, _, out2 = parse_input_output(new_input, run(new_input))
    # Output should be identical because only order matters
    for i in range(n):
        for j in range(m):
            assert out[i][j] == out2[i][j], f"Remapping changed output at ({i},{j})"