from candidate import task_func
from hypothesis import given, settings, strategies as st
import collections
import itertools

# Strategy for generating lists of integers
# Integers are kept within a reasonable range to avoid overflow issues with counts
# and to make it easier to reason about expected outputs.
list_of_ints_strategy = st.lists(st.integers(min_value=-100, max_value=100), min_size=0, max_size=10)

# Strategy for generating the input dictionary 'd'
# Keys are strings, values are lists of integers.
# Dictionary size is limited to keep test execution fast.
input_dict_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=('L', 'N'))),
    values=list_of_ints_strategy,
    min_size=0,
    max_size=5
)

@settings(max_examples=50, deadline=None)
@given(d=input_dict_strategy)
def test_sum_of_counts_equals_total_elements(d):
    """
    Property: The sum of all counts in the output dictionary must equal the total number of
    integers across all input lists.
    """
    try:
        result = task_func(d)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for input {d}: {e}"

    total_elements_in_input = sum(len(lst) for lst in d.values())
    sum_of_output_counts = sum(result.values())

    assert sum_of_output_counts == total_elements_in_input, \
        f"Sum of output counts ({sum_of_output_counts}) does not match total input elements ({total_elements_in_input}) for input {d}. Result: {result}"

@settings(max_examples=50, deadline=None)
@given(d=input_dict_strategy)
def test_all_output_keys_are_from_input_values(d):
    """
    Property: Every key in the output dictionary must be an integer that was present
    in at least one of the input lists.
    """
    try:
        result = task_func(d)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for input {d}: {e}"

    all_input_integers = set(itertools.chain.from_iterable(d.values()))

    for key in result.keys():
        assert key in all_input_integers, \
            f"Output key {key} not found in any input list for input {d}. Result: {result}"

@settings(max_examples=50, deadline=None)
@given(d=input_dict_strategy)
def test_all_input_integers_with_occurrences_are_output_keys(d):
    """
    Property: Every integer that appears in the input lists at least once must be a key
    in the output dictionary.
    """
    try:
        result = task_func(d)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for input {d}: {e}"

    all_input_integers = set(itertools.chain.from_iterable(d.values()))

    for integer in all_input_integers:
        assert integer in result, \
            f"Input integer {integer} is missing from output keys for input {d}. Result: {result}"

@settings(max_examples=50, deadline=None)
@given(d=input_dict_strategy)
def test_output_counts_are_positive(d):
    """
    Property: All values (counts) in the output dictionary must be positive integers.
    (Since only integers present in the input are counted, their count must be at least 1).
    """
    try:
        result = task_func(d)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for input {d}: {e}"

    for count in result.values():
        assert isinstance(count, int) and count > 0, \
            f"Output count {count} is not a positive integer for input {d}. Result: {result}"

@settings(max_examples=50, deadline=None)
@given(d=input_dict_strategy)
def test_empty_input_dictionary_returns_empty_output(d):
    """
    Property: If the input dictionary is empty, the output should be an empty dictionary.
    This is a specific boundary case of the general correctness.
    """
    if not d: # Check if d is empty
        try:
            result = task_func(d)
        except Exception as e:
            assert False, f"task_func raised an unexpected exception for empty input {d}: {e}"
        assert result == {}, f"Empty input dictionary {d} did not return an empty dictionary. Result: {result}"

@settings(max_examples=50, deadline=None)
@given(d=st.dictionaries(
    keys=st.text(min_size=1, max_size=5),
    values=st.lists(st.integers(min_value=-100, max_value=100), min_size=0, max_size=10),
    min_size=1, max_size=5
))
def test_metamorphic_relation_adding_empty_list_does_not_change_counts(d):
    """
    Metamorphic Property: Adding an entry with an empty list to the input dictionary
    should not change the counts of existing integers.
    """
    try:
        original_result = task_func(d)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for original input {d}: {e}"

    # Create a new dictionary with an added empty list
    new_d = d.copy()
    # Ensure the new key doesn't clash with existing keys
    new_key = "new_empty_key"
    while new_key in new_d:
        new_key += "_"
    new_d[new_key] = []

    try:
        modified_result = task_func(new_d)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for modified input {new_d}: {e}"

    assert original_result == modified_result, \
        f"Adding an empty list changed counts. Original: {original_result}, Modified: {modified_result}. Input: {d}, New Input: {new_d}"

@settings(max_examples=50, deadline=None)
@given(d=input_dict_strategy,
       extra_list=list_of_ints_strategy)
