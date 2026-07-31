import random

def gen_input() -> str:
    test_cases = []

    # --- Boundary and small N, K, X cases ---
    # N=1
    test_cases.append((1, 1, 2, [0]))
    test_cases.append((1, 1, 2, [1]))
    test_cases.append((1, 1, 2, [10**9]))
    test_cases.append((1, 10, 8, [1]))
    test_cases.append((1, 10, 8, [10**9])) # Max values for a_i, k, x, min N

    # N=2, minimal k, x
    test_cases.append((2, 1, 2, [0, 0]))
    test_cases.append((2, 1, 2, [1, 1]))
    test_cases.append((2, 1, 2, [1, 2])) # Check simple OR vs mult
    test_cases.append((2, 1, 2, [10**9-1, 10**9]))

    # N=2, maximal k, x
    test_cases.append((2, 10, 8, [1, 1]))
    test_cases.append((2, 10, 8, [1, 10**9]))
    test_cases.append((3, 10, 8, [0, 10**9 // 2, 10**9]))

    # --- Provided example cases ---
    test_cases.append((3, 1, 2, [1, 1, 1]))
    test_cases.append((4, 2, 3, [1, 2, 4, 8]))
    test_cases.append((2, 1, 2, [12, 9]))

    # --- Specific bit patterns and values for a_i ---
    # Powers of 2, small numbers, different x
    test_cases.append((5, 3, 2, [0, 1, 2, 4, 8])) # x=2 (bit shift behavior)
    test_cases.append((5, 3, 3, [0, 1, 2, 4, 8])) # x=3 (more complex bits)
    test_cases.append((5, 3, 7, [0, 1, 2, 4, 8])) # x=7

    # Numbers that are all 1s up to a certain bit (e.g., 2^b - 1)
    test_cases.append((5, 1, 2, [2**i - 1 for i in range(1, 6)]))
    test_cases.append((5, 1, 3, [2**i - 1 for i in range(1, 6)]))
    
    # Boundary values for a_i near 10^9 and 0, 1
    test_cases.append((5, 1, 2, [10**9, 10**9-1, 10**9-2, 1, 0]))

    # --- Large N, small K cases ---
    test_cases.append((200000, 1, 2, [i % 2 for i in range(200000)])) # Alternating 0,1
    test_cases.append((200000, 1, 2, [1] * 200000)) # All ones
    test_cases.append((200000, 1, 2, [10**9] * 200000)) # All max values
    test_cases.append((200000, 1, 2, [random.randint(0, 1) for _ in range(200000)])) # Random 0s and 1s

    # --- Diverse random cases ---
    for _ in range(10): # Add several diverse random cases to ensure variety
        n = random.randint(1, 200000)
        k = random.randint(1, 10)
        x = random.randint(2, 8)
        a = [random.randint(0, 10**9) for _ in range(n)]
        test_cases.append((n, k, x, a))

        # Random case with many zeros and a few large numbers
        a_mixed_zeros = [0] * n
        # Ensure at least one non-zero unless n=1, a=[0]
        num_non_zeros = random.randint(1, min(n, 100))
        for _ in range(num_non_zeros):
            a_mixed_zeros[random.randint(0, n-1)] = random.randint(1, 10**9)
        test_cases.append((n, k, x, a_mixed_zeros))

        # Random case with many small numbers and one or a few large
        if n > 1:
            a_mixed_small_large = [random.randint(0, 100) for _ in range(n-1)]
            a_mixed_small_large.append(random.randint(10**9 - 1000, 10**9))
            random.shuffle(a_mixed_small_large) # Shuffle to make sure the large number isn't always last
            test_cases.append((n, k, x, a_mixed_small_large))
        else: # n=1, just use a large number if not already covered
            test_cases.append((1, k, x, [random.randint(10**9 - 1000, 10**9)]))

    # Choose one randomly from all generated cases
    n, k, x, a = random.choice(test_cases)

    input_str = f"{n} {k} {x}\n" + " ".join(map(str, a)) + "\n"
    return input_str

def check(stdin: str, stdout: str) -> None:
    # 1. Parse input and output
    lines = stdin.strip().split('\n')
    n, k, x = map(int, lines[0].split())
    a = list(map(int, lines[1].split()))

    try:
        output_value = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout}'")

    # 2. Assert output properties

    # Property 1: Output value must be non-negative.
    # All input numbers a_i are >= 0, and x >= 2. Operations maintain non-negativity.
    # Bitwise OR of non-negative numbers is non-negative.
    assert output_value >= 0, f"Output value must be non-negative, but got {output_value}"

    # Property 2: Output value must be at least the initial OR sum.
    # The problem asks to maximize OR after *at most* k operations.
    # Choosing to perform 0 operations is always an option. In this case, the OR sum
    # would be the initial OR sum of all numbers. The optimal solution cannot be worse.
    initial_or = 0
    # Since n >= 1, a is guaranteed to have at least one element.
    for val in a:
        initial_or |= val
    assert output_value >= initial_or, \
        f"Output {output_value} is less than initial OR of array {initial_or}"

    # Property 3: Output value must not exceed a calculated theoretical upper bound.
    # A loose but sound upper bound: the OR sum if *every* element were multiplied by x^k.
    # This is because for any a_i, a_i <= a_i * x^k (since x >= 2, k >= 1).
    # Bitwise OR is monotonic, so if we replace any a_i with a_i * x^k, the OR cannot decrease.
    # The actual solution involves multiplying only ONE element by x^k (or multiple distinct
    # elements if k > 1, but always totaling k multiplications).
    # Even if we multiplied each element by x^k, the result would be (a_1*x^k)|...|(a_n*x^k).
    # The true optimal value (a_j*x^k) | (OR_{i != j} a_i) must be <= this loose bound.
    max_possible_or_bound = 0
    x_pow_k = x ** k # Calculate x^k once. Max x^k is 8^10 approx 10^9.
    # Max a_i * x^k is 10^9 * 8^10 approx 10^18. Python handles large integers.
    for val in a:
        max_possible_or_bound |= (val * x_pow_k)
    
    assert output_value <= max_possible_or_bound, \
        f"Output {output_value} exceeds theoretical maximum possible OR bound {max_possible_or_bound}"