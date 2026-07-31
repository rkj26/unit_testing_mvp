import random
import string
from collections import defaultdict

def gen_input() -> str:
    # Constraints:
    # n: 1 to 300
    # a, b: 1 to 100, 1 <= b < a
    # k: 0 to 300
    # f: 1 to 1000
    # Stop names: 1 to 20 letters (upper/lower case English letters, distinct)

    n = random.randint(1, 300)
    # Ensure a > b
    a = random.randint(2, 100)
    b = random.randint(1, a - 1)
    k = random.randint(0, 300)
    f = random.randint(1, 1000)

    # Introduce some edge cases for parameters
    if random.random() < 0.1: # 10% chance for minimal n
        n = 1
    if random.random() < 0.1: # 10% chance for no travel cards
        k = 0
    if random.random() < 0.1: # 10% chance for max k (can cover many routes)
        k = 300
    if random.random() < 0.05: # 5% chance for b very close to a
        a = random.randint(2, 100)
        b = a - 1
    if random.random() < 0.05: # 5% chance for f very cheap
        f = 1
    if random.random() < 0.05: # 5% chance for f very expensive
        f = random.randint(900, 1000) # Ensures f is often larger than typical trip costs

    input_lines = [f"{n} {a} {b} {k} {f}"]

    # Pool of existing stop names to reuse
    existing_stops = []
    prev_end_stop = None

    def generate_random_stop_name():
        length = random.randint(1, 20)
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    for i in range(n):
        start_stop = None
        end_stop = None

        # Determine start stop:
        # For the first trip, or sometimes for non-transshipment trips, pick a new or existing random stop.
        # Otherwise (higher chance), try to make a transshipment.
        if i == 0 or (random.random() < 0.4 and len(existing_stops) > 0): # 40% chance of random start for subsequent trips
            if not existing_stops or random.random() < 0.3: # 30% chance to introduce a new start stop
                start_stop = generate_random_stop_name()
            else:
                start_stop = random.choice(existing_stops)
        else: # Attempt transshipment
            if prev_end_stop is not None:
                start_stop = prev_end_stop
            else: # Fallback if no prev_end_stop (shouldn't happen for i>0 with n>=1)
                start_stop = generate_random_stop_name()

        # Determine end stop:
        # Ensure end_stop is different from start_stop.
        # Sometimes introduce a new end stop, sometimes pick from existing.
        possible_end_stops = [s for s in existing_stops if s != start_stop]
        
        if not possible_end_stops or random.random() < 0.3: # 30% chance to introduce a new end stop
            end_stop = generate_random_stop_name()
            while end_stop == start_stop: # Ensure start and end are different
                end_stop = generate_random_stop_name()
        else:
            end_stop = random.choice(possible_end_stops)
        
        # Add new stops to the pool
        if start_stop not in existing_stops:
            existing_stops.append(start_stop)
        if end_stop not in existing_stops:
            existing_stops.append(end_stop)

        input_lines.append(f"{start_stop} {end_stop}")
        prev_end_stop = end_stop

    return "\n".join(input_lines) + "\n"

