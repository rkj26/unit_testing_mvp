import random

def gen_input() -> str:
    """
    Generates a single test case input string for the problem.
    Covers various N values and distributions of coordinates.
    """
    # Determine n (number of computers)
    rand_n_choice = random.random()
    if rand_n_choice < 0.05:  # N=1
        n = 1
    elif rand_n_choice < 0.1:  # N=2
        n = 2
    elif rand_n_choice < 0.2:  # N=3 to 10
        n = random.randint(3, 10)
    elif rand_n_choice < 0.5:  # N=10 to 1000 (medium)
        n = random.randint(10, 1000)
    elif rand_n_choice < 0.8:  # N=1000 to 3*10^5 (large)
        n = random.randint(1000, 3 * 10**5)
    else:  # Max N with higher probability
        n = 3 * 10**5 
    
    # Generate distinct coordinates
    x_coords_set = set()
    MAX_COORD = 10**9
    
    # Strategy for coordinate values
    coord_type_choice = random.random()
    if coord_type_choice < 0.25: # Small range coordinates
        start_val = random.randint(1, MAX_COORD // 100)
        while len(x_coords_set) < n:
            x_coords_set.add(random.randint(start_val, min(MAX_COORD, start_val + n * 2 + 100)))
    elif coord_type_choice < 0.5: # Large range coordinates, near MAX_COORD
        end_val = random.randint(MAX_COORD // 2, MAX_COORD)
        while len(x_coords_set) < n:
            x_coords_set.add(random.randint(max(1, end_val - n * 2 - 100), end_val))
    else: # Wide range or mixed coordinates
        # Try to fill from full range, then potentially cluster some for edge cases
        while len(x_coords_set) < n:
            x_coords_set.add(random.randint(1, MAX_COORD))

    x_coords_list = list(x_coords_set)
    random.shuffle(x_coords_list) # Keep coordinates unsorted to test sorting robustness
    
    return f"{n}\n{' '.join(map(str, x_coords_list))}\n"

def check(stdin: str, stdout: str) -> None:
    """
    Asserts properties that the correct output must satisfy.
    This function should not re-implement the full O(N) solver.
    """
    MOD = 10**9 + 7

    # 1. Output format and range check
    try:
        result = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout}'")

    if not (0 <= result < MOD):
        raise AssertionError(f"Output {result} is not within [0, {MOD-1})")

    # Parse input for N and coordinates
    lines = stdin.strip().split('\n')
    n = int(lines[0])
    
    # Coordinates list for small N checks.
    # We sort them here as the problem's F(a) naturally operates on sorted min/max.
    # This is not "reimplementing" the solver, just preparing input data for simple checks.
    if n <= 3: # Only parse coordinates if N is small, avoid parsing large inputs unnecessarily
        try:
            x_coords = list(map(int, lines[1].split()))
            y_sorted = sorted(x_coords)
        except (IndexError, ValueError):
            # This should not happen if gen_input is correct, but defensive.
            raise AssertionError(f"Failed to parse coordinates from stdin: '{stdin}'")


    # 2. Specific checks for small N values (edge cases)
    # These are O(1) computations and do not constitute an "efficient solver".

    if n == 1:
        # For N=1, there's only one non-empty subset {x_1}. F({x_1}) = |x_1 - x_1| = 0.
        expected_sum = 0
        if result != expected_sum:
            raise AssertionError(f"For N=1, expected sum {expected_sum}, but got {result}. Input: {stdin.strip()}")

    elif n == 2:
        # For N=2, coordinates y_0, y_1 (sorted).
        # Subsets: {y_0}, {y_1}, {y_0, y_1}.
        # F({y_0})=0, F({y_1})=0, F({y_0, y_1})=y_1-y_0.
        # Total sum = y_1 - y_0.
        expected_sum = (y_sorted[1] - y_sorted[0]) % MOD
        if expected_sum < 0: # Ensure positive modulo result
            expected_sum += MOD
        if result != expected_sum:
            raise AssertionError(f"For N=2 (coords: {x_coords}), expected sum {expected_sum}, but got {result}. Input: {stdin.strip()}")

    elif n == 3:
        # For N=3, coordinates y_0, y_1, y_2 (sorted).
        # The exact formula for N=3 is sum = (y_2 - y_0) * 2^(3-1-1) + (y_1 - y_0) * 2^(2-1-1) + (y_2 - y_1) * 2^(3-2-1)
        # = (y_2 - y_0) * 2^1 + (y_1 - y_0) * 2^0 + (y_2 - y_1) * 2^0
        # = 2*(y_2 - y_0) + (y_1 - y_0) + (y_2 - y_1)
        # = 2*y_2 - 2*y_0 + y_1 - y_0 + y_2 - y_1
        # = 3*y_2 - 3*y_0
        y0, y1, y2 = y_sorted[0], y_sorted[1], y_sorted[2]
        expected_sum = (3 * y2 - 3 * y0) % MOD
        if expected_sum < 0: # Ensure positive modulo result
            expected_sum += MOD
        if result != expected_sum:
            raise AssertionError(f"For N=3 (coords: {x_coords}), expected sum {expected_sum}, but got {result}. Input: {stdin.strip()}")

    # No further general properties are asserted, as they would require
    # reimplementing the problem's O(N) solution, which is disallowed.