def test_metamorphic_relation_combining_lists_preserves_counts(d, extra_list):
    """
    Metamorphic Property: If we split an input list into two, or combine two lists into one,
    the final counts should remain the same.
    Here, we test by adding a new list to the dictionary and comparing its result
    to a scenario where that list's elements are merged into an existing list.
    """
    if not d: # Ensure there's at least one list to merge into
        if not extra_list: # If both are empty, result should be empty
            try:
                result = task_func(d)
            except Exception as e:
                assert False, f"task_func raised an unexpected exception for input {d}: {e}"
            assert result == {}, f"Empty input {d} and empty extra_list {extra_list} did not return empty dict. Result: {result}"
            return
        # If d is empty but extra_list is not, create a temporary dict for original_result
        d_for_original = {'temp_key': extra_list}
        try:
            original_result = task_func(d_for_original)
        except Exception as e:
            assert False, f"task_func raised an unexpected exception for input {d_for_original}: {e}"
        # For modified_result, d is empty, so it should just be the count of extra_list
        modified_d = {'temp_key': extra_list}
        try:
            modified_result = task_func(modified_d)
        except Exception as e:
            assert False, f"task_func raised an unexpected exception for input {modified_d}: {e}"
        assert original_result == modified_result, \
            f"Metamorphic relation failed for empty d. Original: {original_result}, Modified: {modified_result}. Input: {d}, Extra: {extra_list}"
        return

    # Scenario 1: Add extra_list as a new entry
    d_scenario1 = d.copy()
    new_key = "extra_list_key"
    while new_key in d_scenario1:
        new_key += "_"
    d_scenario1[new_key] = extra_list

    try:
        result_scenario1 = task_func(d_scenario1)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for scenario 1 input {d_scenario1}: {e}"

    # Scenario 2: Merge extra_list into an existing list
    d_scenario2 = d.copy()
    # Pick an arbitrary key from d to merge into
    existing_key = next(iter(d_scenario2))
    d_scenario2[existing_key] = d_scenario2[existing_key] + extra_list

    try:
        result_scenario2 = task_func(d_scenario2)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for scenario 2 input {d_scenario2}: {e}"

    assert result_scenario1 == result_scenario2, \
        f"Merging lists changed counts. Scenario 1: {result_scenario1}, Scenario 2: {result_scenario2}. Original D: {d}, Extra List: {extra_list}"

@settings(max_examples=50, deadline=None)
@given(d=input_dict_strategy)
def test_output_matches_manual_counter(d):
    """
    Property: The output of task_func should be identical to what a manual
    collections.Counter would produce by flattening all lists.
    This is a strong correctness check.
    """
    try:
        result = task_func(d)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for input {d}: {e}"

    all_elements = list(itertools.chain.from_iterable(d.values()))
    expected_result = dict(collections.Counter(all_elements))

    assert result == expected_result, \
        f"Output does not match manual Counter. Expected: {expected_result}, Got: {result}. Input: {d}"

@settings(max_examples=50, deadline=None)
@given(d=st.dictionaries(
    keys=st.text(min_size=1, max_size=5),
    values=st.lists(st.integers(min_value=-100, max_value=100), min_size=1, max_size=10), # Ensure lists are not empty
    min_size=1, max_size=5
))
def test_output_keys_are_integers(d):
    """
    Property: All keys in the output dictionary must be integers.
    """
    try:
        result = task_func(d)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for input {d}: {e}"

    for key in result.keys():
        assert isinstance(key, int), \
            f"Output key {key} is not an integer for input {d}. Result: {result}"

@settings(max_examples=50, deadline=None)
@given(d=input_dict_strategy)
def test_output_values_are_integers(d):
    """
    Property: All values in the output dictionary must be integers.
    """
    try:
        result = task_func(d)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for input {d}: {e}"

    for value in result.values():
        assert isinstance(value, int), \
            f"Output value {value} is not an integer for input {d}. Result: {result}"

@settings(max_examples=50, deadline=None)
@given(d=st.dictionaries(
    keys=st.text(min_size=1, max_size=5),
    values=st.lists(st.integers(min_value=-100, max_value=100), min_size=0, max_size=10),
    min_size=0, max_size=5
))
def test_idempotence_with_no_side_effects(d):
    """
    Property: Calling the function multiple times with the same input should yield
    the same result, and the input dictionary should not be modified.
    """
    d_copy = d.copy()
    for key, value in d.items():
        d_copy[key] = list(value) # Deep copy lists

    try:
        result1 = task_func(d)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception on first call for input {d}: {e}"

    # Check if input 'd' was modified
    assert d == d_copy, f"Input dictionary was modified after first call. Original: {d_copy}, Modified: {d}"

    try:
        result2 = task_func(d)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception on second call for input {d}: {e}"

    assert result1 == result2, \
        f"Calling task_func twice with same input yielded different results. First: {result1}, Second: {result2}. Input: {d}"

    # Check again if input 'd' was modified after second call
    assert d == d_copy, f"Input dictionary was modified after second call. Original: {d_copy}, Modified: {d}"