import random

def gen_input() -> str:
    # N from 1 to 100
    N = random.randint(1, 100)

    a = []
    
    # Introduce different scenarios for a_i values to explore boundaries and common pitfalls
    choice = random.randint(1, 10)
    
    if choice == 1: # All positive values
        for _ in range(N):
            a.append(random.randint(1, 10**9))
    elif choice == 2: # All negative values
        for _ in range(N):
            a.append(random.randint(-10**9, -1))
    elif choice == 3: # All zero values
        for _ in range(N):
            a.append(0)
    elif choice == 4: # Mixed values, small N to explore specific divisor/multiple patterns
        current_N = random.randint(1, min(N, 10)) # Keep N small for structural tests
        for _ in range(current_N):
            a.append(random.randint(-10**9, 10**9))
        N = current_N # Adjust N for this specific case
    elif choice == 5: # Large N, extreme values, mixed
        N = random.randint(50, 100)
        for _ in range(N):
            val_choice = random.randint(1, 3)
            if val_choice == 1: # Large positive
                a.append(random.randint(1, 10**9))
            elif val_choice == 2: # Large negative
                a.append(random.randint(-10**9, -1))
            else: # Zero
                a.append(0)
    elif choice == 6: # N=1 boundary case
        N = 1
        a.append(random.randint(-10**9, 10**9))
    elif choice == 7: # N=100 boundary case, mixed values
        N = 100
        for _ in range(N):
            a.append(random.randint(-10**9, 10**9))
    elif choice == 8: # A few positive values, many negative/zero
        positive_count = random.randint(1, min(N, 5))
        for _ in range(positive_count):
            a.append(random.randint(1, 10**9))
        for _ in range(N - positive_count):
            a.append(random.randint(-10**9, 0))
        random.shuffle(a)
    elif choice == 9: # Many positive values, a few negative/zero
        negative_count = random.randint(1, min(N, 5))
        for _ in range(negative_count):
            a.append(random.randint(-10**9, -1))
        for _ in range(N - negative_count):
            a.append(random.randint(0, 10**9))
        random.shuffle(a)
    else: # Default: general random mixed values
        for _ in range(N):
            a.append(random.randint(-10**9, 10**9))
    
    input_str = f"{N}\n{' '.join(map(str, a))}\n"
    return input_str

def check(stdin: str, stdout: str) -> None:
    # Parse input from stdin string
    lines = stdin.strip().split('\n')
    N = int(lines[0])
    # a_i are 1-indexed in problem, so a[0] corresponds to a_1, a[N-1] to a_N.
    a = list(map(int, lines[1].split()))

    # Parse output from stdout string
    try:
        result = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output '{stdout}' is not a single integer.")

    # Property 1: The maximum earned yen must be non-negative.
    # It's always possible to earn 0 yen by choosing x=1 (smash all gems).
    assert result >= 0, \
        f"Result {result} is negative, but 0 yen is always achievable by smashing all gems. Input: {stdin}"

    # Property 2: The maximum earned yen cannot exceed the sum of all positive a_i values.
    # This represents an upper bound where all positive gems are kept and all negative gems are ignored.
    # No operation can increase this sum.
    max_possible_gain_naive = sum(max(0, val) for val in a)
    assert result <= max_possible_gain_naive, \
        f"Result {result} exceeds the theoretical maximum possible gain {max_possible_gain_naive}. Input: {stdin}"

    # Property 3: If all a_i are strictly positive, the optimal strategy is to perform no operations.
    # In this case, all gems remain, and the total earnings are the sum of all a_i.
    if all(val > 0 for val in a):
        expected_sum = sum(a)
        assert result == expected_sum, \
            f"All a_i are positive; expected to keep all gems for {expected_sum}, got {result}. Input: {stdin}"

    # Property 4: If all a_i are non-positive (negative or zero), the optimal strategy is to smash all gems.
    # This leads to 0 yen, as described in Property 1.
    if all(val <= 0 for val in a):
        assert result == 0, \
            f"All a_i are non-positive; expected 0 yen, got {result}. Input: {stdin}"
            
    # Property 5: For N=1, the optimal is simply max(0, a_1).
    if N == 1:
        expected_result_N1 = max(0, a[0])
        assert result == expected_result_N1, \
            f"N=1 specific case; expected {expected_result_N1}, got {result}. Input: {stdin}"

    # Property 6: For N=2, manually enumerate all relevant minimal sets of smashers.
    # Let a_1=a[0], a_2=a[1].
    # - X_smash = {}: gems 1,2 remain. Gain: a_1 + a_2.
    # - X_smash = {1}: gems 1,2 smashed. Gain: 0.
    # - X_smash = {2}: gem 2 smashed. gem 1 remains. Gain: a_1.
    # The optimal is the maximum of these options.
    if N == 2:
        options = [
            0,                      # Smash all (by choosing x=1)
            a[0] + a[1],            # Smash nothing (X_smash={})
            a[0]                    # Smash multiples of 2 (X_smash={2})
        ]
        expected_result_N2 = max(options)
        assert result == expected_result_N2, \
            f"N=2 specific case; expected {expected_result_N2}, got {result}. Input: {stdin}"

    # Property 7: For N=3, manually enumerate all relevant minimal sets of smashers.
    # Let a_1=a[0], a_2=a[1], a_3=a[2].
    # - X_smash = {}: gems 1,2,3 remain. Gain: a_1 + a_2 + a_3.
    # - X_smash = {1}: all smashed. Gain: 0.
    # - X_smash = {2}: gem 2 smashed. gems 1,3 remain. Gain: a_1 + a_3.
    # - X_smash = {3}: gem 3 smashed. gems 1,2 remain. Gain: a_1 + a_2.
    # - X_smash = {2,3}: gems 2,3 smashed. gem 1 remains. Gain: a_1.
    # Note: X_smash={1,2}, {1,3}, {1,2,3} are covered by X_smash={1} yielding 0.
    # The optimal is the maximum of these options.
    if N == 3:
        options = [
            0,                          # Smash all (by choosing x=1)
            a[0] + a[1] + a[2],         # Smash nothing (X_smash={})
            a[0] + a[2],                # Smash multiples of 2 (X_smash={2})
            a[0] + a[1],                # Smash multiples of 3 (X_smash={3})
            a[0]                        # Smash multiples of 2 AND 3 (X_smash={2,3})
        ]
        expected_result_N3 = max(options)
        assert result == expected_result_N3, \
            f"N=3 specific case; expected {expected_result_N3}, got {result}. Input: {stdin}"