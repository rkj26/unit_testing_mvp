from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str  (the harness provides this)
import random
import collections

# --- Input Generation Strategies ---

@st.composite
def make_input_general(draw):
    """
    Generates a general input with a mix of small and large 'n', and 'a_i' values,
    including scenarios designed to create duplicates and specific problematic patterns
    with a certain probability.
    """
    n = draw(st.integers(min_value=1, max_value=1000)) # Balance test coverage with performance for 'n'
    
    # Prioritize smaller values and duplicates for easier detection of pattern-based wins/losses,
    # but also include large values to test general logic and value range.
    a_strat = st.one_of(
        st.integers(min_value=0, max_value=10),
        st.integers(min_value=0, max_value=100),
        st.integers(min_value=0, max_value=10**9) # Max a_i value
    )
    a_list = draw(st.lists(a_strat, min_size=n, max_size=n))
    
    # Introduce specific duplicate patterns to increase test coverage of these critical cases
    if n >= 2 and draw(st.booleans(average_value=0.3)): # ~30% chance for specific duplicate patterns
        pattern_type = draw(st.integers(min_value=0, max_value=3))
        
        if pattern_type == 0: # Three or more identical piles
            val_strat = st.integers(min_value=0, max_value=min(100, 10**9)) # Keep value small for commonality
            val = draw(val_strat)
            k = draw(st.integers(min_value=3, max_value=min(n, 5))) # 3 to 5 duplicates
            indices = draw(st.sampled_from(list(range(n))), size=k, unique=True)
            for idx in indices:
                a_list[idx] = val
        elif pattern_type == 1: # Two zero piles
            indices = draw(st.sampled_from(list(range(n))), size=2, unique=True)
            a_list[indices[0]] = 0
            a_list[indices[1]] = 0
        elif pattern_type == 2 and n >= 3: # One pair (X,X) and X-1 is present
            x_val_strat = st.integers(min_value=1, max_value=min(100, 10**9)) # X > 0, keep value small
            x_val = draw(x_val_strat)
            indices = draw(st.sampled_from(list(range(n))), size=3, unique=True)
            a_list[indices[0]] = x_val - 1
            a_list[indices[1]] = x_val
            a_list[indices[2]] = x_val
        elif pattern_type == 3 and n >= 4: # Two distinct pairs
            val1_strat = st.integers(min_value=0, max_value=min(100, 10**9))
            val2_strat = st.integers(min_value=0, max_value=min(100, 10**9))
            val1 = draw(val1_strat)
            val2 = draw(val2_strat)
            while val1 == val2: # Ensure distinct values for pairs
                val2 = draw(val2_strat)
            indices = draw(st.sampled_from(list(range(n))), size=4, unique=True)
            a_list[indices[0]] = val1
            a_list[indices[1]] = val1
            a_list[indices[2]] = val2
            a_list[indices[3]] = val2

    draw(st.randoms()).shuffle(a_list) # Shuffle to avoid any implicit ordering assumptions
    return f"{n}\n{' '.join(map(str, a_list))}\n"

@st.composite
def make_input_n1(draw):
    """Generates an input with exactly one pile (n=1)."""
    a1 = draw(st.integers(min_value=0, max_value=10**9))
    return f"1\n{a1}\n"

@st.composite
def make_input_unique_piles(draw):
    """
    Generates an input where all pile sizes are guaranteed to be unique.
    This is used to test the core Nim-like XOR sum logic.
    """
    n = draw(st.integers(min_value=1, max_value=1000))
    # Max value ensures enough range for unique integers, up to 10^9
    max_possible_val = (n - 1) + draw(st.integers(min_value=0, max_value=10**9))
    a_list = draw(st.lists(st.integers(min_value=0, max_value=max_possible_val), min_size=n, max_size=n, unique=True))
    draw(st.randoms()).shuffle(a_list)
    return f"{n}\n{' '.join(map(str, a_list))}\n"

@st.composite
def make_input_one_pair_no_X_minus_1(draw):
    """
    Generates an input with exactly one pair (X,X) such that X > 0 and X-1 is not present
    among the other piles. This targets a specific tricky game state.
    """
    n = draw(st.integers(min_value=2, max_value=1000)) # Need at least 2 for a pair
    
    x_val = draw(st.integers(min_value=1, max_value=1000)) # X > 0 is crucial for this case
    
    # Generate remaining n-2 unique piles, ensuring they don't contain X-1 or X
    remaining_vals = set()
    forbidden_values = {x_val - 1, x_val} 
    
    # Generate distinct values for the other piles, avoiding forbidden_values
    attempts = 0
    while len(remaining_vals) < (n - 2) and attempts < 2000: # Max attempts to avoid infinite loops
        val = draw(st.integers(min_value=0, max_value=10**9))
        if val not in forbidden_values and val not in remaining_vals:
            remaining_vals.add(val)
        attempts += 1
    
    if len(remaining_vals) < (n - 2): # Fallback if generating distinct values failed (unlikely for large max_value)
        return draw(make_input_general())

    a_list = list(remaining_vals)
    a_list.extend([x_val, x_val]) # Add the pair

    draw(st.randoms()).shuffle(a_list)
    return f"{n}\n{' '.join(map(str, a_list))}\n"


