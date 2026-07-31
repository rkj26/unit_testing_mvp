import random
import math

def gen_input() -> str:
    parts = []

    # N, M generation strategy
    rand_nm_choice = random.random()
    if rand_nm_choice < 0.1: # Small N, M
        n = random.randint(1, 5)
        m = random.randint(1, 5)
    elif rand_nm_choice < 0.2: # Max N, M
        n = 2000
        m = 2000
    elif rand_nm_choice < 0.3: # Skewed N, M (small N, large M)
        n = random.randint(1, 5)
        m = random.randint(1000, 2000)
    elif rand_nm_choice < 0.4: # Skewed N, M (large N, small M)
        n = random.randint(1000, 2000)
        m = random.randint(1, 5)
    else: # Random N, M
        n = random.randint(1, 2000)
        m = random.randint(1, 2000)
    parts.append(f"{n} {m}")

    # Array A generation strategy
    a = []
    rand_a_choice = random.random()
    if rand_a_choice < 0.1: # All ones
        a = [1] * n
    elif rand_a_choice < 0.2: # All max value
        a = [2000] * n
    elif rand_a_choice < 0.3: # Sorted
        a = sorted([random.randint(1, 2000) for _ in range(n)])
    elif rand_a_choice < 0.4: # Reverse sorted
        a = sorted([random.randint(1, 2000) for _ in range(n)], reverse=True)
    else: # Random values
        a = [random.randint(1, 2000) for _ in range(n)]
    parts.append(" ".join(map(str, a)))

    # Array B generation strategy (similar to A)
    b = []
    rand_b_choice = random.random()
    if rand_b_choice < 0.1:
        b = [1] * m
    elif rand_b_choice < 0.2:
        b = [2000] * m
    elif rand_b_choice < 0.3:
        b = sorted([random.randint(1, 2000) for _ in range(m)])
    elif rand_b_choice < 0.4:
        b = sorted([random.randint(1, 2000) for _ in range(m)], reverse=True)
    else:
        b = [random.randint(1, 2000) for _ in range(m)]
    parts.append(" ".join(map(str, b)))

    # X generation strategy
    x_val = 0
    rand_x_choice = random.random()
    if rand_x_choice < 0.1: # X very small, potentially leading to 0 output
        min_1x1_sum = min(a) * min(b)
        if min_1x1_sum > 1:
            x_val = random.randint(1, min_1x1_sum - 1)
        else: # If min_1x1_sum is 1, x_val must be at least 1, so ans won't be 0
            x_val = 1
    elif rand_x_choice < 0.2: # X very large, potentially allowing full rectangle
        x_val = 2 * 10**9 # Max possible X
    elif rand_x_choice < 0.3: # X moderate, around average 1x1 sum
        avg_a = sum(a) / n
        avg_b = sum(b) / m
        x_val = int(avg_a * avg_b * random.uniform(0.5, 2.0))
        x_val = max(1, min(x_val, 2 * 10**9))
    else: # Random X
        x_val = random.randint(1, 2 * 10**9)
    parts.append(str(x_val))

    return "\n".join(parts) + "\n"

