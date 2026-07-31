import random
from collections import Counter
import re

def gen_input() -> str:
    # Max value for N and A_i from problem statement
    MAX_N = 100
    MAX_A_I = 300
    MAX_T = 10**7

    # Use weights for different test case types to emphasize crucial cases
    # For a problem like LIS/LNDS on periodic arrays, edge cases for N, T,
    # and properties of A (sorted, same elements, many duplicates) are important
    # for catching hidden divergences.
    test_case_type = random.choices(
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], # 11 different types
        weights=[5, 5, 10, 10, 10, 15, 5, 5, 10, 10, 10], # Weights
        k=1
    )[0]

    if test_case_type == 0: # Smallest N, T
        n = 1
        T = 1
        a = [random.randint(1, MAX_A_I)]
    elif test_case_type == 1: # N=1, large T
        n = 1
        T = random.randint(MAX_T // 2, MAX_T)
        a = [random.randint(1, MAX_A_I)]
    elif test_case_type == 2: # Small N (e.g. 2-5), large T
        n = random.randint(2, 5)
        T = random.randint(MAX_T // 2, MAX_T)
        a = [random.randint(1, MAX_A_I) for _ in range(n)]
    elif test_case_type == 3: # Large N (e.g. 50-100), small T (e.g. 1-5)
        n = random.randint(MAX_N // 2, MAX_N)
        T = random.randint(1, 5)
        a = [random.randint(1, MAX_A_I) for _ in range(n)]
    elif test_case_type == 4: # Medium N, medium T
        n = random.randint(MAX_N // 4, MAX_N * 3 // 4)
        T = random.randint(MAX_T // 100, MAX_T // 10)
        a = [random.randint(1, MAX_A_I) for _ in range(n)]
    elif test_case_type == 5: # All elements identical
        n = random.randint(1, MAX_N)
        T = random.randint(1, MAX_T)
        val = random.randint(1, MAX_A_I)
        a = [val] * n
    elif test_case_type == 6: # Sorted array (non-decreasing)
        n = random.randint(1, MAX_N)
        T = random.randint(1, MAX_T)
        temp_a = [random.randint(1, MAX_A_I) for _ in range(n)]
        a = sorted(temp_a)
    elif test_case_type == 7: # Reverse sorted array (non-increasing)
        n = random.randint(1, MAX_N)
        T = random.randint(1, MAX_T)
        temp_a = [random.randint(1, MAX_A_I) for _ in range(n)]
        a = sorted(temp_a, reverse=True)
    elif test_case_type == 8: # Many duplicates (small range of values)
        n = random.randint(1, MAX_N)
        T = random.randint(1, MAX_T)
        val_range = random.randint(1, 10) # values only from 1 to a small range (e.g., 1-10)
        a = [random.randint(1, val_range) for _ in range(n)]
    elif test_case_type == 9: # Values close to MAX_A_I
        n = random.randint(1, MAX_N)
        T = random.randint(1, MAX_T)
        a = [random.randint(MAX_A_I - 10, MAX_A_I) for _ in range(n)]
    else: # General random case (test_case_type == 10)
        n = random.randint(1, MAX_N)
        T = random.randint(1, MAX_T)
        a = [random.randint(1, MAX_A_I) for _ in range(n)]

    input_str = f"{n} {T}\n"
    input_str += " ".join(map(str, a)) + "\n"
    return input_str


def check(stdin: str, stdout: str) -> None:
    # 1. Parse input (n, T, a)
    lines = stdin.strip().split('\n')
    n, T = map(int, lines[0].split())
    a = list(map(int, lines[1].split()))

    # 2. Parse output (result)
    try:
        result = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout}'")

    # 3. Basic checks: Format/Range invariants
    # The length of a non-decreasing subsequence must be at least 1
    # (since the array is non-empty due to N >= 1) and at most n * T
    # (the total length of the conceptual array).
    assert 1 <= result <= n * T, \
        f"Output {result} is out of expected range [1, {n * T}] for n={n}, T={T}"

    # 4. Lower bound check: Maximum frequency of any element
    # A non-decreasing subsequence can always be formed by taking all occurrences
    # of the most frequent element.
    # The full periodic array consists of 'a' repeated T times.
    # So, first calculate frequencies of elements in the initial 'n' elements.
    counts_in_n = Counter(a)
    if not counts_in_n: # Should not happen based on constraints (1 <= n)
        max_freq_in_n = 0
    else:
        max_freq_in_n = max(counts_in_n.values())

    # The total count of the most frequent element in the n*T array is max_freq_in_n * T.
    lower_bound_by_freq = max_freq_in_n * T
    assert result >= lower_bound_by_freq, \
        (f"Output {result} is less than the maximum frequency lower bound "
         f"{lower_bound_by_freq} (max_freq_in_n={max_freq_in_n}, T={T})")

    # 5. Specific known case: All elements in 'a' are identical
    # If all elements in the initial array 'a' are the same (e.g., [5, 5, 5]),
    # then the full periodic array (e.g., [5, 5, 5, 5, 5, 5, ...]) is entirely non-decreasing.
    # In this specific case, the longest non-decreasing subsequence is the entire array itself.
    if len(set(a)) == 1:
        assert result == n * T, \
            f"Expected {n * T} for an array with all identical elements, but got {result}"

    # Metamorphic relations were considered but are not directly implementable within the
    # `check(stdin, stdout)` signature without an external harness for re-running the program.
    # The current checks cover basic invariants, bounds, and a strong known-answer case.