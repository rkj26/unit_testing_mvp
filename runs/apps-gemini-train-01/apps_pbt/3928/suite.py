import random
import string

def gen_input() -> str:
    """
    Generates a valid input string for the problem.
    Covers various edge cases and typical competitive programming patterns.
    """
    test_type = random.choices(
        [
            'min_max_vals', 'all_same', 'all_distinct', 'alternating',
            'random_long_repeat_pattern', 'random_large', 'random_medium', 'random_small'
        ],
        weights=[5, 10, 5, 5, 10, 20, 20, 25], k=1
    )[0]

    n_val, a_val, b_val = 0, 0, 0
    s_val = ""

    # Ensure valid N, A, B within constraints [1, 5000]
    n_val = random.randint(1, 5000)
    a_val = random.randint(1, 5000)
    b_val = random.randint(1, 5000)

    if test_type == 'min_max_vals':
        n_val = random.choice([1, 2, 3, 5000])
        a_val = random.choice([1, 5000])
        b_val = random.choice([1, 5000])
        s_val = "".join(random.choice(string.ascii_lowercase) for _ in range(n_val))

    elif test_type == 'all_same':
        s_val = random.choice(string.ascii_lowercase) * n_val

    elif test_type == 'all_distinct':
        n_val = random.randint(1, min(26, 5000))  # Max 26 distinct lowercase letters
        s_val = "".join(random.sample(string.ascii_lowercase, n_val))

    elif test_type == 'alternating':
        if n_val == 1:
            s_val = random.choice(string.ascii_lowercase)
        else:
            char1 = random.choice(string.ascii_lowercase)
            char2 = random.choice(string.ascii_lowercase)
            while char1 == char2:
                char2 = random.choice(string.ascii_lowercase)
            s_val = "".join(char1 if i % 2 == 0 else char2 for i in range(n_val))

    elif test_type == 'random_long_repeat_pattern':
        if n_val == 1:
            s_val = random.choice(string.ascii_lowercase)
        else:
            # Create a repeating pattern that's likely to cause 'b' costs
            base_len = random.randint(1, min(n_val - 1, 2500)) # Base pattern length up to N/2
            base_pattern = "".join(random.choice(string.ascii_lowercase) for _ in range(base_len))
            
            s_list = []
            current_len = 0
            while current_len < n_val:
                segment_to_add = base_pattern
                if current_len + len(segment_to_add) > n_val:
                    segment_to_add = segment_to_add[:n_val - current_len]
                s_list.append(segment_to_add)
                current_len += len(segment_to_add)
            s_val = "".join(s_list)

    else:  # 'random_large', 'random_medium', 'random_small'
        s_val = "".join(random.choice(string.ascii_lowercase) for _ in range(n_val))
    
    # Final check for string length, should always be n_val
    if len(s_val) != n_val:
        # Fallback if complex generation somehow resulted in wrong length
        s_val = "".join(random.choice(string.ascii_lowercase) for _ in range(n_val))

    return f"{n_val} {a_val} {b_val}\n{s_val}\n"

def parse_stdin(stdin_str):
    """Parses the stdin string into N, A, B, and S."""
    lines = stdin_str.strip().split('\n')
    n_str, a_str, b_str = lines[0].split()
    n, a, b = int(n_str), int(a_str), int(b_str)
    s = lines[1]
    return n, a, b, s

def check(stdin: str, stdout: str) -> None:
    """
    Asserts properties that the correct output must satisfy.
    Raises AssertionError if any property is violated.
    """
    n, a, b, s = parse_stdin(stdin)

    # Property 1: Output is a single integer.
    try:
        output_value = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a single integer: '{stdout}'")

    # Property 2: Output value is within a reasonable range.
    # The minimum cost for N >= 1 is 'a' (cost of first character).
    # The maximum possible cost is N * A (encoding every character individually).
    assert 1 <= output_value <= n * a, \
        f"Output value {output_value} out of expected range [1, {n*a}] for N={n}, A={a}. Stdin: {stdin}"

    # Property 3: Specific check for strings consisting of identical characters.
    # For s = 'c' * N (e.g., "aaaaa"), the optimal cost follows a specific DP relation:
    # dp[i] = min cost to compress 'c'*i
    # dp[0] = 0
    # For i from 1 to N:
    #   dp[i] = dp[i-1] + a (always possible to encode s[i-1] as a single character)
    #   If i >= 2:
    #     To encode s[k...i-1] (length L = i-k) as a repeat, it must be a substring of s[0...k-1].
    #     For 'c'*N, this is true if L <= k (i.e., i-k <= k, which means i <= 2k, or k >= i/2).
    #     Since dp[k] is non-decreasing, we want the smallest k that satisfies this, which is k_min = ceil(i/2).
    #     Thus, dp[i] = min(dp[i], dp[k_min] + b)
    if len(set(s)) == 1:
        expected_dp = [0] * (n + 1)
        for i in range(1, n + 1):
            expected_dp[i] = expected_dp[i-1] + a # Option 1: encode current char for cost 'a'
            if i >= 2:
                # Option 2: encode s[k_min...i-1] as a repeat for cost 'b'
                # k_min is the start index of the current segment, such that (i-k_min) <= k_min
                k_min = (i + 1) // 2 # equivalent to ceil(i/2) for positive integers
                expected_dp[i] = min(expected_dp[i], expected_dp[k_min] + b)
        
        assert output_value == expected_dp[n], \
            f"Output value {output_value} incorrect for all-same characters (N={n}, A={a}, B={b}, S='{s}'). Expected: {expected_dp[n]}. Stdin: {stdin}"

    # Property 4: If A=1, B=1 and S consists of N distinct characters (N <= 26), cost should be N.
    # In this scenario, no multi-character segment can be a repeat (since all characters are unique).
    # Also, single characters cost 'a'=1. So every character must be encoded individually.
    # The total cost would be N * A = N * 1 = N.
    if a == 1 and b == 1 and n <= 26 and len(set(s)) == n:
        assert output_value == n, \
            f"Output value {output_value} incorrect for N distinct chars, A=1, B=1. Expected: {n}. Stdin: {stdin}"

    # Property 5: Output cost must be at least 'a' if N > 0 (which is always true since N >= 1).
    assert output_value >= a, \
        f"Output value {output_value} is less than 'a' ({a}) which is not possible. Stdin: {stdin}"