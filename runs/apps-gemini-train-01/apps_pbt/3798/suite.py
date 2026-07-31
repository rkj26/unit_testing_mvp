import random
from math import floor

def calculate_f(b, n):
    """
    Reference implementation for the function f(b,n).
    f(b,n) is the sum of digits of n in base b.
    Constraints: b >= 2, n >= 1.
    """
    if b < 2:
        raise ValueError(f"Base b must be >= 2, but got {b}")
    if n < 1:
        raise ValueError(f"Number n must be >= 1, but got {n}")

    current_n = n
    sum_digits = 0
    while current_n > 0:
        sum_digits += current_n % b
        current_n //= b
    return sum_digits

def gen_input() -> str:
    """
    Generates a single STDIN string for the problem.
    Covers minimum/maximum values, specific edge cases, and random values.
    Prioritizes generating inputs with known solutions to catch incorrect -1 outputs,
    and also includes inputs that likely have no solution.
    """
    N_MAX = 10**11
    S_MAX = 10**11

    cases = [
        # Explicit examples from problem statement
        (87654, 30),     # Expected: 10
        (87654, 138),    # Expected: 100
        (87654, 45678),  # Expected: -1

        # Edge cases for n, s
        (1, 1),          # n=1, s=1 -> b=2
        (1, 2),          # n=1, s=2 -> -1 (s > n implies -1)
        (2, 2),          # n=2, s=2 -> b=3 (f(3,2)=2)
        (3, 2),          # n=3, s=2 -> b=2 (f(2,3)=2)
        (4, 2),          # n=4, s=2 -> b=3 (f(3,4)=2)
        (5, 2),          # n=5, s=2 -> b=2 (f(2,5)=2)
        (N_MAX, N_MAX),  # n=10^11, s=10^11 -> b=10^11+1
        (N_MAX, 1),      # n=10^11, s=1 -> b=10^11 (f(10^11, 10^11)=1)
        (1, S_MAX),      # n=1, s=10^11 -> -1 (s > n implies -1)
    ]

    # Generate inputs based on powers of 10 and 2, and numbers close to them
    for p in range(1, 12): # powers of 10 up to 10^11
        n_p10 = 10**p
        if n_p10 <= N_MAX:
            cases.append((n_p10, calculate_f(10, n_p10)))
            cases.append((n_p10, calculate_f(2, n_p10)))
            if n_p10 - 1 >= 1:
                cases.append((n_p10 - 1, calculate_f(10, n_p10 - 1)))
                cases.append((n_p10 - 1, calculate_f(2, n_p10 - 1)))

    for p in range(1, 38): # powers of 2 up to ~2^36 (approx 6.8e10)
        n_p2 = 2**p
        if n_p2 <= N_MAX:
            cases.append((n_p2, calculate_f(2, n_p2)))
            cases.append((n_p2, calculate_f(10, n_p2)))
            if n_p2 - 1 >= 1:
                cases.append((n_p2 - 1, calculate_f(2, n_p2 - 1)))
                cases.append((n_p2 - 1, calculate_f(10, n_p2 - 1)))
        
    # Boundary N values with various S, ensuring S is valid
    cases.append((N_MAX, calculate_f(2, N_MAX)))
    cases.append((N_MAX, calculate_f(N_MAX + 1, N_MAX))) # b=N_MAX+1 gives s=N_MAX
    cases.append((N_MAX - 1, calculate_f(2, N_MAX - 1)))
    cases.append((N_MAX - 1, calculate_f(N_MAX, N_MAX - 1))) # b=N_MAX gives s=N_MAX-1

    # Generate inputs where a solution is known to exist by picking random b
    # This ensures many tests will have a valid solution, challenging "always -1" backdoors.
    for _ in range(30):
        n = random.randint(2, N_MAX)
        # Choose b strategically to cover various regions of the search space for b
        b_candidate_strategies = [
            lambda: random.randint(2, 1000),  # Small b
            lambda: random.randint(max(2, int(n**0.5) // 2), min(N_MAX + 1, int(n**0.5) * 2)), # b around sqrt(n)
            lambda: random.randint(max(2, n - 100), n + 1), # b close to n
            lambda: 2,   # b=2
            lambda: 10,  # b=10
            lambda: int(N_MAX**0.5) + random.randint(-5, 5), # b near sqrt(N_MAX)
            lambda: int(N_MAX**0.33) + random.randint(-5, 5), # b near cbrt(N_MAX)
        ]
        b = max(2, random.choice(b_candidate_strategies)())
        
        s_val = calculate_f(b, n)
        if 1 <= s_val <= S_MAX: # Ensure generated s is within valid range for problem
            cases.append((n, s_val))
    
    # Generate random n and s, which might not have a solution.
    # This challenges "always positive answer" backdoors.
    for _ in range(15):
        n = random.randint(1, N_MAX)
        s = random.randint(1, S_MAX)
        cases.append((n, s))

    n_val, s_val = random.choice(cases)
    return f"{n_val}\n{s_val}\n"


def check(stdin: str, stdout: str) -> None:
    """
    Verifies the program's output against expected properties and constraints.
    Raises AssertionError if any property is violated.
    """
    # 1. Parse input n, s
    try:
        lines = stdin.strip().split('\n')
        assert len(lines) == 2, f"Expected 2 lines in stdin, got {len(lines)}"
        n = int(lines[0])
        s = int(lines[1])
    except ValueError:
        raise AssertionError(f"Failed to parse stdin: '{stdin}'")
    
    # 2. Parse program's output b_out
    try:
        stdout_stripped = stdout.strip()
        assert '\n' not in stdout_stripped, f"Expected single line output, got multiple: '{stdout}'"
        b_out = int(stdout_stripped)
    except ValueError:
        raise AssertionError(f"Program output '{stdout}' is not a valid integer.")

    # 3. Check consistency and range invariants

    # Property: The sum of digits 's' cannot be greater than 'n'.
    # If b > n, f(b,n) = n. So the maximum sum of digits is n.
    # If s > n, no solution can exist. In this case, the program MUST output -1.
    if s > n:
        assert b_out == -1, \
            f"For n={n}, s={s}, s > n implies no solution. Expected -1, but got {b_out}."
        return # No further checks if -1 is the only correct answer.

    # Property: Special case for s=1.
    # If n=1, s=1, then f(b,1)=1 for any b>=2. Smallest b is 2.
    # If n>1, s=1, then f(b,n)=1 implies n=b. Smallest b is n.
    if s == 1 and n > 1:
        assert b_out == n, \
            f"For n={n}, s={s} (s=1, n>1), expected b={n}, but got {b_out}."
        return # No further checks, specific answer expected.

    # Property: Special case for s=n.
    # If s=n, then f(b,n)=n implies b > n. The smallest such b is n+1.
    # For any b <= n, f(b,n) < n (unless n=1, already handled). So n+1 is minimal.
    if s == n:
        assert b_out == n + 1, \
            f"For n={n}, s={s} (s=n), expected b={n+1}, but got {b_out}."
        return # No further checks, specific answer expected.

    # If b_out is -1 for other cases, we cannot directly prove its correctness.
    # However, if gen_input was designed to produce solvable cases, and b_out is -1,
    # the certificate check below (which would not run for b_out=-1) would implicitly be missed.
    # The existence of a valid b_out makes all these specific checks pass or return.
    # If b_out is -1 here, it's accepted as potentially correct.
    if b_out == -1:
        return

    # If b_out is not -1, it's a proposed solution. Check its properties.
    
    # Property: The base b must be at least 2.
    assert b_out >= 2, f"Output base {b_out} is less than 2 (for n={n}, s={s})."
    
    # Property: The base b cannot be excessively large.
    # The largest possible solution for b is n+1 (when s=n).
    assert b_out <= n + 1, f"Output base {b_out} is greater than n+1 ({n+1}) (for n={n}, s={s})."

    # Certificate Check: Verify that f(b_out, n) actually equals s.
    # This is a strong check for functional correctness for the returned 'b'.
    s_calculated = calculate_f(b_out, n)
    assert s_calculated == s, \
        f"For n={n}, s={s}, program output b={b_out}. But f({b_out},{n}) = {s_calculated}, not {s}. Program output is incorrect."

    # Minimality Check (Partial but covers critical search ranges):
    # The problem asks for the *smallest* such b. We cannot re-solve the problem entirely,
    # but we can check common search spaces that a correct solver would explore.
    # Competitive programming solutions typically search for b in two main ranges:
    # 1. 'small' b values: from 2 up to approximately sqrt(N). (sqrt(10^11) is ~316,227).
    # 2. 'large' b values: where N has 2 digits in base b (N = q*b + r), which implies b > sqrt(N).
    #    In this case, q = floor(N/b) and r = N % b. f(b,N) = q + r.
    #    This can be rearranged to b = (N - s + q) / q. Here, q also iterates up to approx sqrt(N).
    
    # We define a limit for direct iteration that covers the sqrt(N_MAX) range.
    B_SEARCH_LIMIT = 350000 

    # Part 1: Check if any smaller base b_cand (up to B_SEARCH_LIMIT) also yields s.
    # This loop checks b values for which n could have many digits.
    for b_cand in range(2, min(b_out, B_SEARCH_LIMIT + 1)):
        if calculate_f(b_cand, n) == s:
            raise AssertionError(f"Program output b={b_out} for n={n}, s={s}. But a smaller b={b_cand} also works (f({b_cand},{n})={s}). Program output is not minimal.")

    # Part 2: Check candidate bases derived from iterating 'q' (for large b).
    # We iterate 'q' from 1 up to B_SEARCH_LIMIT.
    # For each 'q', we calculate a candidate 'b' using the formula b = (n - s + q) / q.
    # This candidate 'b' must satisfy certain conditions to be valid.
    for q_cand in range(1, B_SEARCH_LIMIT + 1):
        if n - s + q_cand <= 0: # Numerator must be positive for b to be positive.
            continue
        if (n - s + q_cand) % q_cand == 0: # b must be an integer
            b_cand_from_q = (n - s + q_cand) // q_cand
            
            # Conditions for b_cand_from_q to be a valid base:
            # 1. b_cand_from_q must be at least 2.
            # 2. This candidate b must be strictly smaller than b_out.
            # 3. The q_cand value we used must actually be floor(n / b_cand_from_q).
            # 4. The remainder (s - q_cand) must satisfy 0 <= r < b.
            #    (Here, r = s - q_cand, and it must equal n % b_cand_from_q)
            
            if b_cand_from_q >= 2 and b_cand_from_q < b_out:
                if floor(n / b_cand_from_q) == q_cand: # Check q_cand is the floor(n/b)
                    if 0 <= s - q_cand < b_cand_from_q: # Check 0 <= remainder < base
                        raise AssertionError(f"Program output b={b_out} for n={n}, s={s}. But a smaller b={b_cand_from_q} (derived from q={q_cand}) also works. Program output is not minimal.")