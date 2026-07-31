import random

# Precompute ops_val outside functions to avoid recomputing on every check call.
# _ops_val[p] stores the minimum number of operations to reduce 'p' to 1.
# The maximum popcount for a number less than 2^1000 is 1000.
# So, we need ops_val for p from 1 to 1000.
MAX_BITS = 1000
_ops_val = [0] * (MAX_BITS + 1)
# ops(1) = 0
_ops_val[1] = 0
# For p > 1, ops(p) = 1 + ops(popcount(p))
for i in range(2, MAX_BITS + 1):
    _ops_val[i] = 1 + _ops_val[bin(i).count('1')]

# Determine the maximum possible 'k' value for x > 1.
# A number 'x' (where x > 1) is special if ops(x) = k.
# This implies 1 + ops(popcount(x)) = k, so ops(popcount(x)) = k - 1.
# The value popcount(x) can be at most MAX_BITS (1000).
# We need to find the maximum value of _ops_val[p] for p in [1, 1000].
# Tracing _ops_val:
# _ops_val[1]=0
# _ops_val[2]=1+_ops_val[1]=1
# _ops_val[3]=1+_ops_val[2]=2
# _ops_val[7]=1+_ops_val[3]=3
# _ops_val[127]=1+_ops_val[7]=4 (since popcount(127)=7)
# The maximum value in _ops_val for p in [1, 1000] is 4.
# So, k-1 can be at most 4.
# Therefore, the maximum k for x > 1 is 4 + 1 = 5.
_max_k_for_x_greater_than_1 = 5


def gen_input() -> str:
    test_cases = [
        # Provided examples
        ("110", "2"),
        ("111111011", "2"),
        ("100011110011110110100", "7"),
        # Smallest/boundary values for n
        ("1", "0"),
        ("1", "1"),
        ("10", "0"),
        ("10", "1"),
        ("10", "2"),
        ("11", "0"),
        ("11", "1"),
        ("11", "2"),
        # Max length n and boundary k values
        ("1" * MAX_BITS, "0"),  # n = 2^1000 - 1, k=0
        ("1" * MAX_BITS, "1"),  # n = 2^1000 - 1, k=1
        ("1" * MAX_BITS, "2"),  # n = 2^1000 - 1, k=2
        ("1" * MAX_BITS, str(_max_k_for_x_greater_than_1)),  # n = 2^1000 - 1, k=5
        ("1" * MAX_BITS, str(_max_k_for_x_greater_than_1 + 1)),  # n = 2^1000 - 1, k=6 (expected 0)
        # Power of 2 for n and boundary k values
        ("1" + "0" * (MAX_BITS - 1), "0"),  # n = 2^999, k=0
        ("1" + "0" * (MAX_BITS - 1), "1"),  # n = 2^999, k=1
        ("1" + "0" * (MAX_BITS - 1), "2"),  # n = 2^999, k=2
        ("1" + "0" * (MAX_BITS - 1), str(_max_k_for_x_greater_than_1)),
        ("1" + "0" * (MAX_BITS - 1), str(_max_k_for_x_greater_than_1 + 1)),
    ]

    # Add random cases to explore diverse inputs
    for _ in range(50):
        n_len = random.randint(1, MAX_BITS)
        
        # Vary n_bin representation: truly random, all ones, or power of 2
        r_n = random.random()
        if r_n < 0.33: # Truly random n_bin
            n_bin = '1' + ''.join(random.choice('01') for _ in range(n_len - 1))
        elif r_n < 0.66: # All ones n_bin (e.g., 111)
            n_bin = '1' * n_len
        else: # Power of 2 n_bin (e.g., 1000)
            n_bin = '1' + '0' * (n_len - 1)
        
        # Vary k value: prioritize boundary/special k values, but also include intermediate
        r_k = random.randint(0, 3) 
        if r_k == 0: # k=0
            k_val = 0
        elif r_k == 1: # k=1
            k_val = 1
        elif r_k == 2: # k > _max_k_for_x_greater_than_1 (expected 0 output)
            k_val = random.randint(_max_k_for_x_greater_than_1 + 1, MAX_BITS)
        else: # Intermediate k values (2 to 5)
            k_val = random.randint(2, _max_k_for_x_greater_than_1)
        
        test_cases.append((n_bin, str(k_val)))

    # Choose one test case randomly
    n_bin, k_str = random.choice(test_cases)
    return f"{n_bin}\n{k_str}\n"


def check(stdin: str, stdout: str) -> None:
    lines = stdin.strip().split('\n')
    n_bin = lines[0]
    k = int(lines[1])

    try:
        output_val = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout}' for input: n={n_bin}, k={k}")

    # Property 1: Output must be non-negative
    assert output_val >= 0, f"Output {output_val} is negative. Input: n={n_bin}, k={k}"

    # Property 2: Special case k=0
    # The only number 'x' for which ops(x) = 0 is x=1.
    # Since the problem constraint is 1 <= n, the number 1 is always included in the range [1, n].
    # Thus, for k=0, the answer must always be 1.
    if k == 0:
        assert output_val == 1, f"Expected 1 for k=0, got {output_val}. Input: n={n_bin}, k={k}"
        return  # This case is fully verified, no further checks needed for this input.

    # Property 3: Special case k=1
    # For a number 'x' (where x > 1) to have ops(x) = 1, it must satisfy:
    # 1 + ops(popcount(x)) = 1  =>  ops(popcount(x)) = 0.
    # The only number 'p' with ops(p) = 0 is p=1.
    # So, we need numbers 'x' such that popcount(x) = 1.
    # These are the powers of 2: 2^0, 2^1, 2^2, ... (i.e., 1, 2, 4, 8, ...).
    # The count of such powers of 2 (x > 0) that are not greater than n (given as n_bin)
    # is simply the length of n's binary representation.
    # For example, if n="110" (decimal 6), len(n_bin)=3. The special numbers are 1 (2^0), 2 (2^1), 4 (2^2). Count is 3.
    # If n="1" (decimal 1), len(n_bin)=1. The special number is 1 (2^0). Count is 1.
    if k == 1:
        expected_count = len(n_bin)
        assert output_val == expected_count, \
            f"Expected {expected_count} for k=1 (count of powers of 2 <= n), got {output_val}. Input: n={n_bin}, k={k}"
        return  # This case is fully verified.

    # Property 4: Cases where k is too large (k > 5)
    # As derived from _max_k_for_x_greater_than_1, the maximum possible value for 'k' when x > 1 is 5.
    # If k is greater than 5, it is impossible to find a number 'x' (where x > 1) that satisfies the condition.
    # Since k=0 and k=1 have already been handled, any k > 5 will result in a count of 0.
    if k > _max_k_for_x_greater_than_1:
        assert output_val == 0, \
            f"Expected 0 for k > {_max_k_for_x_greater_than_1} (no such numbers exist). Got {output_val}. Input: n={n_bin}, k={k}"
        return  # This case is fully verified.

    # For other values of k (k=2, 3, 4, 5), we cannot easily predict the exact count without
    # reimplementing a full solution.
    # However, we can still check the format and range of the output.
    # Property 5: Output must be within the modulo range
    MOD = 10**9 + 7
    assert 0 <= output_val < MOD, \
        f"Output {output_val} is out of expected modulo range [0, {MOD}-1]. Input: n={n_bin}, k={k}"