# --- Helper Functions ---

def parse_input(stdin: str):
    """Parses an stdin string into n and a list of integers."""
    lines = stdin.strip().split('\n')
    n = int(lines[0])
    a_values = list(map(int, lines[1].split()))
    return n, a_values

def _predict_unique_piles_winner_logic(sorted_a: list[int]) -> str:
    """
    Predicts the winner for a game state where all piles are unique.
    This uses the common Nim-like XOR sum transformation: (a_i - (i-1)).
    Assumes `sorted_a` contains unique values and is already sorted.
    Returns "sjfnb\n" if Tokitsukaze wins, "cslnb\n" if CSL wins.
    """
    xor_sum = 0
    for i, val in enumerate(sorted_a):
        xor_sum ^= (val - i)
    return "sjfnb\n" if xor_sum != 0 else "cslnb\n"


# --- Test Functions ---

@given(make_input_general())
@settings(max_examples=200, deadline=None) # Increased max_examples for better coverage
def test_input_order_invariance(stdin):
    """
    Asserts that changing the order of piles in the input does not change the game's outcome.
    A correct solution should implicitly sort the piles or treat them as a multiset.
    """
    n, a_values = parse_input(stdin)
    
    stdout_original = run_candidate(stdin)
    
    # Shuffle the list and create new stdin
    random.shuffle(a_values)
    shuffled_stdin = f"{n}\n{' '.join(map(str, a_values))}\n"
    stdout_shuffled = run_candidate(shuffled_stdin)
    
    assert stdout_original == stdout_shuffled, (
        f"Output changed with shuffled input.\n"
        f"Original input:\n{stdin}\nOutput: {stdout_original}\n"
        f"Shuffled input:\n{shuffled_stdin}\nOutput: {stdout_shuffled}"
    )

@given(make_input_general())
@settings(max_examples=100, deadline=None)
def test_cslnb_if_bad_initial_state(stdin):
    """
    Asserts that CSL wins ("cslnb") if the initial state contains certain
    properties that lead to an immediate loss for Tokitsukaze or force a loss.
    These are direct checks based on the problem's derived losing conditions.
    """
    n, a_values = parse_input(stdin)
    sorted_a = sorted(a_values)
    counts = collections.Counter(sorted_a)

    should_be_cslnb = False

    # Condition 1: Three or more identical piles (e.g., [X,X,X,Y])
    if any(count >= 3 for count in counts.values()):
        should_be_cslnb = True
    
    # Condition 2: Two zero piles (e.g., [0,0,Y,Z])
    if counts[0] >= 2:
        should_be_cslnb = True

    # Condition 3: Two distinct pairs (e.g., [X,X,Y,Y,Z])
    # Tokitsukaze must reduce one pile from one pair. The other pair remains, causing an immediate loss.
    num_pairs = sum(1 for count in counts.values() if count == 2)
    if num_pairs >= 2:
        should_be_cslnb = True

    # Condition 4: Exactly one pair (X,X) and X-1 is also present (e.g., [X-1,X,X,Y])
    # Tokitsukaze must reduce one X to X-1, creating an X-1, X-1 pair.
    elif num_pairs == 1:
        duplicate_val = next(val for val, count in counts.items() if count == 2)
        if duplicate_val > 0 and (duplicate_val - 1) in counts:
            should_be_cslnb = True
    
    if should_be_cslnb:
        stdout = run_candidate(stdin)
        assert stdout == "cslnb\n", (
            f"Expected 'cslnb' for initial losing state, got '{stdout.strip()}' for input:\n{stdin}"
            f"Counts: {counts}"
        )

