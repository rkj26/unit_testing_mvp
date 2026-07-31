import random
import io
from collections import defaultdict

def gen_input() -> str:
    # Generate N and M, preferring larger values to test scalability and boundary conditions.
    # N and M range from 2 to 10^5.
    n = random.choices([2, 3, 10, 100, 1000, 10000, 100000], weights=[5, 5, 10, 15, 20, 20, 25])[0]
    m = random.choices([2, 3, 10, 100, 1000, 10000, 100000], weights=[5, 5, 10, 15, 20, 20, 25])[0]

    # Initialize room states randomly.
    r = [random.randint(0, 1) for _ in range(n)]

    # Data structures to build the switch-room connections and facilitate property generation.
    # room_to_controlling_switches[room_idx] = [s1_idx, s2_idx] (0-indexed switch numbers)
    room_to_controlling_switches = [[] for _ in range(n)]
    # switch_to_controlled_rooms_sets[s_idx] = set of 1-indexed room numbers
    switch_to_controlled_rooms_sets = [set() for _ in range(m)]
    # paired_rooms_map: Key=frozenset({s1_idx, s2_idx}), Value=list of 0-indexed room numbers
    paired_rooms_map = defaultdict(list)

    # Assign two distinct switches to each room to satisfy the problem guarantee.
    for room_idx in range(n):
        s1 = random.randrange(m)
        s2 = random.randrange(m)
        while s1 == s2: # Ensure distinct switches control a room
            s2 = random.randrange(m)
        
        # Store for internal checks and later output formatting (0-indexed switches)
        room_to_controlling_switches[room_idx] = sorted([s1, s2])
        paired_rooms_map[frozenset({s1, s2})].append(room_idx)

        # Store for output formatting (1-indexed room numbers)
        switch_to_controlled_rooms_sets[s1].add(room_idx + 1)
        switch_to_controlled_rooms_sets[s2].add(room_idx + 1)
    
    # Introduce specific conflicts for property checking with a certain probability.
    # If a pair of switches controls multiple rooms, ensure their initial states
    # sometimes conflict (forcing a "NO" answer), and sometimes are consistent.
    for pair_frozenset, room_list_0_idx in paired_rooms_map.items():
        if len(room_list_0_idx) > 1:
            if random.random() < 0.3: # 30% chance to force a conflict for this specific pair
                r[room_list_0_idx[0]] = 0
                r[room_list_0_idx[1]] = 1 # Make the first two rooms of this group have conflicting states
            else: # Otherwise, ensure all rooms controlled by this pair have the same state.
                  # This removes this specific conflict as a reason for "NO" but doesn't guarantee "YES".
                common_val = random.randint(0, 1)
                for room_0_idx in room_list_0_idx:
                    r[room_0_idx] = common_val
        # For rooms controlled by a unique pair of switches, their 'r' values remain random.

    # Construct the STDIN string.
    input_lines = [f"{n} {m}"]
    input_lines.append(" ".join(map(str, r)))
    for i in range(m):
        rooms = sorted(list(switch_to_controlled_rooms_sets[i]))
        input_lines.append(f"{len(rooms)} {' '.join(map(str, rooms))}")
    
    return "\n".join(input_lines) + "\n"

def check(stdin: str, stdout: str) -> None:
    # Property 1: The output must be either "YES" or "NO".
    assert stdout.strip() in ["YES", "NO"], f"Output must be 'YES' or 'NO', got '{stdout.strip()}'"

    # Property 2: If multiple rooms are controlled by the exact same pair of switches,
    # their initial states (r_i) must be identical for a solution to exist.
    # If they have different initial states, it is impossible to unlock all doors,
    # and the program *must* output "NO".

    input_stream = io.StringIO(stdin)
    
    n, m = map(int, input_stream.readline().split())
    initial_room_states = list(map(int, input_stream.readline().split()))
    
    # Reconstruct which two switches control each room from the input.
    # room_to_controlling_switches[room_0_idx] will store a list of two 0-indexed switch numbers.
    room_to_controlling_switches = [[] for _ in range(n)]

    for switch_idx in range(m):
        line_parts = list(map(int, input_stream.readline().split()))
        # num_rooms_controlled = line_parts[0] # Not strictly needed for this check
        rooms_controlled_by_switch = line_parts[1:] # These are 1-indexed room numbers

        for room_1_idx in rooms_controlled_by_switch:
            room_0_idx = room_1_idx - 1
            # Add this switch (0-indexed) to the list for the current room
            room_to_controlling_switches[room_0_idx].append(switch_idx)
    
    # This assertion is to self-verify gen_input's adherence to the problem statement,
    # not a check on the model's output directly.
    for room_0_idx in range(n):
        assert len(room_to_controlling_switches[room_0_idx]) == 2, \
               f"Internal error in test generation: Room {room_0_idx+1} is controlled by " \
               f"{len(room_to_controlling_switches[room_0_idx])} switches, expected 2 as per problem statement."

    # Group rooms by the *pair* of switches that control them.
    # Key: frozenset({s1_idx, s2_idx}), Value: list of 0-indexed room numbers
    paired_rooms_map = defaultdict(list)
    for room_0_idx in range(n):
        # Sort the switch indices to create a canonical key for the pair
        s1_idx, s2_idx = sorted(room_to_controlling_switches[room_0_idx])
        paired_rooms_map[frozenset({s1_idx, s2_idx})].append(room_0_idx)
    
    # Check for contradictions:
    # If a single pair of switches controls multiple rooms, and those rooms have
    # different initial states, then it's impossible to satisfy their conditions simultaneously.
    # For example, if rooms A and B are both controlled by (S1, S2):
    # - If r_A=0, r_B=1: We need S1^S2 = 1^0 = 1 for room A.
    #   And we need S1^S2 = 1^1 = 0 for room B.
    #   S1^S2 cannot be both 1 and 0, so this is an immediate contradiction.
    
    forced_no_by_contradiction = False
    for pair_frozenset, room_0_indices_list in paired_rooms_map.items():
        if len(room_0_indices_list) > 1: # This pair of switches controls more than one room
            # Get the initial state of the first room in this group
            first_room_state = initial_room_states[room_0_indices_list[0]]
            # Check if any other room in this group has a different initial state
            for i in range(1, len(room_0_indices_list)):
                if initial_room_states[room_0_indices_list[i]] != first_room_state:
                    # Contradiction found! This input configuration makes it impossible to succeed.
                    forced_no_by_contradiction = True
                    break # Stop checking rooms for this pair
            if forced_no_by_contradiction:
                break # Stop checking other switch pairs, as a "NO" is already certain

    if forced_no_by_contradiction:
        # If a contradiction was found, the program's output *must* be "NO".
        assert stdout.strip() == "NO", \
               f"Input contains contradictory room states (rooms controlled by same switch pair have different initial states), " \
               f"but the program output was '{stdout.strip()}'. Expected 'NO'."