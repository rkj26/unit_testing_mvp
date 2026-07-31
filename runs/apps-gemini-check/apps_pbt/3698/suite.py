from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str  (the harness provides this)

# Precompute popcount for numbers up to 1000 (max length of n)
# This is used to determine the number of operations to reduce a number to 1.
# max_val = 2^1000 - 1. The maximum popcount for such a number is 1000.
# The maximum popcount of 1000 is 4 (1000_10 = 1111101000_2).
# The maximum popcount of 4 is 2 (4_10 = 100_2).
# The maximum popcount of 2 is 1 (2_10 = 10_2).
# So, the maximum number of operations is small.
MAX_N_LEN = 1000
MAX_K = 1000

# Precompute popcount for numbers up to MAX_N_LEN
popcount_cache = [0] * (MAX_N_LEN + 1)
for i in range(1, MAX_N_LEN + 1):
    popcount_cache[i] = bin(i).count('1')

# Precompute the number of operations to reduce a number x to 1
# ops_to_one[x] stores the minimum number of operations to reduce x to 1.
# We only need this for x up to MAX_N_LEN (the maximum possible popcount of n).
ops_to_one = [0] * (MAX_N_LEN + 1)
ops_to_one[1] = 0 # 1 is already 1, 0 operations
for i in range(2, MAX_N_LEN + 1):
    current_val = i
    operations = 0
    while current_val != 1:
        current_val = popcount_cache[current_val]
        operations += 1
    ops_to_one[i] = operations

@st.composite
def make_input(draw):
    # n is given in its binary representation without any leading zeros.
    # 1 <= n < 2^1000, so n has length between 1 and 1000.
    n_len = draw(st.integers(min_value=1, max_value=MAX_N_LEN))
    n_binary = '1' + draw(st.text(st.sampled_from('01'), min_size=n_len - 1, max_size=n_len - 1))

    # k (0 <= k <= 1000)
    k = draw(st.integers(min_value=0, max_value=MAX_K))

    return f"{n_binary}\n{k}\n"

@given(make_input())
@settings(max_examples=50, deadline=None)
def test_output_format_and_range(stdin):
    stdout = run_candidate(stdin)
    try:
        result = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not an integer: {stdout}")

    # The answer can be large, output it modulo 10^9 + 7.
    # This implies the result should be non-negative and less than 10^9 + 7.
    MOD = 10**9 + 7
    assert 0 <= result < MOD, f"Result {result} is out of expected range [0, {MOD-1}]"

@given(make_input())
@settings(max_examples=50, deadline=None)
def test_k_equals_zero_or_one(stdin):
    n_binary, k_str = stdin.strip().split('\n')
    k = int(k_str)

    stdout = run_candidate(stdin)
    result = int(stdout.strip())

    # If k = 0, only the number 1 is special (0 operations to reduce to 1).
    # So, if n >= 1, the count should be 1. Otherwise 0.
    if k == 0:
        # n_binary is always >= '1', so n >= 1.
        assert result == 1, f"For k=0, expected 1, got {result}"
    
    # If k = 1, special numbers are those that reduce to 1 in exactly one operation.
    # This means their popcount must be 1.
    # The only positive integer with popcount 1 is a power of 2 (1, 2, 4, 8, ...).
    # We need to count powers of 2 <= n.
    if k == 1:
        n_val = int(n_binary, 2)
        expected_count = 0
        power_of_2 = 1
        while power_of_2 <= n_val:
            expected_count += 1
            if power_of_2 > n_val // 2: # Avoid overflow for large n
                break
            power_of_2 *= 2
        
        MOD = 10**9 + 7
        assert result == (expected_count % MOD), \
            f"For k=1, n={n_binary}, expected {expected_count % MOD}, got {result}"

