import random
import math

def _get_places_base7(val):
    """
    Helper to calculate the minimum number of places necessary to display a given value
    in base 7. This is used to determine k_h (for 0 to n-1) and k_m (for 0 to m-1).
    
    As per the problem statement:
    - To display number 0, at least one place is required.
    - For any positive integer X, it requires k places if 7^(k-1) <= X < 7^k.
      This is equivalent to k-1 <= log_7(X) < k, so k = floor(log_7(X)) + 1.
    """
    if val < 0:
        raise ValueError("Value cannot be negative for places calculation")
    if val == 0:
        return 1
    return math.floor(math.log(val, 7)) + 1

def gen_input() -> str:
    n, m = 0, 0
    choice = random.randint(0, 15) # Diversify input generation strategies

    if choice == 0: # Smallest possible n, m
        n, m = 1, 1
    elif choice == 1: # Example 1 from problem statement
        n, m = 2, 3
    elif choice == 2: # Example 2 from problem statement
        n, m = 8, 2
    elif choice == 3: # n, m small random (1 to 10)
        n = random.randint(1, 10)
        m = random.randint(1, 10)
    elif choice == 4: # n, m medium random (1 to ~7^3 = 343)
        n = random.randint(1, 350)
        m = random.randint(1, 350)
    elif choice == 5: # One of n or m is small, the other is large
        n = random.randint(1, 10)
        m = random.randint(1, 10**9)
        if random.random() < 0.5: # Randomly swap n and m
            n, m = m, n
    elif choice == 6: # n or m is 1 (corner case for _get_places_base7(0))
        n = 1
        m = random.randint(1, 10**9)
        if random.random() < 0.5:
            n, m = m, n
    elif choice == 7: # n or m is around 7^k (boundary for number of digits)
        pow_k = random.randint(1, 10) # Powers of 7 from 7^1 to 7^10
        base_val = 7**pow_k
        
        # Test values slightly below, at, and slightly above 7^k
        n_candidates = [base_val, base_val - 1, base_val + 1]
        m_candidates = [base_val, base_val - 1, base_val + 1]
        
        # Filter candidates to be within [1, 10^9] and add general randoms for variety
        n_options = [c for c in n_candidates if 1 <= c <= 10**9] + [random.randint(1, 10**9)]
        m_options = [c for c in m_candidates if 1 <= c <= 10**9] + [random.randint(1, 10**9)]
        
        n = random.choice(n_options)
        m = random.choice(m_options)
        
        # Ensure final values are strictly within problem constraints
        n = max(1, min(n, 10**9))
        m = max(1, min(m, 10**9))
    elif choice == 8: # n, m large random (up to 10^9)
        n = random.randint(1, 10**9)
        m = random.randint(1, 10**9)
    elif choice == 9: # N, M such that k_h + k_m = 7 (maximum non-zero count)
        # Goal: total places sum to 7, e.g., k_h=3, k_m=4.
        kh_target = random.randint(1, 6) # k_h can be 1 to 6
        km_target = 7 - kh_target        # k_m will be 7 - k_h
        
        # Calculate appropriate n, m ranges to achieve these k_h, k_m values
        n_lower_bound = (7**(kh_target - 1)) + 1 if kh_target > 1 else 1
        n_upper_bound = 7**kh_target
        
        m_lower_bound = (7**(km_target - 1)) + 1 if km_target > 1 else 1
        m_upper_bound = 7**km_target

        n = random.randint(n_lower_bound, n_upper_bound)
        m = random.randint(m_lower_bound, m_upper_bound)

        # Cap at 10^9 and ensure >= 1
        n = min(n, 10**9)
        m = min(m, 10**9)
        n = max(1, n)
        m = max(1, m)
    elif choice == 10: # N, M such that k_h + k_m > 7 (expected R=0)
        # Goal: total places sum to > 7, e.g., k_h=4, k_m=4 (sum=8).
        # We ensure n and m individually require a certain minimum number of digits.
        # Max k for 10^9 is 11.
        kh_min_req = random.randint(4, 7) # Minimum k_h to make sum > 7 (e.g. if km_min_req is 1, kh_min_req needs to be 7)
        km_min_req = random.randint(4, 7) # Similarly for k_m
        
        n_lower_bound = (7**(kh_min_req - 1)) + 1 if kh_min_req > 1 else 1
        m_lower_bound = (7**(km_min_req - 1)) + 1 if km_min_req > 1 else 1
        
        n = random.randint(n_lower_bound, 10**9)
        m = random.randint(m_lower_bound, 10**9)
        
        # Ensure n, m are clamped.
        n = max(1, min(n, 10**9))
        m = max(1, min(m, 10**9))
        
        # If the generated values don't happen to force k_h + k_m > 7, try again more aggressively.
        if _get_places_base7(n-1) + _get_places_base7(m-1) <= 7:
            n = random.randint(7**5 + 1, 10**9) # Forces k_h >= 6
            m = random.randint(7**2 + 1, 10**9) # Forces k_m >= 3, resulting in sum >= 9.
            n = max(1, n)
            m = max(1, m)
    elif choice == 11: # Both n and m are maximal (10^9)
        n, m = 10**9, 10**9
    elif choice == 12: # One maximal, one small
        n = 10**9
        m = random.randint(1, 100)
        if random.random() < 0.5:
            n, m = m, n
    elif choice == 13: # n just below a 7^k, m just above a 7^k (tests digit count transitions)
        k_val = random.randint(2, 10) # Needs k_val >= 2 for meaningful "below"
        n = min(10**9, 7**k_val - 1)
        if n < 1: n = 1 # Ensure n is at least 1
        m = min(10**9, 7**k_val + 1)
        if m < 1: m = 1 # Ensure m is at least 1
        if random.random() < 0.5: n, m = m, n # Swap roles
    elif choice == 14: # n, m near boundary points of powers of 7
        powers_of_7 = [7**k for k in range(1, 11)]
        n_base = random.choice(powers_of_7)
        m_base = random.choice(powers_of_7)
        
        n = random.randint(max(1, n_base - 5), min(10**9, n_base + 5))
        m = random.randint(max(1, m_base - 5), min(10**9, m_base + 5))
        n = max(1, min(n, 10**9))
        m = max(1, min(m, 10**9))
    else: # Default: Wide random range if other choices not explicitly handled
        n = random.randint(1, 10**9)
        m = random.randint(1, 10**9)

    return f"{n} {m}\n"


