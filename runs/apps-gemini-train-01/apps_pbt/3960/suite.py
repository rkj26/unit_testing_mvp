import random

def gen_input() -> str:
    """
    Generates a single valid input string for the problem.
    Covers various scenarios including boundary values, large random cases,
    and specific patterns to stress test the model.
    """
    N_MIN = 2
    N_MAX = 10**5
    A_MIN = -10**9
    A_MAX = 10**9

    # Determine n
    n: int
    rand_n_choice = random.random()
    if rand_n_choice < 0.1:  # Smallest N
        n = N_MIN
    elif rand_n_choice < 0.2: # Small N
        n = random.randint(N_MIN, 10)
    elif rand_n_choice < 0.4: # Medium N
        n = random.randint(11, 1000)
    elif rand_n_choice < 0.6: # Large N, but not max
        n = random.randint(1001, N_MAX // 10)
    else: # Max N or near max
        n = random.randint(N_MAX // 2, N_MAX)
    
    a = []
    
    # Determine array generation strategy
    strategy = random.randint(0, 7)

    if strategy == 0: # All elements equal
        val = random.randint(A_MIN, A_MAX)
        a = [val] * n
    elif strategy == 1: # Fully random values
        a = [random.randint(A_MIN, A_MAX) for _ in range(n)]
    elif strategy == 2: # Strictly increasing sequence
        start_val = random.randint(A_MIN, A_MAX - (n - 1))
        # Step can be 0 for duplicates if n is large, but aim for strictly increasing
        step = random.randint(1, max(1, (A_MAX - start_val) // max(1, n - 1)))
        a = [start_val + i * step for i in range(n)]
    elif strategy == 3: # Strictly decreasing sequence
        start_val = random.randint(A_MIN + (n - 1), A_MAX)
        step = random.randint(1, max(1, (start_val - A_MIN) // max(1, n - 1)))
        a = [start_val - i * step for i in range(n)]
    elif strategy == 4: # Alternating high/low values
        val1 = random.randint(A_MIN, A_MAX)
        val2 = random.randint(A_MIN, A_MAX)
        a = [val1 if i % 2 == 0 else val2 for i in range(n)]
    elif strategy == 5: # Values clustered around zero
        a = [random.randint(-1000, 1000) for _ in range(n)]
    elif strategy == 6: # Values clustered near A_MAX
        a = [random.randint(A_MAX - 1000, A_MAX) for _ in range(n)]
    elif strategy == 7: # Values clustered near A_MIN
        a = [random.randint(A_MIN, A_MIN + 1000) for _ in range(n)]
    
    # Ensure values are within bounds (should generally be handled by strategy, but as a safeguard)
    a = [max(A_MIN, min(val, A_MAX)) for val in a]

    input_str = str(n) + "\n" + " ".join(map(str, a)) + "\n"
    return input_str

def check(stdin: str, stdout: str) -> None:
    """
    Checks properties of the program's output.

    Args:
        stdin: The input string provided to the program.
        stdout: The output string produced by the program.

    Raises:
        AssertionError: If any property is violated.
    """
    # Parse stdin to get n and array a
    lines = stdin.strip().split('\n')
    n = int(lines[0])
    a = list(map(int, lines[1].split()))

    # 1. Check output format: Must be a single integer string
    try:
        program_output_str = stdout.strip()
        if not program_output_str:
            raise ValueError("Output is empty.")
        # Check if the string contains non-digit characters other than a leading minus sign
        if not (program_output_str.lstrip('-').isdigit() and 
                (program_output_str.startswith('-') or program_output_str.isdigit())):
            raise ValueError("Output is not a valid integer string.")
        result_int = int(program_output_str)
    except (ValueError, IndexError) as e:
        raise AssertionError(f"Program output format is incorrect: '{stdout}'. Error: {e}")

    # 2. Check output value bounds (loose sanity check)
    # The maximum possible absolute difference is |10^9 - (-10^9)| = 2 * 10^9.
    # The maximum length of the sequence of differences is n-1.
    # The sum can involve at most (n-1) terms.
    # So max possible sum is roughly (n-1) * 2 * 10^9.
    # For n=10^5, this is ~ 10^5 * 2 * 10^9 = 2 * 10^14.
    # We use a slightly generous bound.
    MAX_ABS_RESULT = 2 * 10**14 + 1000 # Adding a buffer for safety
    if not (-MAX_ABS_RESULT <= result_int <= MAX_ABS_RESULT):
        raise AssertionError(
            f"Output {result_int} is outside expected bounds "
            f"[-{MAX_ABS_RESULT}, {MAX_ABS_RESULT}]."
        )

    # 3. Property for n=2: The only possible interval is [1, 2] (1-indexed) or [0, 1] (0-indexed).
    # f(1, 2) = |a[1] - a[2]| * (-1)^(1-1) = |a[1] - a[2]|
    # For 0-indexed Python array `a`: f = abs(a[0] - a[1])
    if n == 2:
        expected_f = abs(a[0] - a[1])
        if result_int != expected_f:
            raise AssertionError(
                f"For n=2 with array {a}, expected maximum f to be {expected_f}, "
                f"but got {result_int}."
            )

    # 4. Property for arrays with all identical elements:
    # If all a_i are the same, then |a_i - a_i+1| will always be 0.
    # The sum f(l, r) will therefore always be 0.
    if len(set(a)) == 1:
        if result_int != 0:
            raise AssertionError(
                f"For array {a} with all identical elements, expected maximum f to be 0, "
                f"but got {result_int}."
            )