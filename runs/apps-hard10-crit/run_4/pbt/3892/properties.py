import itertools
import math

def prop_output_format(run, x):
    """PROPERTY: Output line contains exactly n space-separated integers, ending with newline."""
    out = run(x)
    lines = out.strip().split('\n')
    assert len(lines) == 1, "Output must be exactly one line"
    parts = lines[0].split()
    # Get n from input
    lines_in = x.strip().split('\n')
    n = int(lines_in[0].split()[0])
    assert len(parts) == n, f"Expected {n} numbers, got {len(parts)}"
    for p in parts:
        assert p.isdigit() or (p[0] == '-' and p[1:].isdigit()), f"Non-integer output: {p}"
    return True

def prop_non_decreasing_with_initial_distance(run, x):
    """PROPERTY: If we rotate stations (shift indices), answers rotate accordingly."""
    lines = x.strip().split('\n')
    first = list(map(int, lines[0].split()))
    n, m = first[0], first[1]
    candies = [tuple(map(int, line.split())) for line in lines[1:1+m]]
    out = run(x)
    ans = list(map(int, out.strip().split()))
    # Rotate everything by +1 mod n
    def shift(v, delta):
        return ((v - 1 + delta) % n) + 1
    new_candies = [(shift(a, 1), shift(b, 1)) for (a, b) in candies]
    new_input = f"{n} {m}\n" + "\n".join(f"{a} {b}" for (a, b) in new_candies)
    new_out = run(new_input)
    new_ans = list(map(int, new_out.strip().split()))
    # Check rotation property: answer for station i in original = answer for station i+1 in shifted
    for i in range(n):
        assert ans[i] == new_ans[(i - 1) % n], f"Rotation mismatch at i={i}"
    return True