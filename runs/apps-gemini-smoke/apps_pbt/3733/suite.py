import random
import math
import collections

def gen_input() -> str:
    n = random.randint(1, 4 * 10**5)
    I_bytes = random.randint(1, 10**8)

    a = []
    # Cover various data distributions for 'a'
    # 1. All values are the same
    if random.random() < 0.03:
        val = random.randint(0, 10**9)
        a = [val] * n
    # 2. All values are distinct
    elif random.random() < 0.03:
        # Generate random distinct values up to n
        unique_vals = set()
        while len(unique_vals) < n:
            unique_vals.add(random.randint(0, 10**9))
        a = list(unique_vals)
        random.shuffle(a)
    # 3. Few distinct values, high frequency for some
    elif random.random() < 0.05:
        num_distinct = random.randint(1, min(n, 100)) # Up to 100 distinct values
        distinct_vals = random.sample(range(0, 10**9), num_distinct)
        a = [random.choice(distinct_vals) for _ in range(n)]
    # 4. Values in a very small contiguous range
    elif random.random() < 0.05:
        start_val = random.randint(0, 10**9 - 200)
        end_val = start_val + random.randint(0, 200) # Range of up to 200 values
        a = [random.randint(start_val, end_val) for _ in range(n)]
    # 5. Values with some small and some large outliers
    elif random.random() < 0.03:
        small_val = random.randint(0, 100)
        large_val = random.randint(10**9 - 100, 10**9)
        # Most values are clustered, some are outliers
        if n > 2:
            a = [random.choice([small_val, large_val, random.randint(small_val+1, large_val-1)]) for _ in range(n-2)]
            a.append(small_val)
            a.append(large_val)
        else: # Handle small n
            a = [random.randint(0, 10**9) for _ in range(n)]
    # 6. Values that are already sorted or nearly sorted
    elif random.random() < 0.03:
        temp_a = [random.randint(0, 10**9) for _ in range(n)]
        temp_a.sort()
        a = temp_a
        # Add a few perturbations to make it "nearly" sorted
        for _ in range(min(n // 10, 10)):
            idx1, idx2 = random.sample(range(n), 2)
            a[idx1], a[idx2] = a[idx2], a[idx1]
    # 7. Default: wide range of random values
    else:
        a = [random.randint(0, 10**9) for _ in range(n)]

    # Specific cases for N and I boundaries
    # Min N (1)
    if random.random() < 0.01:
        n = 1
        a = [random.randint(0, 10**9)]
    # Max N (4e5)
    if random.random() < 0.01:
        n = 4 * 10**5
        # Ensure a plausible scenario for max N
        if random.random() < 0.5: # Many distinct values
            a = [i for i in range(n)]
        else: # Few distinct values
            distinct_count = random.randint(1, 5)
            distinct_vals = random.sample(range(0, 10**9), distinct_count)
            a = [random.choice(distinct_vals) for _ in range(n)]

    # Min I (1 byte)
    if random.random() < 0.01:
        I_bytes = 1
        # This often forces K=1, especially for large n
    # Max I (10^8 bytes)
    if random.random() < 0.01:
        I_bytes = 10**8
        # This often means 0 changes are needed for typical N

    # Special case: force K=1 scenario (max_k_bits_per_val = 0)
    # This happens when I_bytes * 8 / n < 1, i.e., I_bytes * 8 < n
    if random.random() < 0.02 and n > 8: # Need n large enough for I_bytes to be at least 1
        I_bytes = random.randint(1, math.ceil(n / 8) - 1)
        if I_bytes == 0: I_bytes = 1 # Minimum I is 1

    # Include provided examples occasionally for sanity
    if random.random() < 0.001:
        return '6 1\n2 1 2 3 4 3\n'
    if random.random() < 0.001:
        return '6 2\n2 1 2 3 4 3\n'
    if random.random() < 0.001:
        return '6 1\n1 1 2 2 3 3\n'

    input_str = f"{n} {I_bytes}\n"
    input_str += " ".join(map(str, a)) + "\n"
    return input_str

def check(stdin: str, stdout: str) -> None:
    lines = stdin.strip().split('\n')
    n, I_bytes = map(int, lines[0].split())
    a = list(map(int, lines[1].split()))

    # 1. Output Format & Range check
    try:
        parsed_output = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output '{stdout.strip()}' is not a valid integer.")
    
    # The number of changed elements must be between 0 and n.
    if not (0 <= parsed_output <= n):
        raise AssertionError(f"Parsed output {parsed_output} is out of range [0, {n}].")

    # Helper function to calculate k bits for K distinct values
    def get_k_bits(K: int) -> int:
        if K == 0: # Problem constraints imply K >= 1
            return 0
        if K == 1:
            return 0
        return math.ceil(math.log2(K))

    # 2. Feasibility of 0 changes check:
    # If the initial array (before any compression) already fits the disk,
    # then the optimal number of changes must be 0.
    distinct_initial = set(a)
    K_initial = len(distinct_initial)
    
    k_initial_bits = get_k_bits(K_initial)
    initial_memory_bits = n * k_initial_bits
    
    if initial_memory_bits <= I_bytes * 8:
        if parsed_output != 0:
            raise AssertionError(
                f"Initial array already fits ({initial_memory_bits} bits <= {I_bytes*8} bits), "
                f"but program output {parsed_output} changes instead of 0."
            )
    else: # initial_memory_bits > I_bytes * 8
        # If the initial array does NOT fit, then the answer MUST be greater than 0.
        if parsed_output == 0:
            raise AssertionError(
                f"Initial array does NOT fit ({initial_memory_bits} bits > {I_bytes*8} bits), "
                f"but program output 0 changes."
            )

    # 3. Special case check: If only 1 distinct value is allowed (max_K_allowed = 1)
    # In this scenario, we can precisely calculate the minimal changes.
    
    # Calculate the maximum number of bits per value (k) allowed by the disk size
    max_k_bits_per_val = 0
    if n > 0: # n is guaranteed to be >= 1 by constraints
        max_k_bits_per_val = math.floor((I_bytes * 8) / n)
    
    # Calculate the maximum number of distinct values (K) that can be stored
    # If max_k_bits_per_val is 0, it means only K=1 is allowed (since K=1 costs 0 bits)
    # Otherwise, K can be up to 2^max_k_bits_per_val
    max_K_allowed = 1 if max_k_bits_per_val == 0 else (1 << max_k_bits_per_val)

    if max_K_allowed == 1:
        # If only one distinct value is allowed, the optimal strategy is to change all
        # elements to the most frequent value in the original array `a`.
        # The number of changes will be `n - (frequency of the most frequent value)`.
        counts = collections.Counter(a)
        
        # In case 'a' is empty, max_frequent_count would be 0, but n>=1 here.
        if not counts: 
            most_frequent_count = 0 
        else:
            most_frequent_count = max(counts.values())
        
        expected_changes_for_K1 = n - most_frequent_count
        
        if parsed_output != expected_changes_for_K1:
            raise AssertionError(
                f"When only 1 distinct value is allowed (max_K_allowed={max_K_allowed}), "
                f"expected changes {expected_changes_for_K1}, but program output {parsed_output}."
            )