def check(stdin: str, stdout: str) -> None:
    # 1. Parse stdin to extract problem parameters and trip details.
    lines = stdin.strip().split('\n')
    n_str, a_str, b_str, k_str, f_str = lines[0].split()
    n, a, b, k, f = int(n_str), int(a_str), int(b_str), int(k_str), int(f_str)

    trips = []
    for i in range(1, n + 1):
        start, end = lines[i].split()
        trips.append((start, end))

    # 2. Parse stdout to get the program's reported total cost.
    try:
        total_cost = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer. Got: '{stdout.strip()}'")

    # --- Properties to check ---

    # Property 1: The total cost cannot be negative.
    assert total_cost >= 0, f"Total cost cannot be negative. Got: {total_cost}"

    # Calculate `cost_no_cards`: The total cost if no travel cards are purchased.
    # This is a deterministic calculation based on the problem rules for individual trip costs.
    cost_no_cards = 0
    prev_end = None
    
    # This dictionary will store the base costs for each unique route (normalized).
    # It's used later to calculate potential savings for the theoretical lower bound.
    # Key: tuple(sorted((stop1, stop2))) representing the route.
    # Value: list of individual base costs for trips on this route.
    route_base_costs_map = defaultdict(list) 

    for i in range(n):
        current_start, current_end = trips[i]
        
        current_trip_base_cost = 0
        if i == 0:
            current_trip_base_cost = a
        else:
            if current_start == prev_end:
                current_trip_base_cost = b
            else:
                current_trip_base_cost = a
        
        cost_no_cards += current_trip_base_cost
        prev_end = current_end

        # Normalize route name: A route from X to Y is the same as Y to X.
        # Use a sorted tuple to represent the unique route identifier.
        route_name_normalized = tuple(sorted((current_start, current_end)))
        route_base_costs_map[route_name_normalized].append(current_trip_base_cost)

    # Property 2: The program's total cost must be less than or equal to `cost_no_cards`.
    # This is an upper bound, as buying travel cards can only reduce or maintain the cost.
    assert total_cost <= cost_no_cards, \
        f"Total cost ({total_cost}) should not exceed cost without any cards ({cost_no_cards})."

    # Property 3: If no travel cards are allowed (k=0), the cost must be exactly `cost_no_cards`.
    if k == 0:
        assert total_cost == cost_no_cards, \
            f"With k=0 (no cards allowed), cost must be exactly cost_no_cards. Got {total_cost}, expected {cost_no_cards}."
    
    # Property 4: If the cost of a single travel card `f` is greater than or equal to `cost_no_cards`,
    # it's never optimal to buy any card. In this case, the total cost must be `cost_no_cards`.
    # (Note: `n >= 1` and `a >= 1`, so `cost_no_cards` is always positive).
    if f >= cost_no_cards:
        assert total_cost == cost_no_cards, \
            f"If card cost f ({f}) is >= total cost without cards ({cost_no_cards}), it's never optimal to buy. " \
            f"Got {total_cost}, expected {cost_no_cards}."

    # Property 5: The program's total cost must be greater than or equal to a theoretical lower bound.
    # This lower bound is calculated by considering the maximum possible savings.
    # The maximum possible savings come from greedily picking up to `k` travel cards
    # for routes that offer the highest *net* savings (total trip costs on that route minus `f`).
    
    potential_net_savings_per_card = []
    for route_name_normalized, individual_trip_base_costs in route_base_costs_map.items():
        # Sum of all individual trip costs that use this specific route, if no card was bought for it.
        total_base_cost_on_this_route = sum(individual_trip_base_costs)
        
        # Net savings if a card is bought for this route: (money saved on trips) - (card cost)
        net_savings_for_this_route = total_base_cost_on_this_route - f
        
        # Only consider cards that yield a positive net saving
        if net_savings_for_this_route > 0:
            potential_net_savings_per_card.append(net_savings_for_this_route)
    
    # Sort the potential net savings in descending order to pick the most profitable `k` cards.
    potential_net_savings_per_card.sort(reverse=True)
    
    total_max_net_savings = 0
    # Sum the top `k` positive net savings (or fewer if less than `k` profitable routes exist).
    for i in range(min(k, len(potential_net_savings_per_card))):
        total_max_net_savings += potential_net_savings_per_card[i]
            
    # The theoretical lower bound cost is the `cost_no_cards` minus these maximum possible net savings.
    theoretical_lower_bound_cost = cost_no_cards - total_max_net_savings

    assert total_cost >= theoretical_lower_bound_cost, \
        f"Total cost ({total_cost}) should be at least the theoretical lower bound ({theoretical_lower_bound_cost}). " \
        f"(Cost without cards: {cost_no_cards}, Max possible net savings: {total_max_net_savings})."