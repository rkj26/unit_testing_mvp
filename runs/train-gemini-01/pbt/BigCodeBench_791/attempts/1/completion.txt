# SEARCH PLAN:
# 1. Test list length boundaries (empty, 1, 2, 3 elements) where the "move first 3" logic is critical.
# 2. Test the total count of elements in the final Counter, which must be 30.
# 3. Test that all original elements (from the *modified* list) are present in the final Counter.
# 4. Test with duplicate elements in the input list to ensure counts are handled correctly.

from candidate import task_func
from hypothesis import given, settings, strategies as st
from collections import Counter
import random # Required for seeding random.shuffle in task_func for reproducible tests.
from itertools import cycle # Not directly used in tests, but part of task_func's logic.

# Constants from the problem description
ELEMENTS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']

# Strategy for elements in the list. Using a small alphabet to encourage duplicates.
element_strategy = st.sampled_from(ELEMENTS)

@settings(max_examples=50, deadline=None)
@given(l=st.lists(element_strategy, min_size=0, max_size=12))
def test_output_counter_total_elements_is_30(l):
    """
    SPEC BASIS: "Returns: - counter (collections.Counter): A frequency counter that maps
                elements from the input list to their frequencies in the first 30 elements
                of the cycled, shuffled list."
    PROPERTY: The sum of all frequencies in the returned Counter must always be 30,
              regardless of the input list's content or length (as long as it's valid).
    STRATEGY: Generate lists of varying lengths, including empty, single-element, and
              lists with duplicates, to ensure the final count of 30 is consistently met.
              This catches issues where the cycling/shuffling/slicing logic is flawed.
    """
    # The problem example uses random.seed(42) *before* calling task_func,
    # implying task_func relies on the global random state.
    # To make tests reproducible, we must seed random before each call.
    # Hypothesis seeds its own strategies, but not the global random module.
    random.seed(42) # Use a fixed seed for reproducibility across test runs.

    try:
        result_counter = task_func(l)
    except Exception:
        result_counter = None

    assert result_counter is not None, "task_func should not raise an exception for valid inputs."
    assert isinstance(result_counter, Counter), "The return type must be collections.Counter."
    assert sum(result_counter.values()) == 30, \
        f"The total count of elements in the counter should be 30, but got {sum(result_counter.values())}"

@settings(max_examples=50, deadline=None)
@given(l=st.lists(element_strategy, min_size=0, max_size=12))
def test_all_elements_from_modified_list_are_present_if_list_not_empty(l):
    """
    SPEC BASIS: "A frequency counter that maps elements from the input list to their frequencies
                in the first 30 elements of the cycled, shuffled list."
    PROPERTY: If the input list `l` is not empty, all unique elements from the *modified*
              version of `l` must be present as keys in the returned Counter.
              (The problem implies `l` is modified in-place before shuffling/cycling).
    STRATEGY: Generate lists of various lengths and contents. This checks if elements are
              lost during the modification, shuffling, or cycling process, especially
              for small lists where elements might be dropped or not cycled enough.
    """
    random.seed(42)

    # Create a copy to simulate the in-place modification and get the expected elements
    # This is a simulation of the *intermediate state* of `l` after modification,
    # which is then shuffled and cycled.
    original_l_copy = list(l)
    if len(original_l_copy) >= 3:
        modified_l_elements = original_l_copy[3:] + original_l_copy[:3]
    else:
        modified_l_elements = original_l_copy # If less than 3, no elements are moved.

    expected_unique_elements = set(modified_l_elements)

    try:
        result_counter = task_func(l)
    except Exception:
        result_counter = None

    assert result_counter is not None, "task_func should not raise an exception for valid inputs."
    if len(l) > 0: # Only assert presence if the original list wasn't empty
        assert expected_unique_elements.issubset(result_counter.keys()), \
            f"Not all unique elements from the modified list {modified_l_elements} are present in the counter keys {result_counter.keys()}"
    else: # If input list is empty, the counter should also be empty (or contain no keys)
        assert not result_counter, "An empty input list should result in an empty counter."


