import random
import sys

def gen_input() -> str:
    # Determine n (length of sequence)
    # Prioritize boundary and interesting values for n
    rand_n_val = random.random()
    if rand_n_val < 0.05:
        n = 1  # Minimum n
    elif rand_n_val < 0.1:
        n = 2  # Small n
    elif rand_n_val < 0.15:
        n = random.randint(3, 10) # Very small n
    elif rand_n_val < 0.25:
        n = random.randint(11, 100) # Small to medium n
    elif rand_n_val < 0.4:
        n = random.randint(101, 500) # Medium n
    elif rand_n_val < 0.5:
        n = random.randint(501, 1000) # Medium to large n
    elif rand_n_val < 0.6:
        n = 2000 # Maximum n
    else:
        n = random.randint(1, 2000) # Wide random range

    arr = []
    # Generate array elements (1s and 2s) with various patterns
    pattern_choice = random.randint(0, 9)

    if pattern_choice == 0: # All 1s
        arr = [1] * n
    elif pattern_choice == 1: # All 2s
        arr = [2] * n
    elif pattern_choice == 2: # Alternating 1, 2, 1, 2...
        arr = [1 if i % 2 == 0 else 2 for i in range(n)]
    elif pattern_choice == 3: # Alternating 2, 1, 2, 1...
        arr = [2 if i % 2 == 0 else 1 for i in range(n)]
    elif pattern_choice == 4: # Many 1s then many 2s (already sorted non-decreasing)
        k = random.randint(0, n)
        arr = [1] * k + [2] * (n - k)
    elif pattern_choice == 5: # Many 2s then many 1s (reverse sorted non-decreasing, good for reversal)
        k = random.randint(0, n)
        arr = [2] * k + [1] * (n - k)
    elif pattern_choice == 6: # Mostly 1s, with a few 2s scattered
        arr = [1] * n
        num_twos = random.randint(0, min(n, n // 10 + 1))
        for _ in range(num_twos):
            arr[random.randint(0, n - 1)] = 2
    elif pattern_choice == 7: # Mostly 2s, with a few 1s scattered
        arr = [2] * n
        num_ones = random.randint(0, min(n, n // 10 + 1))
        for _ in range(num_ones):
            arr[random.randint(0, n - 1)] = 1
    elif pattern_choice == 8: # Single "peak" or "valley" type structure
        # e.g., 1s, then 2, then 1s (peak) or 2s, then 1, then 2s (valley)
        if n >= 3:
            mid = random.randint(1, n - 2)
            if random.random() < 0.5: # Peak (1...1 2 1...1)
                arr = [1] * n
                arr[mid] = 2
            else: # Valley (2...2 1 2...2)
                arr = [2] * n
                arr[mid] = 1
        else: # Fallback for very small n
            arr = [random.randint(1, 2) for _ in range(n)]
    else: # General random mix
        arr = [random.randint(1, 2) for _ in range(n)]

    # Mix in some random changes to make specific patterns less rigid, but not too much
    if pattern_choice < 6 and random.random() < 0.2: # 20% chance to introduce some noise to structured patterns
        for _ in range(random.randint(0, min(n // 5, 20))):
            if n > 0:
                idx = random.randint(0, n - 1)
                arr[idx] = 3 - arr[idx] # Flip 1 to 2, or 2 to 1

    # Final check for n=0 case, though problem states n >= 1
    if n == 0 and arr:
        n = len(arr)
    elif n > 0 and not arr: # Should not happen with above logic
        arr = [random.randint(1, 2) for _ in range(n)]

    return f"{n}\n{' '.join(map(str, arr))}\n"

def calculate_lnds_for_one_array(arr: list[int]) -> int:
    """
    Calculates the length of the longest non-decreasing subsequence (LNDS)
    for a given array consisting only of 1s and 2s.
    An LNDS in such an array is formed by some number of 1s followed by some number of 2s.
    The length is maximized by finding the optimal split point `i`
    where we count 1s in `arr[0...i-1]` and 2s in `arr[i...n-1]`.
    """
    n = len(arr)
    if n == 0:
        return 0

    # prefix_ones[j] = count of 1s in arr[0...j-1]
    # prefix_ones[0] is 0
    prefix_ones = [0] * (n + 1)
    for i in range(n):
        prefix_ones[i+1] = prefix_ones[i] + (1 if arr[i] == 1 else 0)

    # suffix_twos[j] = count of 2s in arr[j...n-1]
    # suffix_twos[n] is 0
    suffix_twos = [0] * (n + 1)
    for i in range(n - 1, -1, -1):
        suffix_twos[i] = suffix_twos[i+1] + (1 if arr[i] == 2 else 0)

    max_lnds = 0
    # Iterate through all possible split points `i` (0 to n)
    # `i` means we consider 1s from `arr[0...i-1]` and 2s from `arr[i...n-1]`
    for i in range(n + 1):
        current_lnds = prefix_ones[i] + suffix_twos[i]
        max_lnds = max(max_lnds, current_lnds)
    return max_lnds

def check(stdin: str, stdout: str) -> None:
    # 1. Parse stdin to get n and the original array
    lines = stdin.strip().split('\n')
    assert len(lines) == 2, f"Stdin should have 2 lines, got {len(lines)}"
    
    n = int(lines[0])
    original_arr_str = lines[1].split()
    original_arr = [int(x) for x in original_arr_str]

    # Basic input validation (should be guaranteed by gen_input, but good for robustness)
    assert 1 <= n <= 2000, f"N out of bounds: {n}"
    assert len(original_arr) == n, f"Array length {len(original_arr)} does not match n={n}"
    assert all(1 <= x <= 2 for x in original_arr), f"Array elements not 1 or 2: {original_arr}"

    # 2. Parse stdout to get the program's answer
    try:
        parsed_ans = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout}'")

    # 3. Assert properties the correct output must satisfy

    # Property 1: Output format and range
    # The length of a subsequence must be at least 1 (since n >= 1)
    # and cannot exceed the total number of elements n.
    assert 1 <= parsed_ans <= n, \
        f"Output {parsed_ans} not within expected range [1, {n}] for n={n}."

    # Property 2: The answer must be at least the LNDS of the original array.
    # This is because choosing an interval [l, r] such that l=r (or an "empty" reversal like l=1, r=0, though problem specifies 1<=l<=r<=n)
    # effectively means no change to the array. The optimal solution must be at least as good as the LNDS of the original array.
    min_possible_lnds_from_original = calculate_lnds_for_one_array(original_arr)
    assert parsed_ans >= min_possible_lnds_from_original, \
        f"Output {parsed_ans} is less than the LNDS of the original array ({min_possible_lnds_from_original})." \
        f"Original array: {original_arr}"