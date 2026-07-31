import random

def gen_input() -> str:
    n = random.randint(0, 1000)
    
    # Choose k, biasing towards smaller values and boundaries but including large
    # This helps in testing small, specific scenarios and also performance for large K
    k_options = [1, 2, 3, 4, 5, 10, 50, 100, 1000, 10**4, 10**5, 10**6]
    k_weights = [10, 10, 10, 10, 10, 5, 5, 5, 5, 5, 5, 10]
    k = random.choices(k_options, weights=k_weights, k=1)[0]
    
    a_values = []

    # Scenario choices to cover various problem aspects
    scenario_choice = random.randint(0, 9)

    if scenario_choice == 0: # All a_i < n (impossible if n > 0). If n=0, implies all a_i=0.
        if n > 0:
            a_values = [random.randint(0, n - 1) for _ in range(k)]
        else: # n == 0. Generate types that are all > 0 for impossible case, or mix for possible case.
            if random.random() < 0.5: # Truly impossible (n=0, all a_i > 0)
                a_values = [random.randint(1, 1000) for _ in range(k)]
            else: # Possible (n=0, some a_i=0)
                a_values = [0] * k
                if k > 1: a_values[random.randint(0, k-1)] = random.randint(1,1000) # Mix it up
            random.shuffle(a_values)
            
    elif scenario_choice == 1: # All a_i > n (impossible if n < 1000). If n=1000, implies all a_i=1000.
        if n < 1000:
            a_values = [random.randint(n + 1, 1000) for _ in range(k)]
        else: # n == 1000. Generate types that are all < 1000 for impossible case, or mix for possible case.
            if random.random() < 0.5: # Truly impossible (n=1000, all a_i < 1000)
                a_values = [random.randint(0, 999) for _ in range(k)]
            else: # Possible (n=1000, some a_i=1000)
                a_values = [1000] * k
                if k > 1: a_values[random.randint(0, k-1)] = random.randint(0,999) # Mix it up
            random.shuffle(a_values)

    elif scenario_choice == 2: # n is present, answer should be 1
        a_values = [random.randint(0, 1000) for _ in range(k - 1)]
        a_values.append(n)
        random.shuffle(a_values)

    elif scenario_choice == 3 and k >= 2: # Two values symmetric around n for potential V=2
        # Try to make a pair (n-x, n+x)
        if n > 0 and n < 1000:
            diff = random.randint(1, min(n, 1000 - n)) # x
            a_values = [n - diff, n + diff]
        else: # n=0 or n=1000, symmetric pair is hard/trivial. Fallback.
            a_values = [random.randint(0, 1000) for _ in range(2)]
            
        while len(a_values) < k:
            a_values.append(random.randint(0, 1000))
        random.shuffle(a_values)
    
    elif scenario_choice == 4 and k >= 2: # Two extreme values 0 and 1000
        a_values = [0, 1000]
        while len(a_values) < k:
            a_values.append(random.randint(0, 1000))
        random.shuffle(a_values)

    elif scenario_choice == 5 and k >= 3: # Three values for more complex sums
        # Generate three base values.
        base_a = [random.randint(0, 1000) for _ in range(3)]
        # Ensure possibility of solution if it wasn't trivially impossible already
        if not any(x <= n for x in base_a) and n > 0:
            base_a[random.randint(0, 2)] = random.randint(0, n)
        if not any(x >= n for x in base_a) and n < 1000:
            base_a[random.randint(0, 2)] = random.randint(n, 1000)
        
        a_values = base_a
        while len(a_values) < k:
            a_values.append(random.randint(0, 1000))
        random.shuffle(a_values)

    else: # General random mix (covers 6, 7, 8, 9)
        a_values = [random.randint(0, 1000) for _ in range(k)]
        # Ensure possibility of solution for most cases if not already impossible
        if not any(x <= n for x in a_values) and n > 0:
            if k > 0: a_values[random.randint(0, k - 1)] = random.randint(0, n)
            else: a_values.append(random.randint(0, n))
        if not any(x >= n for x in a_values) and n < 1000:
            if k > 0: a_values[random.randint(0, k - 1)] = random.randint(n, 1000)
            else: a_values.append(random.randint(n, 1000))

        # Add 0, 1000, or n with some probability to ensure coverage of these specific values
        if random.random() < 0.1:
            if k > 0: a_values[random.randint(0, k - 1)] = 0
            else: a_values.append(0)
        if random.random() < 0.1:
            if k > 0: a_values[random.randint(0, k - 1)] = 1000
            else: a_values.append(1000)
        if random.random() < 0.1:
            if k > 0: a_values[random.randint(0, k - 1)] = n
            else: a_values.append(n)
            
    # Final adjustments to ensure k matches requested and values are valid
    a_values = a_values[:k]
    while len(a_values) < k: # Ensure list has 'k' elements even if generation logic failed to produce enough
        a_values.append(random.randint(0, 1000))
    if not a_values: # Should not happen with k >= 1 as per problem constraints
        a_values = [500] # Fallback to a single valid value
        k = 1
    
    return f"{n} {k}\n" + " ".join(map(str, a_values)) + "\n"


