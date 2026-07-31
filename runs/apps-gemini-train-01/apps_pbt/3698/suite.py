import random
import math

# Precompute path lengths for numbers 1 to 1000.
# The maximum possible popcount for any number x < 2^1000 is 1000 (for 2^1000 - 1, which is 1000 ones).
# Therefore, all subsequent numbers in the reduction sequence (popcount(x), popcount(popcount(x)), etc.)
# will always be within the range [1, 1000].
# This precomputation allows us to find the `path_len` for any popcount value relevant to the problem.
_precomputed_path_lengths = {1: 0}
for i in range(2, 1001):
    _precomputed_path_lengths[i] = 1 + _precomputed_path_lengths[bin(i).count('1')]

# Determine the maximum possible `k` value for any number less than 2^1000.
# This corresponds to the maximum path length achievable starting from any number
# whose popcount is in the range [1, 1000].
# E.g., path_len(127) = 1 + path_len(popcount(127)) = 1 + path_len(7)
# = 1 + (1 + path_len(popcount(7))) = 1 + (1 + path_len(3))
# = 1 + (1 + (1 + path_len(popcount(3)))) = 1 + (1 + (1 + path_len(2)))
# = 1 + (1 + (1 + (1 + path_len(1)))) = 1 + 1 + 1 + 1 + 0 = 4.
# After inspecting the precomputed values, the maximum is indeed 4.
MAX_K_FOR_ANY_N = max(_precomputed_path_lengths.values())

def gen_input() -> str:
    # Randomly choose length for n (up to 1000 bits).
    # Prioritize smaller lengths for more targeted testing, but also cover large lengths.
    n_len = random.choices(
        [1, 2, 3, 4, 10, 100, 500, 999, 1000], 
        weights=[3, 3, 3, 3, 2, 2, 2, 2, 2]
    )[0]
    if random.random() < 0.8: # Most of the time, pick a truly random length
        n_len = random.randint(1, 1000)

    # Generate n (binary string)
    n_str = "1" # n must start with '1' and be positive
    if n_len > 1:
        choice_type = random.random()
        if choice_type < 0.15: # All ones (e.g., "111")
            n_str = "1" * n_len
        elif choice_type < 0.3: # Smallest for its length (e.g., "100")
            n_str = "1" + "0" * (n_len - 1)
        else: # Random bits
            n_str += "".join(random.choices("01", k=n_len - 1))
    
    # Generate k (0 <= k <= 1000)
    k = random.randint(0, 1000)
    
    # Prioritize boundary and interesting k values
    if random.random() < 0.2:
        k = random.choices(
            [0, 1, 2, 3, 4, 5, MAX_K_FOR_ANY_N, MAX_K_FOR_ANY_N + 1, 1000],
            weights=[10, 10, 5, 3, 2, 1, 1, 1, 1]
        )[0]
    
    return f"{n_str}\n{k}\n"

def check(stdin: str, stdout: str) -> None:
    lines = stdin.strip().split('\n')
    n_str = lines[0]
    k = int(lines[1])

    # --- Property 1: Output format and range ---
    # The output must be a single integer, non-negative, and within the modulo range.
    try:
        output_val = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout}'")

    MOD = 10**9 + 7
    assert 0 <= output_val < MOD, \
        f"Output value {output_val} out of expected range [0, {MOD-1}] (modulo operation expected)"

    # --- Property 2: k = 0 ---
    # If k = 0, a number `x` is special if it takes 0 operations to reduce to 1.
    # This only happens if `x = 1`.
    # Since `n` is always >= 1, `x = 1` is always a candidate number.
    # Therefore, the count of special numbers not greater than `n` must be exactly 1.
    if k == 0:
        assert output_val == 1, f"Expected 1 for k=0 (n='{n_str}'), got {output_val}"

    # --- Property 3: k = 1 ---
    # If k = 1, a number `x` is special if `popcount(x) = 1` and `x > 1` (since `path_len(1)=0`).
    # This means `x` must be a power of 2, i.e., `x = 2^p` for `p >= 1`.
    # The count of such numbers `x` not greater than `n` is `floor(log2(n))`.
    # - If `n = 1` ("1"), `floor(log2(1))` is 0.
    # - If `n > 1`, `len(n_str) - 1` is exactly `floor(log2(n))`.
    #   (e.g., for `n="110"` (6_10), `len=3`, `floor(log2(6))=2`. Powers of 2 are 2^1, 2^2. Count=2.)
    if k == 1:
        if n_str == "1":
            expected_count_k1 = 0
        else:
            expected_count_k1 = len(n_str) - 1
        assert output_val == expected_count_k1, \
            f"Expected {expected_count_k1} for k=1 and n='{n_str}', got {output_val}"
            
    # --- Property 4: k is too large for any number < 2^1000 to be special ---
    # As analyzed, the maximum possible path length for any positive integer `x`
    # (where `x` is restricted to be less than `2^1000`) is 4. This occurs for numbers
    # like 127. If `k` is greater than 4, no number `x` can satisfy the `k` operations
    # requirement.
    if k > MAX_K_FOR_ANY_N: # MAX_K_FOR_ANY_N is 4
        assert output_val == 0, \
            f"Expected 0 for k={k} and n='{n_str}' (max possible k for any n < 2^1000 is {MAX_K_FOR_ANY_N}), got {output_val}"

    # --- Property 5: Special handling for n="1" ---
    # If `n` is "1", the only number to consider is `x=1`.
    # - If `k=0`, `x=1` is special (takes 0 ops to reduce to 1). Count is 1.
    # - If `k>0`, `x=1` is NOT special (path_len(1)=0 != k). Count is 0.
    # This property partially overlaps with P2 and P3, but being explicit for n="1" is robust.
    if n_str == "1":
        if k == 0:
            assert output_val == 1, f"Expected 1 for n='1', k=0, got {output_val}"
        else: # k > 0
            assert output_val == 0, f"Expected 0 for n='1', k={k} (k!=0), got {output_val}"