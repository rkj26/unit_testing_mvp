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

def prop_adding_unreachable_candy_increases_time(run, x):
    """PROPERTY: Adding a candy with a_i = b_i (impossible per spec) would break, but adding a real candy cannot decrease time."""
    lines = x.strip().split('\n')
    first = list(map(int, lines[0].split()))
    n, m = first[0], first[1]
    candies = [tuple(map(int, line.split())) for line in lines[1:1+m]]
    out = run(x)
    ans = list(map(int, out.strip().split()))
    # Add a new candy from station 1 to station n (valid, distinct)
    new_candies = candies + [(1, n)]
    new_input = f"{n} {m+1}\n" + "\n".join(f"{a} {b}" for (a, b) in new_candies)
    new_out = run(new_input)
    new_ans = list(map(int, new_out.strip().split()))
    for i in range(n):
        assert new_ans[i] >= ans[i], f"Time decreased at station {i} after adding a candy"
    return True

def prop_duplicate_candies_symmetry(run, x):
    """PROPERTY: Duplicating all candies exactly doubles the total work for each starting station, or less if train can carry multiple at once? Actually, train can carry infinite, so duplicating candies with same (a,b) may not double time if they can be delivered together. But here loading rule: at most one candy can be loaded from a station before leaving. So duplicates at same a need separate passes. So time should at least increase (or stay same if m=0). We check monotonic increase."""
    lines = x.strip().split('\n')
    first = list(map(int, lines[0].split()))
    n, m = first[0], first[1]
    candies = [tuple(map(int, line.split())) for line in lines[1:1+m]]
    out = run(x)
    ans = list(map(int, out.strip().split()))
    # Duplicate all candies
    new_candies = candies + candies
    new_input = f"{n} {2*m}\n" + "\n".join(f"{a} {b}" for (a, b) in new_candies)
    new_out = run(new_input)
    new_ans = list(map(int, new_out.strip().split()))
    for i in range(n):
        assert new_ans[i] >= ans[i], f"Time decreased after duplicating all candies at station {i}"
    return True

def prop_merge_split_consistency(run, x):
    """PROPERTY: Splitting a candy into two steps (a->t, t->b) with intermediate t increases or keeps same total time."""
    import random
    lines = x.strip().split('\n')
    first = list(map(int, lines[0].split()))
    n, m = first[0], first[1]
    candies = [tuple(map(int, line.split())) for line in lines[1:1+m]]
    if m == 0:
        return True
    out = run(x)
    ans = list(map(int, out.strip().split()))
    # Pick a random candy
    idx = random.randint(0, m-1)
    a, b = candies[idx]
    # Choose intermediate station t different from a and b
    possible = [i for i in range(1, n+1) if i != a and i != b]
    if not possible:
        return True
    t = possible[0]
    new_candies = candies[:idx] + candies[idx+1:] + [(a, t), (t, b)]
    new_input = f"{n} {m+1}\n" + "\n".join(f"{a} {b}" for (a, b) in new_candies)
    new_out = run(new_input)
    new_ans = list(map(int, new_out.strip().split()))
    # Delivering via intermediate should not be faster than direct
    for i in range(n):
        assert new_ans[i] >= ans[i], f"Splitting candy made it faster at station {i}"
    return True