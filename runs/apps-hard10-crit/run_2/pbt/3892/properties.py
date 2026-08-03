import re
import itertools

def parse_input(in_str: str):
    lines = in_str.strip().splitlines()
    n_m = list(map(int, lines[0].split()))
    n, m = n_m[0], n_m[1]
    candies = []
    for i in range(1, m+1):
        a, b = map(int, lines[i].split())
        candies.append((a, b))
    return n, m, candies

def parse_output(out_str: str, n: int):
    nums = list(map(int, out_str.strip().split()))
    assert len(nums) == n
    return nums

def prop_output_format_and_bounds(run, x):
    """PROPERTY: Output must be exactly n integers, non-negative."""
    n, m, candies = parse_input(x)
    out = run(x)
    times = parse_output(out, n)
    # times are non-negative integers (could be zero only if m=0, but m>=1)
    assert all(t >= 0 for t in times)
    # no extra whitespace/newlines except possibly trailing newline allowed
    lines = out.strip().splitlines()
    assert len(lines) == 1
    tokens = lines[0].split()
    assert len(tokens) == n
    # check tokens are integers
    for tok in tokens:
        int(tok)

def prop_cyclic_shift_invariance(run, x):
    """PROPERTY: Rotating stations rotates answers accordingly."""
    n, m, candies = parse_input(x)
    out = run(x)
    times = parse_output(out, n)
    # rotate stations: map station i -> i+1 mod n (1-based)
    def rotate_station(s):
        return s % n + 1
    new_candies = [(rotate_station(a), rotate_station(b)) for (a, b) in candies]
    new_input = f"{n} {m}\n" + "\n".join(f"{a} {b}" for a, b in new_candies)
    new_out = run(new_input)
    new_times = parse_output(new_out, n)
    # times should rotate: new_times[i] = times[(i-2) mod n] (0-based)
    for i in range(n):
        orig_idx = (i - 1) % n  # because station i+1 in new corresponds to station i in original (1-based shift)
        assert new_times[i] == times[orig_idx]