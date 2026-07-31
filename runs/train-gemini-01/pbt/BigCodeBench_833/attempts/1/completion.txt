# SEARCH PLAN:
# 1. Mode and Frequency correctness: Verify the returned mode is truly the most frequent, and the generator yields correct counts for all elements. Target small lists and narrow ranges where verification is easier.
# 2. Range and Length adherence: Ensure all generated numbers are within the specified range and the total count matches `list_length`. Target boundary values for ranges and list lengths.
# 3. Reproducibility: Confirm that `random_seed` makes the function deterministic, producing identical outputs for identical inputs. Target various seeds and parameters.

from candidate import task_func
from hypothesis import given, settings, strategies as st
from collections import Counter
import random
from statistics import mode as stats_mode # Use an alias to avoid name collision with test variable

@settings(max_examples=50, deadline=None)
@given(
    list_length=st.integers(min_value=1, max_value=12),
    range_start=st.integers(min_value=-10, max_value=10),
    range_end=st.integers(min_value=-10, max_value=10),
    random_seed=st.integers(min_value=0, max_value=1000)
)
def test_mode_and_generator_frequencies_correctness(list_length, range_start, range_end, random_seed):
    """
    SPEC BASIS: "Generate a random list of integers within a specified range. ... find and return the mode of the list. ...
                generator object that yields tuples. Each tuple contains a number from the list and its frequency."
    PROPERTY: The returned mode is the most frequent element in the generated list. The generator yields all numbers
              with their correct frequencies, and the sum of frequencies equals the list length.
    STRATEGY: Generate small lists with varying ranges (including `range_start == range_end` and negative numbers)
              to make it easier to verify the mode and frequencies against a re-generated list.
    """
    # Ensure range_start <= range_end for valid input to task_func
    if range_start > range_end:
        range_start, range_end = range_end, range_start

    try:
        returned_mode, numbers_generator = task_func(list_length, range_start, range_end, random_seed)
    except Exception:
        assert False, "task_func raised an unexpected exception"

    # Re-generate the original list to verify against
    random.seed(random_seed)
    original_list = [random.randint(range_start, range_end) for _ in range(list_length)]
    
    # Calculate expected mode and frequencies
    if not original_list: # Should not happen with list_length >= 1, but for robustness
        expected_mode = None
        expected_frequencies = Counter()
    else:
        # statistics.mode raises StatisticsError for empty list or no unique mode.
        # The problem implies a mode will always be found for a non-empty list.
        # If there are multiple modes, statistics.mode returns the first one encountered.
        try:
            expected_mode = stats_mode(original_list)
        except Exception: # Catch StatisticsError if it occurs, though unlikely for list_length >= 1
            expected_mode = None # Indicate an issue if mode cannot be determined
        expected_frequencies = Counter(original_list)

    # Convert generator output to a list of (number, frequency) tuples for comparison
    actual_frequencies_list = list(numbers_generator)
    
    # Verify mode
    assert returned_mode == expected_mode, \
        f"Returned mode {returned_mode} does not match expected mode {expected_mode} for list {original_list}"

    # Verify generator content (frequencies)
    # Reconstruct a Counter from the generator output for order-insensitive comparison
    actual_frequencies_counter = Counter()
    for num, freq in actual_frequencies_list:
        actual_frequencies_counter[num] += freq # Sum frequencies for each number

    assert actual_frequencies_counter == expected_frequencies, \
        f"Generator frequencies {actual_frequencies_counter} do not match expected {expected_frequencies} for list {original_list}"

    # Verify total count from generator matches list_length
    assert sum(f for _, f in actual_frequencies_list) == list_length, \
        f"Sum of frequencies from generator ({sum(f for _, f in actual_frequencies_list)}) does not match list_length ({list_length})"