def check(stdin: str, stdout: str) -> None:
    # 1. Parse input
    lines = stdin.strip().split('\n')
    n, k = map(int, lines[0].split())
    a = list(map(int, lines[1].split()))

    # 2. Parse output
    try:
        result = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not an integer: '{stdout}' for input:\n{stdin}")

    # 3. Format/Shape/Range invariants
    # If not -1, result must be a positive integer
    if result != -1:
        assert result >= 1, f"Expected a positive volume or -1, but got {result} for input:\n{stdin}"

    # 4. Certificate checks / Hard constraints

    # Property 1: If n is one of the a_i, the answer must be 1.
    if n in a:
        assert result == 1, f"If target concentration {n} is available, expected volume 1, but got {result} for input:\n{stdin}"
        return # This is a definitive answer, no need for further checks if V=1 is required

    # Get min/max a_i for range checks
    min_a = min(a)
    max_a = max(a)

    # Property 2: If all a_i are strictly less than n OR all a_i are strictly greater than n, it's impossible.
    # Case a: all a_i > n
    if min_a > n: 
        assert result == -1, f"All concentrations {a} are greater than target {n}, expected -1, but got {result} for input:\n{stdin}"
    
    # Case b: all a_i < n
    if max_a < n: 
        assert result == -1, f"All concentrations {a} are less than target {n}, expected -1, but got {result} for input:\n{stdin}"

    # Property 3: Upper bound for positive results
    # For integer `a_i` and `n` in [0, 1000], the minimum total volume `V` is at most 1000 if a solution exists.
    # This upper bound is observed in competitive programming problems of this structure,
    # as the maximum absolute difference (1000) limits the necessary coefficients (volumes) for balancing.
    if result != -1:
        assert result <= 1000, f"If a solution exists, minimum volume should be <= 1000, but got {result} for input:\n{stdin}"

    # Property 4: Check for V=2 solution possibility (if V=1 is not possible)
    # This means finding v1, v2 >= 0 such that v1 + v2 = 2 and v1*(a_x-n) + v2*(a_y-n) = 0.
    # Since V=1 is already handled by Property 1 (if n in a), we are now only checking for solutions where n is NOT in `a`.
    # The only way to get V=2 when n is not in `a` is if 1*(a_x-n) + 1*(a_y-n) = 0 for some a_x, a_y from the input.
    # This simplifies to a_x + a_y = 2n.
    # If such a combination exists, a solution with V=2 is possible. In this case, the program must not output -1.
    found_v2_solution_candidate = False
    # Use a set for faster lookup of required complements
    a_set = set(a)
    
    for val1 in a:
        # We need val2 such that val1 + val2 = 2n => val2 = 2n - val1
        val2_required = 2 * n - val1
        # Check if val2_required is within valid concentration range and available in input 'a'
        if 0 <= val2_required <= 1000 and val2_required in a_set:
            found_v2_solution_candidate = True
            break
    
    if found_v2_solution_candidate:
        # If a V=2 solution candidate exists and n is not in `a` (guaranteed by the 'return' in Prop 1),
        # then the program should NOT return -1.
        assert result != -1, f"Found a solution with V=2 (e.g. {val1} + {val2_required} = 2*{n}), but program returned -1 for input:\n{stdin}"