@settings(max_examples=50, deadline=None)
@given(l=st.lists(element_strategy, min_size=0, max_size=12))
def test_no_unexpected_elements_in_counter(l):
    """
    SPEC BASIS: "A frequency counter that maps elements from the input list to their frequencies..."
    PROPERTY: The returned Counter should only contain elements that were present in the
              *modified* input list. No new, unexpected elements should appear.
    STRATEGY: Generate lists with various elements. This catches cases where the function
              introduces elements not derived from the input, or misinterprets elements.
    """
    random.seed(42)

    original_l_copy = list(l)
    if len(original_l_copy) >= 3:
        modified_l_elements = original_l_copy[3:] + original_l_copy[:3]
    else:
        modified_l_elements = original_l_copy

    allowed_elements = set(modified_l_elements)

    try:
        result_counter = task_func(l)
    except Exception:
        result_counter = None

    assert result_counter is not None, "task_func should not raise an exception for valid inputs."
    for key in result_counter.keys():
        assert key in allowed_elements, \
            f"Counter contains unexpected element '{key}'. Allowed elements: {allowed_elements}"

@settings(max_examples=50, deadline=None)
@given(l=st.one_of(
    st.just([]),
    st.just(['A']),
    st.just(['A', 'B']),
    st.just(['A', 'B', 'C']),
    st.lists(element_strategy, min_size=4, max_size=12)
))
def test_list_modification_effect_on_counter_for_small_lists(l):
    """
    SPEC BASIS: "move the first 3 elements to the end of the list."
                "A frequency counter that maps elements from the input list to their frequencies
                in the first 30 elements of the cycled, shuffled list."
    PROPERTY: The elements counted are those from the list *after* the first 3 elements
              have been moved. This is implicitly tested by comparing the counter keys
              against the *modified* list's unique elements.
    STRATEGY: Focus on boundary list lengths (0, 1, 2, 3 elements) where the "move first 3"
              logic is an edge case. For lists with < 3 elements, no elements are moved.
              For lists with exactly 3 elements, the list is effectively rotated.
    """
    random.seed(42)

    # Simulate the expected state of 'l' *after* modification but *before* shuffling/cycling
    expected_modified_l = list(l)
    if len(expected_modified_l) >= 3:
        # This is how the list *should* look before shuffling and cycling
        expected_modified_l = expected_modified_l[3:] + expected_modified_l[:3]
    # If len < 3, expected_modified_l remains unchanged.

    try:
        result_counter = task_func(l)
    except Exception:
        result_counter = None

    assert result_counter is not None, "task_func should not raise an exception for valid inputs."

    # If the list is empty, the counter should be empty.
    if not expected_modified_l:
        assert not result_counter, "Empty input list should result in an empty counter."
    else:
        # All elements in the counter must come from the *modified* list.
        assert all(item in expected_modified_l for item in result_counter.keys()), \
            f"Counter keys {result_counter.keys()} contain elements not from the modified list {expected_modified_l}"
        # And if the modified list is not empty, the counter should not be empty.
        assert result_counter, "Non-empty modified list should result in a non-empty counter."

# Example test from problem description to ensure consistency
@settings(max_examples=1, deadline=None) # Only run once for the specific example
@given(l=st.just(ELEMENTS))
def test_example_from_problem_description(l):
    """
    SPEC BASIS: Example: >>> random.seed(42) >>> task_func(ELEMENTS)
                Counter({'I': 3, 'F': 3, 'G': 3, 'J': 3, 'E': 3, 'A': 3, 'B': 3, 'H': 3, 'D': 3, 'C': 3})
    PROPERTY: The function output for the given example input and seed matches the specified output.
    STRATEGY: Use st.just to provide the exact ELEMENTS list.
    """
    random.seed(42) # Set the seed as per the example

    try:
        result = task_func(l)
    except Exception:
        result = None

    assert result is not None, "task_func should not raise an exception for the example input."
    expected_counter = Counter({'I': 3, 'F': 3, 'G': 3, 'J': 3, 'E': 3, 'A': 3, 'B': 3, 'H': 3, 'D': 3, 'C': 3})
    assert result == expected_counter, f"Example output mismatch. Expected {expected_counter}, got {result}"