@settings(max_examples=50, deadline=None)
@given(
    list_length=st.integers(min_value=1, max_value=12),
    range_start=st.integers(min_value=-10, max_value=10),
    range_end=st.integers(min_value=-10, max_value=10),
    random_seed=st.integers(min_value=0, max_value=1000)
)
def test_range_and_length_adherence(list_length, range_start, range_end, random_seed):
    """
    SPEC BASIS: "Generate a random list of integers within a specified range. ... list_length (int): The length of the random list to be generated."
    PROPERTY: All numbers yielded by the generator are within the specified [range_start, range_end] (inclusive).
              The total count of numbers represented by the generator equals `list_length`.
    STRATEGY: Test with various `list_length` values (including 1) and `range_start`/`range_end` values,
              including negative numbers, zero, and cases where `range_start == range_end`.
    """
    # Ensure range_start <= range_end for valid input to task_func
    if range_start > range_end:
        range_start, range_end = range_end, range_start

    try:
        _, numbers_generator = task_func(list_length, range_start, range_end, random_seed)
    except Exception:
        assert False, "task_func raised an unexpected exception"

    total_elements_from_generator = 0
    for num, freq in numbers_generator:
        # Verify each number is within the specified range
        assert range_start <= num <= range_end, \
            f"Number {num} from generator is outside specified range [{range_start}, {range_end}]"
        # Accumulate total count
        total_elements_from_generator += freq

    # Verify the total count matches the specified list_length
    assert total_elements_from_generator == list_length, \
        f"Total elements from generator ({total_elements_from_generator}) does not match list_length ({list_length})"


@settings(max_examples=50, deadline=None)
@given(
    list_length=st.integers(min_value=1, max_value=12),
    range_start=st.integers(min_value=-10, max_value=10),
    range_end=st.integers(min_value=-10, max_value=10),
    random_seed=st.integers(min_value=0, max_value=1000)
)
def test_reproducibility_with_random_seed(list_length, range_start, range_end, random_seed):
    """
    SPEC BASIS: "random_seed (int): Seed for the rng." (implies deterministic behavior for a given seed).
    PROPERTY: Calling `task_func` twice with the exact same parameters, including `random_seed`,
              produces identical results (mode and generator content).
    STRATEGY: Call `task_func` twice with the same Hypothesis-generated inputs and assert that
              both the returned mode and the fully consumed generator outputs are identical.
    """
    # Ensure range_start <= range_end for valid input to task_func
    if range_start > range_end:
        range_start, range_end = range_end, range_start

    try:
        mode1, gen1 = task_func(list_length, range_start, range_end, random_seed)
        mode2, gen2 = task_func(list_length, range_start, range_end, random_seed)
    except Exception:
        assert False, "task_func raised an unexpected exception during reproducibility test"

    assert mode1 == mode2, \
        f"Modes differ for same seed {random_seed}: {mode1} != {mode2}"

    # Convert generators to lists for comparison
    list1 = list(gen1)
    list2 = list(gen2)

    assert list1 == list2, \
        f"Generator outputs differ for same seed {random_seed}: {list1} != {list2}"

    # Also check that the order of elements in the generator is consistent,
    # as `random.seed` should make the entire generation process deterministic.
    # If the problem allowed arbitrary order, we would use Counter here.
    # The example output `[(136, 1), (30, 1), ...]` suggests a specific order (insertion order or similar).
    # Since `random.seed` is used, the underlying list generation should be identical,
    # and thus the processing into a generator should also be identical, preserving order.
    # If the implementation uses `collections.Counter().items()`, the order is not guaranteed
    # in Python versions < 3.7. However, the problem implies a direct conversion from the list,
    # and `random.seed` should make the list itself deterministic.
    # For robustness, we can compare Counters if exact order is not strictly guaranteed by spec,
    # but given `random.seed` and the expectation of deterministic behavior, `list1 == list2` is stronger.
    assert Counter(dict(list1)) == Counter(dict(list2)), \
        f"Generator outputs (as Counters) differ for same seed {random_seed}: {Counter(dict(list1))} != {Counter(dict(list2))}"