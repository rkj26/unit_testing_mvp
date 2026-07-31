from hypothesis import given, strategies as st, settings
import math

# Memoization for _calculate_ops to avoid redundant computations in brute force
_memo_ops = {}

def _calculate_ops(x):
    """
    Helper function to calculate the minimum number of operations to reduce x to 1.
    ops(1) = 0
    ops(x) = 1 + ops(popcount(x)) for x > 1
    """
    if x == 1:
        return 0
    if x <= 0:
        # Problem statement implies positive integers, but guard against invalid inputs
        return float('inf') 
    if x not in _memo_ops:
        _memo_ops[x] = 1 + _calculate_ops(bin(x).count('1'))
    return _memo_ops[x]

def _solve_brute_force_small_n(n_binary_str, k_val):
    """
    Brute-force solver for small N, used for verification.
    Counts numbers x <= N such that ops(x) == k_val, modulo 10^9 + 7.
    """
    N = int(n_binary_str, 2)
    count = 0
    mod_val = 10**9 + 7
    for x in range(1, N + 1):
        if _calculate_ops(x) == k_val:
            count = (count + 1) % mod_val
    return count

@st.composite
def make_input(draw, max_n_len=1000, max_k=1000):
    """
    Generates valid input (n_binary_str, k_val) according to problem constraints.
    n is a binary string without leading zeros, 1 <= n < 2^1000.
    k is an integer, 0 <= k <= 1000.
    """
    n_len = draw(st.integers(min_value=1, max_value=max_n_len))
    if n_len == 1:
        n_binary_str = '1'
    else:
        # Ensure no leading zeros by starting with '1'
        n_binary_str = '1' + draw(st.text(st.just('0') | st.just('1'), min_size=n_len-1, max_size=n_len-1))
    
    k_val = draw(st.integers(min_value=0, max_value=max_k))
    
    return f"{n_binary_str}\n{k_val}\n"

@st.composite
def make_input_small_n(draw):
    """
    Generates input with small N (length up to 20 bits) for brute-force verification.
    k can be any valid value (0 to 1000).
    """
    n_len = draw(st.integers(min_value=1, max_value=20)) # N up to 2^20 - 1
    if n_len == 1:
        n_binary_str = '1'
    else:
        n_binary_str = '1' + draw(st.text(st.just('0') | st.just('1'), min_size=n_len-1, max_size=n_len-1))
    
    k_val = draw(st.integers(min_value=0, max_value=1000)) # k can be large, brute force will return 0 if k > 4
    
    return f"{n_binary_str}\n{k_val}\n"

@st.composite
def make_input_small_n_and_n_plus_one(draw):
    """
    Generates two related inputs: (n, k) and (n+1, k) for small n.
    Used to verify monotonicity.
    """
    # Max N for (N+1) not to exceed roughly 2^19 - 1 (for length up to 19) to keep int conversion and brute force fast.
    n_len = draw(st.integers(min_value=1, max_value=18)) 
    if n_len == 1:
        n_binary_str = '1'
    else:
        n_binary_str = '1' + draw(st.text(st.just('0') | st.just('1'), min_size=n_len-1, max_size=n_len-1))
    
    k_val = draw(st.integers(min_value=0, max_value=1000)) # k can be large
    
    N = int(n_binary_str, 2)
    N_plus_one = N + 1
    N_plus_one_binary_str = bin(N_plus_one)[2:]
    
    return f"{n_binary_str}\n{k_val}\n", f"{N_plus_one_binary_str}\n{k_val}\n"


@given(make_input())
@settings(max_examples=50, deadline=None)
def test_k_edge_cases(stdin):
    """
    Tests specific properties based on the value of k, which are constant or simple to compute
    regardless of n (for n < 2^1000).
    1. If k=0: Only x=1 is special. Since n >= 1, the count is always 1.
    2. If k=1: Special numbers are powers of 2 greater than 1. The count is len(n_binary_str) - 1.
       (e.g., if n='1', count=0; if n='10', count=1 for x=2).
    3. If k > 4: For any x < 2^1000, the maximum number of operations to reduce to 1 is 4.
       (e.g., 2^1000-1 (1000 ones) -> 1000 -> 6 -> 2 -> 1, takes 4 steps).
       Thus, for k > 4, the count must be 0.
    """
    n_binary_str, k_str = stdin.strip().split('\n')
    k_val = int(k_str)
    
    stdout = run_candidate(stdin)
    result = stdout.strip()

    if k_val == 0:
        assert result == '1', f"Input: n={n_binary_str}, k={k_val}. Expected 1, got {result}"
    elif k_val == 1:
        expected_count = len(n_binary_str) - 1
        assert result == str(expected_count), f"Input: n={n_binary_str}, k={k_val}. Expected {expected_count}, got {result}"
    elif k_val > 4:
        assert result == '0', f"Input: n={n_binary_str}, k={k_val}. Expected 0, got {result}"

@given(make_input_small_n())
@settings(max_examples=100, deadline=None)
def test_small_n_brute_force_match(stdin):
    """
    For small N (binary string length up to 20), we can re-compute the correct answer
    using a brute-force approach and compare it directly with the candidate's output.
    This thoroughly tests the program's logic for a significant range of inputs
    where the true counts are generally small enough not to cause modulo issues.
    """
    n_binary_str, k_str = stdin.strip().split('\n')
    k_val = int(k_str)

    stdout = run_candidate(stdin)
    result = stdout.strip()

    expected_count = _solve_brute_force_small_n(n_binary_str, k_val)
    assert result == str(expected_count), f"Input: n={n_binary_str}, k={k_val}. Expected {expected_count}, got {result}"

@given(make_input_small_n_and_n_plus_one())
@settings(max_examples=100, deadline=None)
def test_small_n_monotonicity(inputs):
    """
    Tests the metamorphic property that if N1 < N2, then count(N1, k) <= count(N2, k).
    This test focuses on N and N+1 for small N values.
    Since N is small, the true counts are less than 10^9 + 7, allowing direct comparison
    of the numerical results without being affected by modulo arithmetic.
    """
    stdin_n, stdin_n_plus_one = inputs
    
    n_binary_str, k_str = stdin_n.strip().split('\n')
    k_val = int(k_str)
    N_val = int(n_binary_str, 2)

    # Brute force calculate expected counts to ensure that results are not affected by modulo
    # if the candidate implementation accidentally computes large numbers that wrap.
    expected_n_count = _solve_brute_force_small_n(n_binary_str, k_val)
    expected_n_plus_one_count = _solve_brute_force_small_n(bin(N_val + 1)[2:], k_val)

    # Run the candidate for both inputs
    stdout_n = run_candidate(stdin_n)
    stdout_n_plus_one = run_candidate(stdin_n_plus_one)
    
    result_n = int(stdout_n.strip())
    result_n_plus_one = int(stdout_n_plus_one.strip())

    # Assert that the candidate's output matches the expected monotonic property AND
    # also matches our brute force for small N to detect any subtle discrepancies.
    assert result_n <= result_n_plus_one, \
        f"Monotonicity failed for k={k_val}: count(n={n_binary_str})={result_n}, count(n+1={bin(N_val+1)[2:]})={result_n_plus_one}"
    assert result_n == expected_n_count, \
        f"Mismatch with brute force for n={n_binary_str}, k={k_val}: Expected {expected_n_count}, got {result_n}"
    assert result_n_plus_one == expected_n_plus_one_count, \
        f"Mismatch with brute force for n+1={bin(N_val+1)[2:]}, k={k_val}: Expected {expected_n_plus_one_count}, got {result_n_plus_one}"