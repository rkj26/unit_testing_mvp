import random

MOD = 998244353
MAX_COMB_N = 3999  # Maximum value for N+K-1 (2000+2000-1)
fact = [1] * (MAX_COMB_N + 1)
inv_fact = [1] * (MAX_COMB_N + 1)

def precompute_factorials():
    """Precomputes factorials and inverse factorials modulo MOD."""
    fact[0] = 1
    for i in range(1, MAX_COMB_N + 1):
        fact[i] = (fact[i-1] * i) % MOD
    
    # inv_fact[MAX_COMB_N] = fact[MAX_COMB_N]^(MOD-2) mod MOD (Fermat's Little Theorem)
    inv_fact[MAX_COMB_N] = pow(fact[MAX_COMB_N], MOD - 2, MOD)
    
    # Compute inverse factorials for smaller numbers
    for i in range(MAX_COMB_N - 1, -1, -1):
        inv_fact[i] = (inv_fact[i+1] * (i+1)) % MOD

# Precompute factorials once when the script is loaded
precompute_factorials()

def nCr_mod_p(n, r):
    """Calculates n choose r modulo MOD."""
    if r < 0 or r > n:
        return 0
    num = fact[n]
    den = (inv_fact[r] * inv_fact[n-r]) % MOD
    return (num * den) % MOD

def gen_input() -> str:
    """
    Generates a single input string for the problem.
    Covers boundary conditions, typical values, and some random cases.
    """
    test_cases = [
        (1, 2),        # Smallest K, N
        (3, 3),        # Sample 1
        (4, 5),        # Sample 2
        (2000, 2000),  # Max K, Max N
        (1, 2000),     # Min K, Max N
        (2000, 2),     # Max K, Min N (triggers N=2 specific check)
        (2, 2),        # Small K, N=2 (triggers N=2 specific check)
        (2, 3),        # Small K, Small N
        (10, 10),      # Medium K, N
        (100, 50),     # K large, N small
        (50, 100),     # K small, N large
        (random.randint(1, 2000), 2), # Random K, fixed N=2
        (1, random.randint(2, 2000)), # Fixed K=1, random N
    ]

    # Add several random cases to explore the input space more broadly
    for _ in range(random.randint(5, 10)):
        K = random.randint(1, 2000)
        N = random.randint(2, 2000)
        test_cases.append((K, N))
    
    # Pick one of the generated test cases
    K, N = random.choice(test_cases)
    return f"{K} {N}\n"