@given(make_input_unique_piles())
@settings(max_examples=100, deadline=None)
def test_unique_piles_xor_sum_logic(stdin):
    """
    Asserts the outcome for states where all piles are unique, based on the XOR sum logic.
    This verifies the "normal form" of the game when no immediate duplicate-loss conditions apply.
    """
    n, a_values = parse_input(stdin)
    sorted_a = sorted(a_values)
    
    # Sanity check: ensure no duplicates in the generated input (should be guaranteed by strategy)
    if len(set(sorted_a)) != n:
        # If this happens, the input generator is flawed for this test. Skip or raise.
        # For competitive programming, unique=True should guarantee uniqueness.
        print(f"make_input_unique_piles generated non-unique piles, skipping: {stdin}")
        return

    expected_output = _predict_unique_piles_winner_logic(sorted_a)
    stdout = run_candidate(stdin)
    
    assert stdout == expected_output, (
        f"Incorrect output for unique piles (XOR sum logic).\n"
        f"Input:\n{stdin}Sorted A: {sorted_a}\n"
        f"Expected: {expected_output.strip()}\nGot: {stdout.strip()}"
    )

@given(make_input_one_pair_no_X_minus_1())
@settings(max_examples=100, deadline=None)
def test_one_pair_special_case(stdin):
    """
    Asserts the outcome for states with exactly one pair (X,X), where X > 0 and X-1 is NOT present.
    In this scenario, Tokitsukaze makes one optimal move (reducing one X to X-1), then CSL plays first
    on the resulting unique-piles state. The outcome is 'flipped' relative to the standard unique-piles game.
    """
    n, a_values = parse_input(stdin)
    sorted_a_original = sorted(a_values)
    counts = collections.Counter(sorted_a_original)

    # Verify pre-conditions for this test, if generator failed (robustness check)
    num_pairs = sum(1 for count in counts.items() if count[1] == 2)
    if num_pairs != 1:
        print(f"Generator for 'one_pair_no_X_minus_1' produced {num_pairs} pairs, skipping: {stdin}")
        return
    
    duplicate_val = next(val for val, count in counts.items() if count == 2)
    if not (duplicate_val > 0 and (duplicate_val - 1) not in counts):
        print(f"Generator for 'one_pair_no_X_minus_1' produced a case where X=0 or X-1 is present, skipping: {stdin}")
        return

    # Simulate Tokitsukaze's optimal first move: reduce one 'X' to 'X-1'
    simulated_a = list(sorted_a_original)
    
    # Find one 'X' to change and decrement it
    idx_to_change = simulated_a.index(duplicate_val)
    simulated_a[idx_to_change] -= 1
    
    sorted_simulated_a = sorted(simulated_a)
    
    # Sanity check: the simulated state should now consist of all unique piles.
    if len(set(sorted_simulated_a)) != n:
        print(f"Simulated move resulted in duplicates despite conditions, skipping (should be caught by other tests): {stdin}")
        return

    # CSL now moves first on `sorted_simulated_a`.
    # If `_predict_unique_piles_winner_logic` says sjfnb (Tokitsukaze wins if she moves first),
    # then CSL would win this state (since CSL is moving first). So Tokitsukaze loses (cslnb).
    # If it says cslnb (CSL wins if Tokitsukaze moves first),
    # then CSL would lose this state. So Tokitsukaze wins (sjfnb).
    expected_output_for_simulated_state = _predict_unique_piles_winner_logic(sorted_simulated_a)
    
    if expected_output_for_simulated_state == "sjfnb\n":
        expected_output = "cslnb\n" # CSL wins the game from Tokitsukaze's perspective
    else:
        expected_output = "sjfnb\n" # Tokitsukaze wins the game from Tokitsukaze's perspective
    
    stdout = run_candidate(stdin)
    
    assert stdout == expected_output, (
        f"Incorrect output for one-pair special case.\n"
        f"Input:\n{stdin}Sorted A (original): {sorted_a_original}\n"
        f"Simulated A (after Toki's move): {sorted_simulated_a}\n"
        f"Predicted for simulated state (Toki moves first): {expected_output_for_simulated_state.strip()}\n"
        f"Final Expected (Toki's perspective): {expected_output.strip()}\nGot: {stdout.strip()}"
    )


@given(make_input_n1())
@settings(max_examples=50, deadline=None)
def test_n1_specific_outcome(stdin):
    """
    Asserts the specific outcome for the n=1 case.
    If a_1=0, Tokitsukaze cannot move, so CSL wins.
    If a_1 > 0, Tokitsukaze can make a move, and there are never two piles with the same number
    of stones (because there's only one pile), so the game simplifies to standard Nim on one pile.
    Tokitsukaze wins if a_1 > 0.
    """
    n, a_values = parse_input(stdin)
    assert n == 1, "Input generator for n=1 produced n != 1"
    a1 = a_values[0]

    if a1 == 0:
        expected_output = "cslnb\n"
    else:
        expected_output = "sjfnb\n"
    
    stdout = run_candidate(stdin)
    assert stdout == expected_output, (
        f"Incorrect output for n=1 case.\n"
        f"Input:\n{stdin}Expected: {expected_output.strip()}\nGot: {stdout.strip()}"
    )