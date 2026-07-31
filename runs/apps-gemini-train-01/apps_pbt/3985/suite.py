import random

# Helper function for check, not part of the main solution logic
# Computes the total number of prime factors of a number, with multiplicity.
# E.g., get_prime_factors_count(12) = 3 (factors are 2, 2, 3)
def get_prime_factors_count(num: int) -> int:
    if num <= 1:
        return 0
    count = 0
    d = 2
    temp = num
    while d * d <= temp:
        while temp % d == 0:
            count += 1
            temp //= d
        d += 1
    if temp > 1:  # remaining factor is prime
        count += 1
    return count

def gen_input() -> str:
    # --- Generate n and m (array size and number of good pairs) ---
    n_choice = random.randint(0, 4)
    if n_choice == 0: n = 2  # Minimum n
    elif n_choice == 1: n = random.randint(3, 5)  # Small n
    elif n_choice == 2: n = random.randint(6, 20)  # Medium n
    elif n_choice == 3: n = random.randint(21, 99) # Large n
    else: n = 100 # Maximum n

    m_choice = random.randint(0, 4)
    if m_choice == 0: m = 1  # Minimum m
    elif m_choice == 1: m = random.randint(2, 5)  # Small m
    elif m_choice == 2: m = random.randint(6, 20)  # Medium m
    elif m_choice == 3: m = random.randint(21, 99) # Large m
    else: m = 100 # Maximum m

    # --- Generate array a ---
    a = []
    a_type_choice = random.random()
    if a_type_choice < 0.02: # 2% chance for all 1s
        a = [1] * n
    elif a_type_choice < 0.04: # 2% chance for all powers of 2 (values > 1)
        for _ in range(n):
            a.append(1 << random.randint(1, 29)) # 2^1 to 2^29 (max 2^29 is < 10^9)
    elif a_type_choice < 0.06: # 2% chance for all identical large composite numbers
        val = random.randint(10**8, 10**9)
        if val == 1: val = random.randint(2, 10**9) # Ensure not 1 if random.randint chose 1
        a = [val] * n
    else: # General random mix of numbers
        for _ in range(n):
            val_choice = random.randint(0, 5)
            if val_choice == 0: # Small value
                a.append(random.randint(1, 10))
            elif val_choice == 1: # Large value
                a.append(random.randint(10**8, 10**9))
            elif val_choice == 2: # Power of 2 (could be 1 if exponent is 0)
                a.append(1 << random.randint(0, 29))
            elif val_choice == 3: # Number with a specific small prime factor
                # Choose a small prime, then multiply by a random number to stay within 10^9
                p = random.choice([2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97])
                max_multiplier = 10**9 // p
                multiplier = random.randint(1, max_multiplier)
                a.append(p * multiplier)
                # Ensure it's not 0 (not possible given randint(1, max_multiplier))
                # or 1 (only possible if p=1, which is not in our list, or multiplier was 1/p, not possible)
            elif val_choice == 4: # Value 1
                a.append(1)
            else: # General random value
                a.append(random.randint(1, 10**9))
    
    # --- Generate good pairs ---
    good_pairs = set()
    all_possible_pairs = []
    for i in range(1, n + 1):
        for j in range(i + 1, n + 1):
            if (i + j) % 2 == 1: # i+j is odd means one index is odd, the other is even
                all_possible_pairs.append((i, j))
    
    num_possible_pairs = len(all_possible_pairs)
    # m_actual caps m by the total number of valid pairs for the current n
    m_actual = min(m, num_possible_pairs) 

    if m_actual > 0:
        if random.random() < 0.05 and num_possible_pairs > 0: # 5% chance to use all possible pairs
            good_pairs.update(all_possible_pairs)
            m_actual = num_possible_pairs
        else: # Randomly sample m_actual pairs
            good_pairs_list = random.sample(all_possible_pairs, m_actual)
            good_pairs.update(good_pairs_list)
    # Note: For n >= 2, there is always at least one possible good pair (1,2).
    # Since m >= 1, m_actual will always be >= 1.

    # --- Construct input string ---
    input_str = f"{n} {m_actual}\n"
    input_str += " ".join(map(str, a)) + "\n"
    # Sort good pairs for consistent test case order (helpful for debugging failing tests)
    for i, j in sorted(list(good_pairs)): 
        input_str += f"{i} {j}\n"
    
    return input_str

def check(stdin: str, stdout: str) -> None:
    # --- Parse stdin to extract n, m, and the array a ---
    lines = stdin.strip().split('\n')
    n_str, m_str = lines[0].split()
    n = int(n_str)
    m = int(m_str)
    a_str = list(map(int, lines[1].split()))
    
    # --- Parse stdout and perform basic format validation ---
    try:
        ans = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout}'")

    # --- Property 1: The answer must be non-negative ---
    # The number of operations cannot be negative.
    assert ans >= 0, f"Answer must be non-negative, but got {ans}"

    # --- Property 2: The answer must not exceed the total number of prime factors across all a[i] ---
    # Each operation removes one prime factor (with multiplicity) from *two* numbers.
    # Therefore, the total number of operations can never be more than the sum of all prime factors
    # (with multiplicity) present in the initial array a. This is a sound upper bound.
    total_omega = 0
    for x in a_str:
        total_omega += get_prime_factors_count(x)
    
    assert ans <= total_omega, \
        f"Answer {ans} exceeds maximum possible operations. Total prime factors available in array: {total_omega}"

    # --- Property 3: If m=0 (no good pairs), the answer must be 0 ---
    # If there are no good pairs specified, no operations can ever be performed.
    if m == 0:
        assert ans == 0, f"If m=0 (no good pairs), answer must be 0, but got {ans}"
    
    # --- Property 4: If all a[i] are 1, the answer must be 0 ---
    # If all numbers in the array are 1, they have no prime factors greater than 1,
    # so no 'v > 1' exists to divide them. Thus, no operations can be performed.
    if all(x == 1 for x in a_str):
        assert ans == 0, f"If all a[i] are 1, answer must be 0, but got {ans}"