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