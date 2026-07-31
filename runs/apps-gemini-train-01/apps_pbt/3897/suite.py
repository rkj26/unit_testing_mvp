import random

def gen_input() -> str:
    n = random.randint(1, 500)
    a = []

    # Strategy choices for generating 'a' values to cover various cases
    strategy_choice = random.randint(0, 9)

    if strategy_choice == 0:  # Small n, varied a_i
        n = random.randint(1, min(n, 5)) # Keep n small for some tests
        a = [random.randint(1, 10**9) for _ in range(n)]
    elif strategy_choice == 1:  # Max n (500), all ones or all max values (10^9)
        n = 500
        if random.random() < 0.5:
            a = [1] * n
        else:
            a = [10**9] * n
    elif strategy_choice == 2:  # Max n (500), mixed values (1s, max values, random small/large)
        n = 500
        for _ in range(n):
            r = random.random()
            if r < 0.05: a.append(1)  # 5% ones
            elif r < 0.1: a.append(10**9)  # 5% max
            else: a.append(random.randint(2, 10**9))  # 90% random
    elif strategy_choice == 3:  # Mostly ones for a variable n, with a few other numbers
        n = random.randint(1, 500)
        num_ones = random.randint(0, n - 1)
        a = [1] * num_ones
        for _ in range(n - num_ones):
            a.append(random.randint(2, 10**9))
        random.shuffle(a)
    elif strategy_choice == 4:  # All a_i have the same value
        n = random.randint(1, 500)
        val = random.choice([1, 2, 3, 5, 7, 10**9, random.randint(1, 10**9)])
        a = [val] * n
    elif strategy_choice == 5:  # a_i are products of small prime factors
        n = random.randint(1, 500)
        small_primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97]
        for _ in range(n):
            val = 1
            num_factors_in_a_i = random.randint(1, 4)  # Product of 1 to 4 small primes
            for _ in range(num_factors_in_a_i):
                val *= random.choice(small_primes)
                if val > 10**9:
                    val = 10**9 # Cap to stay within bounds
                    break
            a.append(val if val > 0 else 1) # Ensure positive
    elif strategy_choice == 6:  # One large prime factor mixed with others (mostly 1s or small numbers)
        n = random.randint(1, 500)
        large_primes = [999999937, 999999893, 999999883, 999999863, 999999739] # Some large primes close to 10^9
        a = [random.choice(large_primes)]
        for _ in range(n - 1):
            a.append(1 if random.random() < 0.7 else random.randint(2, 100)) # Other factors are small or 1
        random.shuffle(a)
    elif strategy_choice == 7: # Single a_i (n=1) for extreme value or random
        n = 1
        a = [random.randint(1, 10**9)]
    elif strategy_choice == 8: # Specific example-like cases from problem statement or common edge cases
        examples = [
            (1, [15]),        # Sample 1
            (3, [1, 1, 2]),   # Sample 2
            (2, [5, 7]),      # Sample 3
            (2, [1, 2]),      # m=2, n=2 -> 2
            (3, [2, 2, 2]),   # m=8, n=3 -> 10
            (2, [2, 2]),      # m=4, n=2 -> 3
            (2, [6, 6]),      # m=36, n=2 -> 9
            (3, [1, 1, 6]),   # m=6, n=3 -> 9
            (3, [1, 2, 3]),   # m=6, n=3 -> 9
            (500, [1] * 499 + [2]), # m=2, n=500 -> 500
            (500, [1] * 500), # m=1, n=500 -> 1
        ]
        n, a = random.choice(examples)
    else:  # Fully random case
        a = [random.randint(1, 10**9) for _ in range(n)]

    return f"{n}\n{' '.join(map(str, a))}\n"


def check(stdin: str, stdout: str) -> None:
    MOD = 1000000007

    # 1. Parse stdin to extract n and a_i values
    lines = stdin.strip().split('\n')
    n = int(lines[0])
    a_str = lines[1].split()
    a = [int(x) for x in a_str]

    # 2. Parse stdout: The output must be a single integer
    try:
        output_value = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout}'")

    # 3. Check format and range properties
    # The output must be within [0, MOD-1] as it's modulo MOD.
    assert 0 <= output_value < MOD, f"Output {output_value} not in range [0, {MOD-1}]"

    # 4. Property: The number of decompositions must always be positive.
    # There is always at least one decomposition (e.g., (1, ..., 1, m) if m > 0).
    assert output_value > 0, f"Output {output_value} must be positive."

    # 5. Property: If n = 1, there is always exactly 1 decomposition.
    # The only decomposition is (m).
    if n == 1:
        assert output_value == 1, f"For n=1, expected 1, got {output_value}"

    # 6. Property: If m = 1 (i.e., all a_i are 1), there is always exactly 1 decomposition.
    # The only decomposition is (1, 1, ..., 1).
    product_is_one = True
    for x in a:
        if x != 1:
            product_is_one = False
            break
    if product_is_one:
        assert output_value == 1, f"For m=1 (all a_i=1), expected 1, got {output_value}"

    # 7. Property: If m is a small prime number P (and n > 0), the number of decompositions is n.
    # This happens when exactly one a_i is P and all other a_j are 1.
    # We check this only for a fixed, small set of known prime numbers to avoid re-implementing a solver.
    if n > 0:
        non_one_elements = [x for x in a if x != 1]
        if len(non_one_elements) == 1:
            prime_candidate = non_one_elements[0]
            # List of small primes for which we can safely hardcode primality check.
            fixed_small_primes = {
                2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97
            }
            if prime_candidate in fixed_small_primes:
                assert output_value == n, f"For m={prime_candidate} (prime) and n={n}, expected {n}, got {output_value} for stdin: {stdin!r}"