def check(stdin: str, stdout: str) -> None:
    lines = stdin.strip().split('\n')
    n, m = map(int, lines[0].split())
    a = list(map(int, lines[1].split()))
    b = list(map(int, lines[2].split()))
    x = int(lines[3])

    try:
        ans = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout.strip()}'")

    # Property 1: Output must be within valid range [0, N*M]
    # The maximum possible area is N*M. The minimum is 0 if no subrectangle satisfies the condition.
    assert 0 <= ans <= n * m, \
        f"Output area {ans} is out of bounds [0, {n * m}] for N={n}, M={m}."

    # Precompute minimum sum for any subarray of a given length for array `a`
    # min_sum_for_len_a[k] stores the minimum sum of a subarray of length k.
    # Uses 0-indexed prefix sums for efficiency.
    min_sum_for_len_a = [float('inf')] * (n + 1) # min_sum_for_len_a[0] is unused, lengths are 1 to n
    prefix_a = [0] * (n + 1)
    for i in range(n):
        prefix_a[i+1] = prefix_a[i] + a[i]

    for length_a in range(1, n + 1):
        for i in range(n - length_a + 1): # i is starting index in 0-indexed 'a'
            current_sum_a = prefix_a[i + length_a] - prefix_a[i]
            min_sum_for_len_a[length_a] = min(min_sum_for_len_a[length_a], current_sum_a)

    # Precompute minimum sum for any subarray of a given length for array `b`
    min_sum_for_len_b = [float('inf')] * (m + 1) # min_sum_for_len_b[0] is unused, lengths are 1 to m
    prefix_b = [0] * (m + 1)
    for i in range(m):
        prefix_b[i+1] = prefix_b[i] + b[i]

    for length_b in range(1, m + 1):
        for i in range(m - length_b + 1): # i is starting index in 0-indexed 'b'
            current_sum_b = prefix_b[i + length_b] - prefix_b[i]
            min_sum_for_len_b[length_b] = min(min_sum_for_len_b[length_b], current_sum_b)

    # Property 2: If the program outputs a positive area `ans`,
    # then there must exist at least one subrectangle with area `ans`
    # and a total sum of elements less than or equal to `x`.
    # This verifies the "existence" part of the solution for the given `ans`.
    if ans > 0:
        found_valid_rectangle_for_ans = False
        # Iterate over possible lengths for the 'a' dimension of a rectangle with area `ans`
        # l_a must be a divisor of `ans`.
        for l_a in range(1, n + 1):
            if ans % l_a == 0:
                l_b = ans // l_a
                # Check if l_b is a valid length for the 'b' dimension
                if 1 <= l_b <= m:
                    sum_a_val = min_sum_for_len_a[l_a]
                    sum_b_val = min_sum_for_len_b[l_b]

                    # Check for valid minimum sums (not still float('inf')) and the total sum condition.
                    # Python integers handle arbitrary size, so `sum_a_val * sum_b_val` will not overflow.
                    if sum_a_val != float('inf') and sum_b_val != float('inf'):
                        if sum_a_val * sum_b_val <= x:
                            found_valid_rectangle_for_ans = True
                            break # Found a valid subrectangle, no need to check further for this ans
            if found_valid_rectangle_for_ans:
                break
        
        assert found_valid_rectangle_for_ans, \
            f"Program output {ans}, but no subrectangle of area {ans} was found whose total sum <= {x}."

    # Property 3: If the program outputs 0, then no subrectangle (of any size)
    # has a total sum of elements less than or equal to `x`.
    # This verifies the "no solution" case.
    if ans == 0:
        any_rectangle_fits = False
        # Iterate over all possible subrectangle dimensions (l_a x l_b)
        for l_a in range(1, n + 1):
            for l_b in range(1, m + 1):
                sum_a_val = min_sum_for_len_a[l_a]
                sum_b_val = min_sum_for_len_b[l_b]
                
                # If both minimum sums are valid and their product is <= x, then a solution exists.
                if sum_a_val != float('inf') and sum_b_val != float('inf'):
                    if sum_a_val * sum_b_val <= x:
                        any_rectangle_fits = True
                        break # Found one, so ans should not be 0
            if any_rectangle_fits:
                break
        
        assert not any_rectangle_fits, \
            f"Program output 0, but there exists at least one subrectangle with total sum <= {x}." \
            f" For example, a 1x1 rectangle with minimum sum {min(a)*min(b)}."

    # Property 4: If the sum of all elements in the entire N x M matrix is <= x,
    # then the maximum possible area must be N * M.
    total_sum_a = prefix_a[n]
    total_sum_b = prefix_b[m]
    
    # Check if the product of total sums is within the limit `x`.
    # Python handles large integers, so direct product is safe.
    if total_sum_a * total_sum_b <= x:
        assert ans == n * m, \
            f"The sum of all elements in the full {n}x{m} matrix ({total_sum_a * total_sum_b}) is <= {x}, " \
            f"but the program output {ans} instead of {n * m}."