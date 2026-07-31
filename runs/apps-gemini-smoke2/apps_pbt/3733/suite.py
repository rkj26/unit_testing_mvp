import math
from collections import Counter
from hypothesis import given, strategies as st, settings
from harness import run_candidate   # Assume this is provided by the harness

# Helper function for calculating k_bits, needed by some tests
def _calculate_k_bits(num_distinct_values):
    if num_distinct_values <= 1: # K=0 or K=1 implies k=0
        return 0
    return math.ceil(math.log2(num_distinct_values))

# Build ONE valid STDIN string in this problem's exact input format (include newlines the problem expects).
@st.composite
def make_input(draw):
    n = draw(st.integers(min_value=1, max_value=4 * 10**5))
    I = draw(st.integers(min_value=1, max_value=10**8))
    
    # Generate array elements.
    # To encourage various distinct counts, we want to test scenarios
    # with few distinct values, many distinct values, and values from a wide range.
    
    # Strategy to vary distinctness:
    # 1. All elements are the same (K=1)
    # 2. All elements are unique (K=n) - limited to smaller N for performance
    # 3. Intermediate number of unique elements
    
    choice = draw(st.sampled_from(['all_same', 'all_unique', 'mixed']))
    
    if choice == 'all_same':
        val = draw(st.integers(min_value=0, max_value=10**9))
        a = [val] * n
    elif choice == 'all_unique':
        # Generating N unique integers for large N can be slow.
        # Limit N for the 'all_unique' case, or ensure numbers are drawn from a smaller range.
        # Here we limit N for all unique case, and for larger N fallback to 'mixed'.
        if n > 2000: # Heuristic to avoid excessively slow unique list generation for very large N
            # For very large N, it's more efficient to generate unique values from a pool
            # and then sample, like 'mixed' case, but aiming for high unique count.
            num_unique_values = draw(st.integers(min_value=max(1, n // 2), max_value=min(n, 2000)))
            unique_vals = draw(st.lists(st.integers(min_value=0, max_value=10**9),
                                        min_size=num_unique_values, max_size=num_unique_values, unique=True))
            a = draw(st.lists(st.sampled_from(unique_vals), min_size=n, max_size=n))
        else:
            a = draw(st.lists(st.integers(min_value=0, max_value=10**9), min_size=n, max_size=n, unique=True))
    else: # 'mixed' or default case
        # Generate `num_unique_values` distinct values, then fill the array by sampling from them.
        num_unique_values = draw(st.integers(min_value=1, max_value=min(n, 2000))) # Limit unique values count
        unique_vals = draw(st.lists(st.integers(min_value=0, max_value=10**9),
                                    min_size=num_unique_values, max_size=num_unique_values, unique=True))
        a = draw(st.lists(st.sampled_from(unique_vals), min_size=n, max_size=n))
    
    # Shuffle to avoid sorted inputs always (unless explicitly desired for a test)
    draw(st.randoms()).shuffle(a)
    
    return f"{n} {I}\n" + " ".join(map(str, a))


# Test Suite
# ---

# Test 1: Basic output format and range checks
@given(make_input())
@settings(max_examples=50, deadline=None)
def test_output_format_and_range(stdin):
    stdout = run_candidate(stdin)
    
    # Check for single line output
    parts = stdout.strip().split('\n')
    if len(parts) != 1:
        raise AssertionError(f"Output has multiple lines, expected one: '{stdout}'")

    # Check if output is an integer
    try:
        ans = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not an integer: '{stdout}'")
    
    # Check if output is within [0, n]
    n = int(stdin.split('\n')[0].split(' ')[0])
    if not (0 <= ans <= n):
        raise AssertionError(f"Output '{ans}' is out of range [0, {n}] (n from input: {n}). Input first line: '{stdin.splitlines()[0]}'")

# Test 2: If initial state fits the disk, no changes should be made (ans = 0)
@st.composite
def make_input_no_compression_needed(draw):
    n = draw(st.integers(min_value=1, max_value=4 * 10**5))
    
    # Generate array elements with varying distinctness
    num_unique_values = draw(st.integers(min_value=1, max_value=min(n, 2000))) 
    unique_vals = draw(st.lists(st.integers(min_value=0, max_value=10**9), 
                                min_size=num_unique_values, max_size=num_unique_values, unique=True))
    a = draw(st.lists(st.sampled_from(unique_vals), min_size=n, max_size=n))
    draw(st.randoms()).shuffle(a)

    initial_distinct_count = len(set(a))
    initial_k_bits = _calculate_k_bits(initial_distinct_count)
    
    # Calculate min_I_needed to make it fit, ensuring 8I >= n * initial_k_bits.
    min_I_needed = (n * initial_k_bits + 7) // 8 # Ceiling division
    
    # Ensure I is at least 1 and large enough
    I = draw(st.integers(min_value=max(1, min_I_needed), max_value=10**8))
    
    return f"{n} {I}\n" + " ".join(map(str, a))

@given(make_input_no_compression_needed())
@settings(max_examples=50, deadline=None)
def test_no_changes_if_sufficient_disk_space(stdin):
    stdout = run_candidate(stdin)
    ans = int(stdout.strip())

    lines = stdin.strip().split('\n')
    n, I_val = map(int, lines[0].split())
    a = list(map(int, lines[1].split()))
    
    initial_distinct_count = len(set(a))
    initial_k_bits = _calculate_k_bits(initial_distinct_count)

    # Re-verify the condition based on the generated input
    if n * initial_k_bits <= 8 * I_val:
        if ans != 0:
            raise AssertionError(f"Expected 0 changes when disk space is sufficient, but got {ans}. "
                                 f"Input: n={n}, I={I_val}. Array distinct elements: {initial_distinct_count}, "
                                 f"bits needed per element: {initial_k_bits}. Total bits needed: {n * initial_k_bits}. "
                                 f"Available disk bits: {8 * I_val}.")

# Test 3: Specific case - when only 1 distinct value (K=1, k=0 bits) is allowed.
# In this scenario, the optimal strategy is to convert all elements to the most frequent value.
# The number of changes will be n - count_of_most_frequent_element.
@st.composite
def make_input_force_K_one(draw):
    # Choose I and n such that 8*I // n == 0. This implies 8*I < n.
    # To achieve this reliably, we can pick I first, then ensure n is sufficiently large.
    # Max I is 10^8. If I is 10^8, then n must be > 8*10^8, which exceeds 4*10^5.
    # So max I for this scenario needs to be smaller. Max_N / 8 approx = 4e5 / 8 = 5e4.
    I_for_K1 = draw(st.integers(min_value=1, max_value=math.floor((4 * 10**5 - 1) / 8))) 
    
    n_lower_bound = 8 * I_for_K1 + 1 # Smallest n such that 8*I < n
    n_for_K1 = draw(st.integers(min_value=n_lower_bound, max_value=4 * 10**5))

    a = draw(st.lists(st.integers(min_value=0, max_value=10**9), min_size=n_for_K1, max_size=n_for_K1))
    draw(st.randoms()).shuffle(a)
    
    return f"{n_for_K1} {I_for_K1}\n" + " ".join(map(str, a))

@given(make_input_force_K_one())
@settings(max_examples=50, deadline=None)
def test_forced_single_distinct_value(stdin):
    stdout = run_candidate(stdin)
    ans = int(stdout.strip())

    lines = stdin.strip().split('\n')
    n, I_val = map(int, lines[0].split())
    a = list(map(int, lines[1].split()))

    # The input strategy guarantees max_k_bits_allowed = 8 * I_val // n == 0.
    # This means only K=1 (0 bits per element) is allowed by disk size.
    
    counts = Counter(a)
    if not counts: # Should not happen for n >= 1
        expected_min_changes = 0
    else:
        most_frequent_count = max(counts.values())
        expected_min_changes = n - most_frequent_count
    
    if ans != expected_min_changes:
        # Truncate array for error message to avoid flooding console
        display_a = a if len(a) <= 20 else a[:10] + ['...'] + a[-10:]
        raise AssertionError(f"Expected {expected_min_changes} changes when only K=1 (0 bits) is allowed, "
                             f"but got {ans}. n={n}, I={I_val}. Array values: {display_a}.")

# Test 4: Metamorphic test - increasing disk space should not increase the number of changes
@st.composite
def make_input_for_monotonicity(draw):
    n = draw(st.integers(min_value=1, max_value=4 * 10**5))
    I_base = draw(st.integers(min_value=1, max_value=10**8 - 1)) # Ensure I_base + 1 doesn't exceed 10^8
    
    # Generate array with varying distinctness to test different scenarios
    num_unique_values = draw(st.integers(min_value=1, max_value=min(n, 2000))) 
    unique_vals = draw(st.lists(st.integers(min_value=0, max_value=10**9), 
                                min_size=num_unique_values, max_size=num_unique_values, unique=True))
    a = draw(st.lists(st.sampled_from(unique_vals), min_size=n, max_size=n))
    draw(st.randoms()).shuffle(a)
    
    stdin_base = f"{n} {I_base}\n" + " ".join(map(str, a))
    stdin_inc = f"{n} {I_base + 1}\n" + " ".join(map(str, a))
    return stdin_base, stdin_inc

@given(make_input_for_monotonicity())
@settings(max_examples=50, deadline=None)
def test_monotonicity_with_increasing_disk_space(inputs):
    stdin_base, stdin_inc = inputs
    
    ans_base_str = run_candidate(stdin_base)
    ans_inc_str = run_candidate(stdin_inc)
    
    try:
        ans_base = int(ans_base_str.strip())
        ans_inc = int(ans_inc_str.strip())
    except ValueError:
        raise AssertionError(f"Output not an integer. Base: '{ans_base_str}', Inc: '{ans_inc_str}'")

    # If I_base < I_base + 1, then ans_base (changes for less space) >= ans_inc (changes for more space).
    if ans_base < ans_inc:
        n_base, I_val_base = map(int, stdin_base.split('\n')[0].split())
        n_inc, I_val_inc = map(int, stdin_inc.split('\n')[0].split())
        # Truncate array string for error message
        a_str = stdin_base.split('\n')[1]
        display_a = a_str if len(a_str) <= 100 else a_str[:50] + ' ... ' + a_str[-50:]

        raise AssertionError(f"Increasing disk space (I) unexpectedly increased changes. "
                             f"Input base: n={n_base}, I={I_val_base}. Changes: {ans_base}. "
                             f"Input increased: n={n_inc}, I={I_val_inc}. Changes: {ans_inc}. "
                             f"Expected ans_base >= ans_inc. Array: {display_a}.")

# Test 5: Check N=1 case (should always be 0 changes)
@st.composite
def make_input_n_equals_one(draw):
    n = 1
    I = draw(st.integers(min_value=1, max_value=10**8))
    a = draw(st.lists(st.integers(min_value=0, max_value=10**9), min_size=n, max_size=n))
    return f"{n} {I}\n" + " ".join(map(str, a))

@given(make_input_n_equals_one())
@settings(max_examples=20, deadline=None)
def test_n_equals_one(stdin):
    stdout = run_candidate(stdin)
    ans = int(stdout.strip())
    
    if ans != 0:
        # For n=1, there's always only 1 distinct element (K=1) in the array, no matter its value.
        # k = ceil(log2 1) = 0 bits.
        # Total bits = n * k = 1 * 0 = 0 bits.
        # Disk constraint: 0 <= 8 * I. Since I >= 1, this is always true.
        # So 0 changes are always needed.
        raise AssertionError(f"Expected 0 changes when n=1, but got {ans}. Input: '{stdin.strip()}'")