def check(stdin: str, stdout: str) -> None:
    # 1. Parse Input (n, m) from stdin
    try:
        n_str, m_str = stdin.strip().split()
        n = int(n_str)
        m = int(m_str)
        # Input constraints: 1 <= n, m <= 10^9
        assert 1 <= n <= 10**9 and 1 <= m <= 10**9, f"Input n={n}, m={m} violates constraints."
    except Exception as e:
        raise AssertionError(f"Failed to parse stdin '{stdin.strip()}': {e}")

    # 2. Parse Output (R) from stdout
    try:
        R = int(stdout.strip())
    except Exception as e:
        raise AssertionError(f"Failed to parse stdout '{stdout.strip()}' as an integer: {e}")

    # 3. Basic Format and Range Check for R
    assert R >= 0, f"Output R must be non-negative, but got {R} for n={n}, m={m}."

    # 4. Calculate k_h and k_m based on problem definition
    # k_h is the number of places needed to display any integer from 0 to n-1.
    # k_m is the number of places needed to display any integer from 0 to m-1.
    k_h = _get_places_base7(n - 1)
    k_m = _get_places_base7(m - 1)

    # Property 1: If the total number of places required (k_h + k_m) is greater than 7,
    # it is impossible to have all distinct digits, because base 7 only has 7 unique digits (0-6).
    # In such a scenario, the count of valid moments of time (R) must be 0.
    if k_h + k_m > 7:
        assert R == 0, \
            f"Expected R=0 because k_h ({k_h}) + k_m ({k_m}) > 7. Got {R} for n={n}, m={m}."
            
    # Property 2: The number of distinct pairs (R) cannot exceed the total possible pairs (n * m).
    # This is a very loose but fundamentally true upper bound.
    assert R <= n * m, \
        f"R ({R}) cannot be greater than n * m ({n*m}) for n={n}, m={m}."
        
    # Property 3: A tighter upper bound for R.
    # The maximum number of distinct digit sequences possible with `total_places` digits
    # chosen from 7 unique base-7 digits (0-6) is P(7, total_places).
    # Each valid (hour, minute) pair corresponds to such a unique distinct digit sequence.
    # Therefore, R cannot exceed this number of permutations.
    max_digit_permutations = 1
    total_places = k_h + k_m
    if total_places <= 7:
        for i in range(total_places):
            max_digit_permutations *= (7 - i)
    else:
        # If total_places > 7, it's impossible to have distinct digits.
        # This case should already be caught by Property 1, but this provides a consistent upper bound.
        max_digit_permutations = 0 
            
    assert R <= max_digit_permutations, \
        f"R ({R}) cannot exceed P(7, k_h+k_m) ({max_digit_permutations}) " \
        f"where k_h={k_h}, k_m={k_m} for n={n}, m={m}."

    # Property 4: Specific edge case for (n=1, m=1).
    # For n=1, hour is 0. For m=1, minute is 0.
    # The time is (0:0). In base 7, these are "0" and "0".
    # The digits displayed are '0' and '0', which are not distinct.
    # Thus, R must be 0 for this input.
    if n == 1 and m == 1:
        assert R == 0, f"For n=1, m=1, expected R=0. Got {R}."