import random

def gen_input() -> str:
    parts = []

    # N: number of jury members (cities 1 to N)
    # M: number of flights
    # K: duration of work in Metropolis
    
    # Scale choices for N, M, K to cover various input sizes
    scale_n = random.choices(['small', 'medium', 'large'], weights=[0.2, 0.5, 0.3])[0]
    scale_m = random.choices(['very_small', 'small', 'medium', 'large'], weights=[0.05, 0.15, 0.4, 0.4])[0]
    scale_k = random.choices(['small', 'medium', 'large', 'extreme'], weights=[0.2, 0.4, 0.3, 0.1])[0]

    if scale_n == 'small':
        n = random.randint(1, 5)
    elif scale_n == 'medium':
        n = random.randint(5, 100) 
    else: # large
        n = random.randint(100, 10**5)
    
    if scale_m == 'very_small':
        # Cases where M is clearly not enough for all members (e.g., M=0, or M < 2*N)
        m = random.randint(0, max(0, 2 * n - 1)) # max(0, ...) to ensure m is non-negative
        
    elif scale_m == 'small':
        # Just enough flights for N members to have some options, but not many choices
        m = random.randint(2 * n, 2 * n + 100) 
    elif scale_m == 'medium':
        m = random.randint(2 * n + 100, 1000)
    else: # large
        m = random.randint(1000, 10**5)
    
    if scale_k == 'small':
        k = random.randint(1, 5)
    elif scale_k == 'medium':
        k = random.randint(5, 100)
    elif scale_k == 'large':
        k = random.randint(100, 10**4)
    else: # extreme
        k = random.randint(10**4, 10**6)

    parts.append(f"{n} {m} {k}")

    max_d = 10**6
    max_c = 10**6

    all_flights = []

    # Generate "core" flights for each city if M allows for at least one arrival/departure per member.
    # This helps in creating potentially solvable test cases and specific timing challenges.
    if m >= 2 * n:
        scenario_type = random.choices(['wide', 'tight', 'impossible_day_overlap'], weights=[0.6, 0.3, 0.1])[0]

        min_arrival_day_bound = 1
        max_departure_day_bound = max_d

        if scenario_type == 'wide':
            # Arrival days early, departure days late, plenty of buffer for K days
            min_arrival_day_bound = random.randint(1, max_d // 10)
            target_dep_day = min_arrival_day_bound + k + max_d // 4
            max_departure_day_bound = random.randint(target_dep_day, max_d)
            if max_departure_day_bound < target_dep_day: max_departure_day_bound = target_dep_day # Ensure minimum
            
        elif scenario_type == 'tight':
            # Arrival and departure days closer, just enough for K days
            # max_possible_arr_day ensures that even if min_dep_day is max_d, there's a k+1 day gap
            max_possible_arr_day = max_d - (k + 1) - 1 
            if max_possible_arr_day < 1: max_possible_arr_day = 1

            min_arrival_day_bound = random.randint(1, max_possible_arr_day) 
            
            # max_departure_day_bound should be at least min_arrival_day_bound + k + 1
            min_dep_day_required = min_arrival_day_bound + k + 1
            max_departure_day_bound = random.randint(min_dep_day_required, min_dep_day_required + 5)
            if max_departure_day_bound > max_d: max_departure_day_bound = max_d
            if max_departure_day_bound < min_dep_day_required: max_departure_day_bound = min_dep_day_required 
        
        else: # 'impossible_day_overlap' (makes timing for core flights difficult/impossible)
            # Create a situation where the best possible common interval for K days is unlikely to be met.
            # Set a latest acceptable arrival day (D_arr_max_target) and earliest departure day (D_dep_min_target)
            # such that D_dep_min_target - D_arr_max_target <= k (or close to it).
            D_arr_max_target = random.randint(1, max_d - k - 1)
            D_dep_min_target = random.randint(D_arr_max_target + 1, D_arr_max_target + k)
            
            min_arrival_day_bound = random.randint(1, D_arr_max_target)
            max_departure_day_bound = random.randint(D_dep_min_target, max_d)
            if max_departure_day_bound < D_dep_min_target: max_departure_day_bound = D_dep_min_target
            if min_arrival_day_bound >= max_departure_day_bound - (k + 1): # Adjust if accidentally possible
                min_arrival_day_bound = max(1, max_departure_day_bound - (k + 1) - random.randint(1, 5))

        for city_id in range(1, n + 1):
            # Arrival flight for city_id to Metropolis (city 0)
            d_arr = random.randint(1, min_arrival_day_bound)
            c_arr = random.randint(1, max_c // 2) # Core flights can be relatively cheap
            all_flights.append((d_arr, city_id, 0, c_arr))

            # Departure flight for city_id from Metropolis (city 0)
            d_dep = random.randint(max_departure_day_bound, max_d)
            c_dep = random.randint(1, max_c // 2) # Core flights can be relatively cheap
            all_flights.append((d_dep, 0, city_id, c_dep))

    # Add remaining flights as "noise" or alternatives
    remaining_flights_to_add = m - len(all_flights)
    for _ in range(remaining_flights_to_add):
        d = random.randint(1, max_d)
        c = random.randint(1, max_c)
        if random.random() < 0.5: # Flight to Metropolis
            f = random.randint(1, n)
            t = 0
        else: # Flight from Metropolis
            f = 0
            t = random.randint(1, n)
        all_flights.append((d, f, t, c))

    random.shuffle(all_flights) # Shuffle to mix core and noise flights, and randomize order

    for d, f, t, c in all_flights: # Print exactly M flights
        parts.append(f"{d} {f} {t} {c}")

    return "\n".join(parts) + "\n"


def check(stdin: str, stdout: str) -> None:
    # Parse input
    lines = stdin.strip().split('\n')
    n, m, k = map(int, lines[0].split())
    
    flights_data = []
    # Only parse up to 'm' flights. Some very_small M cases might have less lines if m=0.
    for i in range(1, min(m + 1, len(lines))):
        d, f, t, c = map(int, lines[i].split())
        flights_data.append((d, f, t, c))

    # Parse output
    try:
        program_output = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout.strip()}'")

    # Property 1: Output value range and sign
    if program_output != -1:
        if program_output < 0:
            raise AssertionError(f"Program output a negative cost ({program_output}) but not -1.")
        # Maximum possible cost is 2 * 10^5 * 10^6 = 2 * 10^11. This fits in Python's arbitrary-precision integers.
        
    # Property 2: Calculate a lower bound on cost and check for fundamental impossibility
    # Initialize min_arrival_cost and min_departure_cost for each city 1..n
    # Use float('inf') to represent unreachable cities or missing flight types
    min_arrival_cost = [float('inf')] * (n + 1)
    min_departure_cost = [float('inf')] * (n + 1)

    for d, f, t, c in flights_data:
        if t == 0:  # Flight to Metropolis (arrival for city f)
            min_arrival_cost[f] = min(min_arrival_cost[f], c)
        elif f == 0: # Flight from Metropolis (departure for city t)
            min_departure_cost[t] = min(min_departure_cost[t], c)
        # Note: The problem statement guarantees 'exactly one of f_i and t_i equals zero',
        # so no other cases for flights need to be handled.

    total_min_possible_cost_lower_bound = 0
    is_fundamentally_impossible = False

    for city_id in range(1, n + 1):
        if min_arrival_cost[city_id] == float('inf') or min_departure_cost[city_id] == float('inf'):
            is_fundamentally_impossible = True
            break
        total_min_possible_cost_lower_bound += min_arrival_cost[city_id] + min_departure_cost[city_id]
    
    # Assertions based on fundamental impossibility and lower bound
    if is_fundamentally_impossible:
        # If any city lacks a required flight (arrival or departure), it's impossible.
        # The program MUST output -1.
        if program_output != -1:
            raise AssertionError(
                f"Program output {program_output} (not -1) "
                f"even though at least one city (1..{n}) cannot arrive/depart Metropolis due to missing flights. "
                f"Input: N={n}, K={k}, M={m}."
            )
    else: 
        # If every city has at least one arrival and one departure flight option, 
        # then a solution is fundamentally possible, but might be impossible due to timing (k days).
        if program_output != -1:
            # If the program found a solution, its cost must be at least the sum of the cheapest individual
            # arrival and departure flights for each city.
            if program_output < total_min_possible_cost_lower_bound:
                raise AssertionError(
                    f"Program output {program_output} which is less than "
                    f"the theoretical minimum lower bound {total_min_possible_cost_lower_bound}. "
                    f"Input: N={n}, K={k}, M={m}."
                )
        # If program_output is -1 here, it means the program determined it's impossible due to timing
        # constraints for K days. This is a valid outcome and cannot be verified without re-solving
        # the problem's core logic, which is avoided for soundness. So, no assertion is made.