@given(make_input())
@settings(max_examples=50, deadline=None)
def test_k_too_large_for_any_number(stdin):
    n_binary, k_str = stdin.strip().split('\n')
    k = int(k_str)

    stdout = run_candidate(stdin)
    result = int(stdout.strip())

    # The maximum number of operations to reduce any number to 1 is small.
    # For example, for n < 2^1000, max popcount is 1000.
    # popcount(1000) = 6 (1111101000_2)
    # popcount(6) = 2 (110_2)
    # popcount(2) = 1 (10_2)
    # So, max operations for any number up to 2^1000-1 is 3 (e.g., 2^1000-1 -> 1000 -> 6 -> 2 -> 1).
    # The actual maximum is 4 (e.g., 2^1000-1 -> 1000 -> 6 -> 2 -> 1).
    # Let's find the maximum possible k for which an answer can be non-zero.
    # The maximum popcount for a number up to 2^1000-1 is 1000 (for 2^1000-1).
    # The sequence of popcounts would be:
    # x -> popcount(x) -> popcount(popcount(x)) -> ... -> 1
    # Max popcount is 1000.
    # ops_to_one[1000] = 3 (1000 -> 6 -> 2 -> 1)
    # So, if k > ops_to_one[max_popcount_of_n], the answer must be 0.
    # max_popcount_of_n is the length of n_binary, which is at most 1000.
    max_possible_popcount = len(n_binary)
    
    # If k is greater than the maximum possible operations for any number whose popcount is <= max_possible_popcount,
    # then the answer must be 0.
    # The maximum value for popcount(x) is len(n_binary).
    # The maximum value for popcount(popcount(x)) is popcount(len(n_binary)).
    # The maximum value for popcount(popcount(popcount(x))) is popcount(popcount(len(n_binary))).
    # We need to find the maximum ops_to_one[p] where p <= len(n_binary).
    max_ops_for_any_popcount_up_to_len_n = 0
    for p_val in range(1, max_possible_popcount + 1):
        max_ops_for_any_popcount_up_to_len_n = max(max_ops_for_any_popcount_up_to_len_n, ops_to_one[p_val])

    if k > max_ops_for_any_popcount_up_to_len_n:
        assert result == 0, \
            f"For k={k} (too large), expected 0, got {result}. Max ops for popcount up to {max_possible_popcount} is {max_ops_for_any_popcount_up_to_len_n}"

@given(make_input())
@settings(max_examples=50, deadline=None)
def test_monotonicity_with_k(stdin):
    n_binary, k_str = stdin.strip().split('\n')
    k = int(k_str)

    # If k is increased, the set of special numbers can only shrink or stay the same.
    # Thus, the count of special numbers should be non-increasing.
    # This is not strictly true because the definition is "minimum number of operations".
    # If a number X takes 2 operations to reduce to 1, it's special for k=2.
    # It's NOT special for k=1, because it takes 2 ops, not 1.
    # It's NOT special for k=3, because it takes 2 ops, not 3.
    # So, the count is not monotonic with k.

    # However, we can test a different kind of monotonicity.
    # If k is fixed, and n increases, the count should be non-decreasing.
    # This is a standard property for counting problems.
    if len(n_binary) > 1: # Need at least two bits to make a smaller n
        # Create a slightly smaller n by flipping the last bit from 1 to 0, if possible.
        # Or by truncating if the last bit is 0.
        n_val = int(n_binary, 2)
        
        # Try a slightly smaller n
        smaller_n_binary = None
        if n_binary.endswith('1'):
            smaller_n_binary = n_binary[:-1] + '0'
        elif len(n_binary) > 1:
            # If it ends with 0, try removing the last bit (effectively dividing by 2)
            smaller_n_binary = n_binary[:-1]
            if smaller_n_binary == '0': # Ensure no leading zeros
                smaller_n_binary = '1' # Smallest possible n
        
        if smaller_n_binary and smaller_n_binary != '0':
            stdin_smaller_n = f"{smaller_n_binary}\n{k}\n"
            
            stdout_n = run_candidate(stdin)
            result_n = int(stdout_n.strip())

            stdout_smaller_n = run_candidate(stdin_smaller_n)
            result_smaller_n = int(stdout_smaller_n.strip())

            assert result_n >= result_smaller_n, \
                f"Monotonicity violation: n={n_binary}, k={k} -> {result_n}; " \
                f"smaller_n={smaller_n_binary}, k={k} -> {result_smaller_n}. Expected result_n >= result_smaller_n."