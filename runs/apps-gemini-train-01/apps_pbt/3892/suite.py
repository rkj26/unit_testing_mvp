import random
import math

def gen_input() -> str:
    # Constraints: 2 <= n <= 100; 1 <= m <= 200
    # a_i, b_i: 1 <= a_i, b_i <= n; a_i != b_i

    # Strategy for input generation:
    # Deliberately cover minimum/maximum sizes, extreme values, and specific patterns
    # that might expose hidden divergences.

    test_type = random.randint(0, 9)

    if test_type == 0: # Minimum n, m
        n = 2
        m = 1
    elif test_type == 1: # Maximum n, m
        n = 100
        m = 200
    elif test_type == 2: # n small (2-5), m max (200)
        n = random.randint(2, 5)
        m = 200
    elif test_type == 3: # n max (100), m small (1-5)
        n = 100
        m = random.randint(1, 5)
    elif test_type == 4: # Random n, m within constraints
        n = random.randint(2, 100)
        m = random.randint(1, 200)
    elif test_type == 5: # Candies heavily concentrated at one station
        n = random.randint(2, 100)
        m = random.randint(1, 200)
        fixed_a = random.randint(1, n)
        candies = []
        for _ in range(m):
            b = random.randint(1, n)
            while b == fixed_a: # Ensure a_i != b_i
                b = random.randint(1, n)
            candies.append(f"{fixed_a} {b}")
        return f"{n} {m}\n" + "\n".join(candies) + "\n"
    elif test_type == 6: # Candies always going to the next station (shortest travel time post-pickup)
        n = random.randint(2, 100)
        m = random.randint(1, 200)
        candies = []
        for _ in range(m):
            a = random.randint(1, n)
            b = (a % n) + 1 # Next station in circular order
            candies.append(f"{a} {b}")
        return f"{n} {m}\n" + "\n".join(candies) + "\n"
    elif test_type == 7: # Candies always going to the previous station (longest travel time post-pickup, n-1)
        n = random.randint(2, 100)
        m = random.randint(1, 200)
        candies = []
        for _ in range(m):
            a = random.randint(1, n)
            b = ((a - 2 + n) % n) + 1 # Previous station in circular order (e.g., 1 goes to n)
            candies.append(f"{a} {b}")
        return f"{n} {m}\n" + "\n".join(candies) + "\n"
    elif test_type == 8: # Candies concentrated on two specific stations
        n = random.randint(2, 100)
        m = random.randint(1, 200)
        station1 = random.randint(1, n)
        station2 = random.randint(1, n)
        while station1 == station2:
            station2 = random.randint(1, n) # Ensure two distinct stations
        
        candies = []
        for i in range(m):
            # Roughly split candies between the two stations
            a = station1 if i < m // 2 else station2
            b = random.randint(1, n)
            while b == a: # Ensure a_i != b_i
                b = random.randint(1, n)
            candies.append(f"{a} {b}")
        return f"{n} {m}\n" + "\n".join(candies) + "\n"
    else: # General random case (fall-through if not one of the specific types)
        n = random.randint(2, 100)
        m = random.randint(1, 200)

    candies = []
    for _ in range(m):
        a = random.randint(1, n)
        b = random.randint(1, n)
        while a == b: # Ensure a_i != b_i
            b = random.randint(1, n)
        candies.append(f"{a} {b}")

    return f"{n} {m}\n" + "\n".join(candies) + "\n"


def check(stdin: str, stdout: str) -> None:
    input_lines = stdin.strip().split('\n')
    n, m = map(int, input_lines[0].split())
    
    candies_data = []
    for i in range(1, m + 1):
        a, b = map(int, input_lines[i].split())
        candies_data.append((a, b))

    # --- Property 1: Output format and basic value ranges ---
    output_parts = stdout.strip().split()
    assert len(output_parts) == n, \
        f"Output should contain exactly {n} space-separated integers, but found {len(output_parts)}."

    actual_times = []
    for part in output_parts:
        try:
            time_val = int(part)
            actual_times.append(time_val)
        except ValueError:
            raise AssertionError(f"Output part '{part}' is not a valid integer.")
        
        # Time must be positive since m >= 1 and a_i != b_i ensures at least 1 second travel.
        assert time_val >= 1, f"Time value {time_val} for a starting station must be at least 1."
        
        # A loose upper bound: In the worst case, for each of m candies, it might take N-1 time
        # to deliver. Plus, a station with m candies would require (m-1)*N extra loops.
        # Max (m-1)*N + N-1 (max travel for last candy) + N-1 (max travel to pick up)
        # Roughly, 2 * m * N is a safe upper bound. (e.g. 2*200*100 = 40000)
        assert time_val <= 2 * m * n, \
            f"Time value {time_val} exceeds a generous upper bound of {2 * m * n}."

    # --- Property 2: Correctness using a derived optimal time formula (Certificate Check) ---
    # The optimal time for a given starting station S is determined by the "bottleneck" station 'u'.
    # A station 'u' with `k` candies requires `k` visits for pickup. The `(k-1)` extra visits
    # each imply a full train cycle of `n` seconds. Plus, the initial travel from S to u,
    # and finally the minimum travel time for a candy from u to its destination.
    # The total time is the maximum of these values over all stations 'u' that have candies.

    # Helper function for circular travel time (clockwise)
    def get_travel_time(start_station, end_station, num_stations):
        if start_station == end_station:
            return 0
        return (end_station - start_station + num_stations) % num_stations

    # Step 1: Aggregate candy information
    # candies_at_station[u] stores the count of candies originating at station u.
    # min_delivery_travel[u] stores the minimum time to deliver ANY candy that starts at station u.
    candies_at_station = [0] * (n + 1) # Stations are 1-indexed
    min_delivery_travel = [math.inf] * (n + 1) # Initialize with infinity

    for a, b in candies_data:
        candies_at_station[a] += 1
        travel_a_to_b = get_travel_time(a, b, n)
        min_delivery_travel[a] = min(min_delivery_travel[a], travel_a_to_b)

    # Step 2: Calculate expected minimum time for each starting station S
    expected_times = []
    for S in range(1, n + 1): # Iterate for each possible starting station S (1 to n)
        max_time_for_S = 0

        # Iterate through all stations 'u' to find the bottleneck
        for u in range(1, n + 1):
            if candies_at_station[u] > 0: # Only consider stations that have candies
                # Calculate the time associated with station 'u' being the bottleneck:
                # 1. (candies_at_station[u] - 1) * n: Time for all but the first pickup at 'u'
                #    (each requiring a full cycle of n seconds to revisit 'u').
                # 2. get_travel_time(S, u, n): Time for the train to reach 'u' for its first pickup,
                #    starting from S.
                # 3. min_delivery_travel[u]: Time to deliver one of the candies from 'u' to its closest destination.
                time_component_for_u = (candies_at_station[u] - 1) * n \
                                     + get_travel_time(S, u, n) \
                                     + min_delivery_travel[u]
                
                max_time_for_S = max(max_time_for_S, time_component_for_u)
        
        expected_times.append(max_time_for_S)

    # Final assertion: The program's output must exactly match the calculated optimal times
    assert actual_times == expected_times, \
        f"Mismatch in calculated optimal times for starting stations.\n" \
        f"Expected: {expected_times}\n" \
        f"Actual:   {actual_times}\n" \
        f"Input: {stdin.strip()}"