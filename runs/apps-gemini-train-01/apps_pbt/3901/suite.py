import random
import math

# Global list of primes, pre-generated for efficiency in gen_input.
# Primes up to 32000 are sufficient for generating numbers for N up to 2000
# using the p_i * p_{i+1} construction without exceeding 10^9 (e.g., 17000 * 17000 ~ 2.89e8).
_primes = []
_max_prime_limit = 32000

def _generate_primes_sieve(limit):
    """Generates primes up to a given limit using a sieve and populates _primes."""
    is_prime = [True] * (limit + 1)
    is_prime[0] = is_prime[1] = False
    for p in range(2, limit + 1):
        if is_prime[p]:
            _primes.append(p)
            for multiple in range(p * p, limit + 1, p):
                is_prime[multiple] = False

# Generate primes once when the module is loaded.
_generate_primes_sieve(_max_prime_limit)

def _calculate_gcd_of_array(arr):
    """Helper to calculate GCD of all elements in an array."""
    if not arr:
        return 0 # Should not happen based on problem constraints (N >= 1)
    result = arr[0]
    for i in range(1, len(arr)):
        result = math.gcd(result, arr[i])
        if result == 1:
            # Optimization: if GCD becomes 1, it will remain 1
            return 1
    return result

def gen_input() -> str:
    """
    Generates a random input string for the problem.
    Covers various edge cases and complex scenarios to stress test the solution.
    """
    n = 0
    a = []

    # Use a weighted random choice to prioritize certain test case types
    # (e.g., more general random cases, but also specific edge cases like all ones,
    # impossible cases, or cases that exercise the 'min_len' logic for no-ones).
    test_case_type = random.choices(
        [
            "N=1",
            "All_ones",
            "One_one_present",
            "Impossible_gcd_gt_1",
            "No_ones_min_len_2_coprime_pair",
            "No_ones_min_len_3_cyclic_primes", # Example: [p1*p2, p2*p3, p3*p1]
            "No_ones_min_len_N_cyclic_primes", # Example: [p1*p2, ..., p_N*p1]
            "Max_N_all_ones",
            "Max_N_one_one_present",
            "Max_N_impossible_gcd_gt_1",
            "Max_N_random_gcd_1",
            "Random_N_random_A" # General random case
        ],
        weights=[0.05, 0.05, 0.1, 0.1, 0.1, 0.1, 0.1, 0.05, 0.05, 0.05, 0.05, 0.2]
    )[0]

    if test_case_type == "N=1":
        n = 1
        a = [random.randint(1, 10**9)]
        if random.random() < 0.5: # Sometimes make it 1
            a[0] = 1
    elif test_case_type == "All_ones":
        n = random.randint(1, 2000)
        a = [1] * n
    elif test_case_type == "One_one_present":
        n = random.randint(2, 2000)
        a = [random.randint(2, 10**9) for _ in range(n)]
        a[random.randint(0, n - 1)] = 1
    elif test_case_type == "Impossible_gcd_gt_1":
        n = random.randint(1, 2000)
        # Choose a common factor, preferably a small prime or a composite number
        k = random.randint(2, _primes[min(len(_primes)-1, 100)] if _primes else 1000) 
        a = [random.randint(1, 10**9 // k) * k for _ in range(n)]
        a = [max(k, x) for x in a] # Ensure elements are at least k, not 0
    elif test_case_type == "No_ones_min_len_2_coprime_pair":
        n = random.randint(2, 2000)
        a = [random.randint(2, 10**9) for _ in range(n)]
        idx = random.randint(0, n - 2) # Index for the coprime pair
        
        # Select two distinct primes to guarantee their GCD is 1
        p1 = random.choice(_primes)
        p2 = random.choice(_primes)
        while p1 == p2: p2 = random.choice(_primes) 
        
        a[idx] = p1
        a[idx+1] = p2
        # Ensure no accidental 1s in the array
        for i in range(n):
            if a[i] == 1: a[i] = random.randint(2, 10**9)
            if a[i] < 2: a[i] = 2 # Ensure values are at least 2
    elif test_case_type == "No_ones_min_len_3_cyclic_primes":
        n = random.randint(3, 2000)
        a = [random.randint(2, 10**9) for _ in range(n)]
        idx = random.randint(0, n - 3) # Starting index for the triplet
        
        tries = 0
        while tries < 100: # Try to find suitable primes for p1*p2, p2*p3, p3*p1
            # Sample 3 distinct primes
            p_indices = random.sample(range(len(_primes)), 3)
            p1, p2, p3 = _primes[p_indices[0]], _primes[p_indices[1]], _primes[p_indices[2]]
            
            # Check for overflow
            if p1 * p2 <= 10**9 and p2 * p3 <= 10**9 and p3 * p1 <= 10**9:
                a[idx] = p1 * p2
                a[idx+1] = p2 * p3
                a[idx+2] = p3 * p1
                break
            tries += 1
        else: # Fallback to a fixed small example if suitable primes not found quickly
            a[idx] = 6   # 2*3
            a[idx+1] = 10 # 2*5
            a[idx+2] = 15 # 3*5
        
        # Ensure no accidental 1s in the array
        for i in range(n):
            if a[i] == 1: a[i] = random.randint(2, 10**9)
            if a[i] < 2: a[i] = 2 # Ensure values are at least 2

    elif test_case_type == "No_ones_min_len_N_cyclic_primes":
        # This case aims for 'min_len' (shortest subarray with GCD=1) to be the full array length N.
        # This is achieved by a_i = p_i * p_{i+1} with p_N = p_0 (cyclic product of N distinct primes).
        # We need at least N distinct primes. _primes has enough for N=2000.
        n = random.randint(2, min(len(_primes) - 1, 2000)) 
        a = []
        start_prime_idx = random.randint(0, len(_primes) - n - 1)
        possible = True
        for i in range(n):
            p1 = _primes[start_prime_idx + i]
            p2 = _primes[start_prime_idx + ((i + 1) % n)] # Cyclic index for p2
            
            val = p1 * p2
            if val > 10**9: # Check for overflow
                possible = False
                break
            a.append(val)
        
        if not possible: # Fallback if prime products are too large
            n = random.randint(2, 2000)
            a = [random.randint(2, 10**9) for _ in range(n)]
            # Ensure overall GCD is 1 for this fallback case
            if _calculate_gcd_of_array(a) > 1:
                a[random.randint(0, n-1)] = random.choice(_primes) # Replace with a prime
            # Ensure no 1s
            for i in range(n):
                if a[i] == 1: a[i] = random.randint(2, 10**9)
                if a[i] < 2: a[i] = 2 # Ensure values are at least 2
    
    elif test_case_type == "Max_N_all_ones":
        n = 2000
        a = [1] * n
    elif test_case_type == "Max_N_one_one_present":
        n = 2000
        a = [random.randint(2, 10**9) for _ in range(n)]
        a[random.randint(0, n - 1)] = 1
    elif test_case_type == "Max_N_impossible_gcd_gt_1":
        n = 2000
        k = random.randint(2, _primes[min(len(_primes)-1, 100)] if _primes else 1000)
        a = [random.randint(1, 10**9 // k) * k for _ in range(n)]
        a = [max(k, x) for x in a]
    elif test_case_type == "Max_N_random_gcd_1":
        n = 2000
        a = [random.randint(2, 10**9) for _ in range(n)]
        # Ensure overall GCD is 1 by introducing a prime (if array is not empty)
        if n > 0:
            a[random.randint(0, n - 1)] = random.choice(_primes)
    elif test_case_type == "Random_N_random_A": # General random case
        n = random.randint(1, 2000)
        a = [random.randint(1, 10**9) for _ in range(n)]

    input_str = f"{n}\n{' '.join(map(str, a))}\n"
    return input_str


def check(stdin: str, stdout: str) -> None:
    """
    Checks properties of the program's output without re-implementing the full solver.
    """
    # 1. Parse input from stdin string.
    lines = stdin.strip().split('\n')
    n = int(lines[0])
    a = list(map(int, lines[1].split()))

    # Basic input validation (ensures gen_input() provides valid data, and for robustness).
    assert 1 <= n <= 2000, f"Input N out of range: {n}"
    assert len(a) == n, f"Input array length mismatch. Expected {n}, got {len(a)}"
    assert all(1 <= x <= 10**9 for x in a), f"Input array elements out of range: {a}"

    # 2. Parse output from stdout string and perform basic format/range validation.
    try:
        ans = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout}'")

    # The maximum number of operations is 2*N-2.
    # (N-1 operations to create the first '1' from a 'min_len=N' subarray,
    # plus N-1 operations to convert the remaining N-1 elements using an existing '1').
    # For N=1, if a[0]=1, ans=0. If a[0]!=1, ans=-1. The upper bound 2*N-2 becomes 0 for N=1.
    if not (-1 <= ans <= 2 * n - 2):
        raise AssertionError(f"Output {ans} is out of expected range [-1, {2*n-2}] for N={n}")

    # 3. Property: If the Greatest Common Divisor (GCD) of all elements in the initial array
    # is greater than 1, it is impossible to make all elements 1.
    # This is because any operation (gcd(x, y)) results in a number that is a multiple of gcd(x, y).
    # If all initial numbers are multiples of G > 1, all subsequent numbers will also be multiples of G,
    # thus never reaching 1.
    global_gcd = _calculate_gcd_of_array(a)
    if global_gcd > 1:
        assert ans == -1, \
            f"Expected -1 because global GCD is {global_gcd} > 1, but got {ans}"

    # 4. Property: If there is already at least one '1' in the array, the minimum operations
    # needed is simply N - (count of 1s).
    # This is because each non-'1' element can be converted to '1' in exactly one operation
    # by applying gcd(X, 1) with an adjacent '1'. Since we want N ones, and we already have
    # 'num_ones' ones, we need to convert N - num_ones elements. Each costs one operation.
    num_ones = a.count(1)
    if num_ones > 0:
        expected_ans = n - num_ones
        assert ans == expected_ans, \
            f"Expected {expected_ans} operations because there are {num_ones} ones, but got {ans}"

    # 5. Property: If there are no '1's initially, but the global GCD is 1 (meaning it IS possible),
    # then the answer must be at least N.
    # This condition (num_ones == 0 and global_gcd == 1) implicitly means N > 1,
    # because if N=1 and a[0]!=1, then global_gcd would be a[0] > 1, covered by check 3.
    # The logic:
    #   - It takes 'min_len - 1' operations to create the first '1' in the array, where 'min_len'
    #     is the length of the shortest subarray whose GCD is 1. Since no '1's exist, min_len >= 2,
    #     so 'min_len - 1 >= 1'.
    #   - After creating the first '1', it takes 'N - 1' additional operations to convert the
    #     remaining 'N - 1' elements into '1's using the existing '1' (similar to check 4).
    #   - Total operations = (min_len - 1) + (N - 1).
    #   - Since (min_len - 1) >= 1, total operations >= 1 + (N - 1) = N.
    if num_ones == 0 and global_gcd == 1:
        assert ans >= n, \
            f"Expected at least {n} operations when no 1s initially (N={n}, GCD=1), but got {ans}"