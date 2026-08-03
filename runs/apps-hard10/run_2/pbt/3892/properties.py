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

def prop_adding_duplicate_candy_increases_time(run, x):
    """PROPERTY: Adding a candy identical to an existing one cannot decrease time."""
    n, m, candies = parse_input(x)
    if m >= 200:  # max m is 200, can't add
        return
    out = run(x)
    times_orig = parse_output(out, n)
    # add a duplicate of first candy
    dup = candies[0]
    new_input = f"{n} {m+1}\n" + "\n".join(f"{a} {b}" for a, b in candies) + f"\n{dup[0]} {dup[1]}"
    new_out = run(new_input)
    times_new = parse_output(new_out, n)
    # time for each start station cannot decrease
    for i in range(n):
        assert times_new[i] >= times_orig[i]

def prop_reverse_network_symmetry(run, x):
    """PROPERTY: Reversing direction of network (n->1) and swapping a,b yields same times reversed."""
    n, m, candies = parse_input(x)
    out = run(x)
    times = parse_output(out, n)
    # reverse network: station i's next is i-1 (mod n, 1-based)
    # equivalent to relabel station i -> n+1-i
    def rev(s):
        return n + 1 - s
    new_candies = [(rev(b), rev(a)) for (a, b) in candies]  # swap a,b because direction reversed
    new_input = f"{n} {m}\n" + "\n".join(f"{a} {b}" for a, b in new_candies)
    new_out = run(new_input)
    new_times = parse_output(new_out, n)
    # times should be reversed: new_times[rev(i)-1] = times[i-1]
    for i in range(1, n+1):
        new_i = rev(i)
        assert new_times[new_i-1] == times[i-1]

def prop_merge_split_candies_inequality(run, x):
    """PROPERTY: Splitting a candy into two with same a,b cannot reduce total time below original."""
    n, m, candies = parse_input(x)
    if m >= 200:  # cannot add two candies
        return
    out = run(x)
    times_orig = parse_output(out, n)
    # pick first candy
    a1, b1 = candies[0]
    # create new input with that candy replaced by two identical ones
    new_candies = candies[:]  # includes first candy
    new_candies.append((a1, b1))  # duplicate it
    new_input = f"{n} {m+1}\n" + "\n".join(f"{a} {b}" for a, b in new_candies)
    new_out = run(new_input)
    times_new = parse_output(new_out, n)
    # times cannot be less than original for any start station
    for i in range(n):
        assert times_new[i] >= times_orig[i]