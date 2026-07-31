import random

def gen_input() -> str:
    """
    Generates a valid test input string for the problem.
    Covers various edge cases and random scenarios for N, K, Q, and array A.
    """
    
    # Define categories of test cases to ensure broad coverage
    case_types = [
        "min_N_K_Q",                  # N=1, K=1, Q=1
        "N_eq_K_Q_eq_1",              # N=K, Q=1 (large N possible)
        "small_N_K_Q",                # Small N, K, Q with random A_i
        "large_N_K_Q_K1",             # N=max, K=1, Q=max (tests K=1 property extensively)
        "large_N_K_Q1",               # N=max, K=random, Q=1 (tests Q=1 property extensively)
        "large_N_K_Q_random",         # N=max, K=random, Q=random
        "all_ones_A",                 # All A_i = 1
        "all_max_val_A",              # All A_i = 10^9
        "sorted_asc_A",               # A is sorted ascending
        "sorted_desc_A",              # A is sorted descending
        "many_duplicates_small_range",# A with few unique values in small range
        "many_duplicates_large_range",# A with few unique values in large range
        "random_values_wide_range",   # A with values across full 1 to 10^9 range
        "random_values_small_range_low", # A with values 1 to 1000
        "random_values_small_range_high",# A with values 10^9-1000 to 10^9
    ]

    choice = random.choice(case_types)

    N, K, Q = 0, 0, 0
    A = []

    if choice == "min_N_K_Q":
        N, K, Q = 1, 1, 1
        A = [random.randint(1, 10**9)]
    elif choice == "N_eq_K_Q_eq_1":
        N = random.randint(2, 2000)
        K = N
        Q = 1
        A = [random.randint(1, 10**9) for _ in range(N)]
    elif choice == "small_N_K_Q":
        N = random.randint(2, 10)
        K = random.randint(1, N)
        Q = random.randint(1, N - K + 1)
        A = [random.randint(1, 100) for _ in range(N)]
    elif choice == "large_N_K_Q_K1":
        N = 2000
        K = 1
        Q = N # Max Q for K=1
        A = [random.randint(1, 10**9) for _ in range(N)]
    elif choice == "large_N_K_Q1":
        N = 2000
        K = random.randint(1, N)
        Q = 1
        A = [random.randint(1, 10**9) for _ in range(N)]
    elif choice == "large_N_K_Q_random":
        N = 2000
        K = random.randint(1, N)
        Q = random.randint(1, N - K + 1)
        A = [random.randint(1, 10**9) for _ in range(N)]
    elif choice == "all_ones_A":
        N = random.randint(1, 2000)
        K = random.randint(1, N)
        Q = random.randint(1, N - K + 1)
        A = [1] * N
    elif choice == "all_max_val_A":
        N = random.randint(1, 2000)
        K = random.randint(1, N)
        Q = random.randint(1, N - K + 1)
        A = [10**9] * N
    elif choice == "sorted_asc_A":
        N = random.randint(1, 2000)
        K = random.randint(1, N)
        Q = random.randint(1, N - K + 1)
        # Ensure values are distinct but don't exceed 10^9
        base = random.randint(1, 10**9 - N)
        A = sorted([base + i for i in range(N)])
    elif choice == "sorted_desc_A":
        N = random.randint(1, 2000)
        K = random.randint(1, N)
        Q = random.randint(1, N - K + 1)
        base = random.randint(1, 10**9 - N)
        A = sorted([base + i for i in range(N)], reverse=True)
    elif choice == "many_duplicates_small_range":
        N = random.randint(10, 2000)
        K = random.randint(1, N)
        Q = random.randint(1, N - K + 1)
        unique_vals = [random.randint(1, 10) for _ in range(random.randint(2, min(N, 5)))]
        A = [random.choice(unique_vals) for _ in range(N)]
        random.shuffle(A)
    elif choice == "many_duplicates_large_range":
        N = random.randint(10, 2000)
        K = random.randint(1, N)
        Q = random.randint(1, N - K + 1)
        unique_vals = [random.randint(1, 10**9) for _ in range(random.randint(2, min(N, 5)))]
        A = [random.choice(unique_vals) for _ in range(N)]
        random.shuffle(A)
    elif choice == "random_values_wide_range":
        N = random.randint(1, 2000)
        K = random.randint(1, N)
        Q = random.randint(1, N - K + 1)
        A = [random.randint(1, 10**9) for _ in range(N)]
    elif choice == "random_values_small_range_low":
        N = random.randint(1, 2000)
        K = random.randint(1, N)
        Q = random.randint(1, N - K + 1)
        A = [random.randint(1, 1000) for _ in range(N)]
    elif choice == "random_values_small_range_high":
        N = random.randint(1, 2000)
        K = random.randint(1, N)
        Q = random.randint(1, N - K + 1)
        A = [random.randint(10**9 - 1000, 10**9) for _ in range(N)]
    
    # Ensure N, K, Q are correctly set in case a choice didn't fully initialize them
    if N == 0: # Fallback for robustness, though should be covered
        N = random.randint(1, 2000)
        K = random.randint(1, N)
        Q = random.randint(1, N - K + 1)
        A = [random.randint(1, 10**9) for _ in range(N)]

    input_str = f"{N} {K} {Q}\n" + " ".join(map(str, A)) + "\n"
    return input_str


def check(stdin: str, stdout: str) -> None:
    """
    Verifies properties of the program's output without re-implementing the core logic.
    Focuses on output format, basic range, and strong properties for specific edge cases.
    """

    # 1. Parse input
    lines = stdin.strip().split('\n')
    N, K, Q = map(int, lines[0].split())
    A = list(map(int, lines[1].split()))

    # 2. Parse output
    try:
        result = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout}'")

    # 3. Property: Output must be non-negative
    assert result >= 0, f"Result {result} is negative, but X-Y must be non-negative."

    # 4. Property: Output must be within a reasonable upper bound
    # The maximum possible difference is max(A_i) - min(A_i) = 10^9 - 1.
    assert result <= 10**9 - 1, f"Result {result} exceeds max possible difference (10^9-1)."

    # 5. Property: Special case Q=1
    # If only one operation is performed, the largest removed element (X) and the smallest
    # removed element (Y) are the same value. Thus, X-Y must be 0.
    if Q == 1:
        assert result == 0, \
            f"For Q=1, X-Y must be 0, but got {result}. Input: {stdin.strip()}"

    # 6. Property: Special case K=1
    # If K=1, each chosen contiguous subsequence has length 1, i.e., [A_i].
    # The smallest element in such a subsequence is A_i itself.
    # So, Q operations consist of choosing Q elements from A and removing them.
    # The goal is to minimize max(chosen_A_i) - min(chosen_A_i).
    # This can be found by sorting A and taking a sliding window of size Q.
    if K == 1:
        sorted_A = sorted(A)
        min_diff_K1 = float('inf')
        # Iterate through all possible contiguous subsegments of length Q in the sorted array
        for i in range(N - Q + 1):
            current_diff = sorted_A[i + Q - 1] - sorted_A[i]
            min_diff_K1 = min(min_diff_K1, current_diff)
        
        assert result == min_diff_K1, \
            f"For K=1, expected {min_diff_K1}, got {result}. Input: {stdin.strip()}"