def check(stdin: str, stdout: str) -> None:
    """
    Verifies properties of the program's output.

    The problem asks for combinations of N dice (1 to K sides) such that no two *distinct* dice
    (positions) sum to i. If a value V appears multiple times, say on dice D_a and D_b, then D_a + D_b = 2V.
    If values V1 and V2 (V1 != V2) appear on dice D_a and D_b, then D_a + D_b = V1 + V2.
    The condition is that for any two dice D_j, D_k (j!=k) showing values x_j, x_k, we must have x_j + x_k != i.
    This implies:
    1. If a value `v` is shown by `c_v >= 2` dice, then `2*v != i`.
    2. If values `v1` and `v2` (`v1 != v2`) are shown by at least one die each, then `v1 + v2 != i`.
    """
    lines = stdin.strip().split()
    K = int(lines[0])
    N = int(lines[1])

    try:
        output_values = [int(x) for x in stdout.strip().split()]
    except ValueError:
        raise AssertionError(f"Output for K={K}, N={N} contains non-integer values: {stdout}")

    # Property 1: Output size
    # Expected output contains 2K-1 integers, for i=2, ..., 2K.
    expected_output_len = 2 * K - 1
    assert len(output_values) == expected_output_len, \
        f"Output length mismatch for K={K}, N={N}. Expected {expected_output_len} values, got {len(output_values)}."

    # Property 2: All values are within modulo range [0, MOD-1]
    for idx, val in enumerate(output_values):
        assert 0 <= val < MOD, \
            f"Output value out of modulo range for i={idx+2} (K={K}, N={N}). Got {val}, expected in [0, {MOD-1}]."

    # Property 3: Symmetry of answers
    # The number of valid combinations for 'i' should be equal to that for '2K+2-i'.
    # output_values[j] corresponds to i = j+2.
    # So, output_values[j] should equal output_values[j'] where j'+2 = 2K+2-(j+2) => j' = 2K-j-2.
    # We iterate j from 0 up to (K-2), as the midpoint is j = K-2 (for i = K).
    # The index 2K-2-j will correctly cover the symmetric parts.
    for j in range(K - 1): # loop for j in [0, K-2]
        assert output_values[j] == output_values[2*K - 2 - j], \
            f"Symmetry violation for K={K}, N={N}. For i={j+2} and i'={2*K+2-(j+2)} ({2*K-j}): " \
            f"Values {output_values[j]} != {output_values[2*K-2-j]} (indices {j} and {2*K-2-j})."

    # Property 4: Value for i=2 (first element, output_values[0])
    # For i=2, the condition "x_j + x_k != 2" implies:
    # 1. If a value `v` is shown by `c_v >= 2` dice, then `2*v != 2`, meaning `v != 1`.
    # 2. If values `v1` and `v2` (`v1 != v2`) are shown, then `v1 + v2 != 2`. This is vacuously true
    #    for positive integers `v1, v2` where `v1 != v2`.
    # So, the only restriction is that the value 1 cannot appear on two or more dice (`c_1 <= 1`).
    # Number of combinations with `c_1 = 0`: Choose N dice from values {2, ..., K}. (K-1 available values).
    #   Stars and bars: nCr(N + (K-1) - 1, N) = nCr(N+K-2, N).
    # Number of combinations with `c_1 = 1`: One die shows 1. Choose N-1 dice from values {2, ..., K}.
    #   Stars and bars: nCr((N-1) + (K-1) - 1, N-1) = nCr(N+K-3, N-1).
    expected_ans0 = (nCr_mod_p(N + K - 2, N) + nCr_mod_p(N + K - 3, N - 1)) % MOD
    assert output_values[0] == expected_ans0, \
        f"Incorrect value for i=2 (first output) for K={K}, N={N}. Expected {expected_ans0}, got {output_values[0]}."

    # Property 5: Specific check for N=2
    # For N=2, a combination is simply (x1, x2) with 1 <= x1 <= x2 <= K.
    # The condition "x_j + x_k != i" simply means x1 + x2 != i.
    # So, the answer for a given i is (total combinations for N=2) - (invalid combinations for N=2 and i).
    if N == 2:
        # Total combinations of 2 dice from K sides (indistinguishable): nCr(2+K-1, 2) = nCr(K+1, 2)
        total_combinations_N2 = nCr_mod_p(K + 1, 2)

        for j in range(expected_output_len):
            current_i = j + 2 # The sum i for the current output value

            # Count invalid pairs (x1, x2) such that 1 <= x1 <= x2 <= K and x1 + x2 = current_i.
            # From x1 + x2 = current_i and x1 <= x2, we get 2*x1 <= current_i => x1 <= current_i / 2.
            # From x1 + x2 = current_i and x2 <= K, we get x1 >= current_i - K.
            lower_bound_x1 = max(1, current_i - K)
            upper_bound_x1 = min(K, current_i // 2) # Note: x1 must also be <= K

            num_invalid_pairs = 0
            if lower_bound_x1 <= upper_bound_x1:
                num_invalid_pairs = upper_bound_x1 - lower_bound_x1 + 1
            
            # The result must be non-negative, add MOD before taking modulo if subtraction could be negative
            expected_ans_N2_i = (total_combinations_N2 - num_invalid_pairs + MOD) % MOD
            
            assert output_values[j] == expected_ans_N2_i, \
                f"Incorrect value for N=2, i={current_i} (output index {j}) for K={K}, N={N}. " \
                f"Expected {expected_ans_N2_i}, got {output_values[j]}."