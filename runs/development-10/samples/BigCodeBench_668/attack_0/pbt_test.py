import itertools
import math
from candidate import task_func
from hypothesis import given, settings, strategies as st

@settings(max_examples=50, deadline=None)
@given(data=st.dictionaries(
    keys=st.text(alphabet=st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=1),
    values=st.integers(min_value=-100, max_value=100),
    min_size=1,
    max_size=12
))
def test_output_is_list_of_keys(data):
    result = task_func(data)
    assert isinstance(result, list)
    for key in result:
        assert key in data

@settings(max_examples=50, deadline=None)
@given(data=st.dictionaries(
    keys=st.text(alphabet=st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=1),
    values=st.integers(min_value=1, max_value=100), # All positive values
    min_size=1,
    max_size=12
))
def test_all_positive_values_returns_single_min_key(data):
    result = task_func(data)
    assert len(result) == 1
    min_val = min(data.values())
    assert data[result[0]] == min_val

@settings(max_examples=50, deadline=None)
@given(data=st.dictionaries(
    keys=st.text(alphabet=st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=1),
    values=st.integers(min_value=-100, max_value=-1), # All negative values
    min_size=1,
    max_size=12
))
def test_all_negative_values_returns_all_keys(data):
    result = task_func(data)
    assert len(result) == len(data)
    # The order of keys in the result list is not specified, so convert to set for comparison
    assert set(result) == set(data.keys())

@settings(max_examples=50, deadline=None)
@given(data=st.dictionaries(
    keys=st.text(alphabet=st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=1),
    values=st.integers(min_value=-100, max_value=100),
    min_size=1,
    max_size=12
))
def test_result_sum_is_minimum_possible(data):
    result = task_func(data)
    actual_sum = sum(data[key] for key in result)

    min_possible_sum = 0
    for i in range(1, len(data) + 1):
        for subset_keys in itertools.combinations(data.keys(), i):
            current_sum = sum(data[key] for key in subset_keys)
            if current_sum < min_possible_sum:
                min_possible_sum = current_sum
    
    # Also consider the empty set sum (0) if all values are positive or zero
    # The problem implies finding a subsequence, which usually means non-empty.
    # However, if all values are positive, the minimum sum is the smallest positive value.
    # If all values are positive, the minimum sum is the smallest single value.
    # If there are negative values, the minimum sum will be negative or zero.
    # The example `['a']` for `{'a': 1, 'b': 2, 'c': 3}` implies non-empty.
    # The example `['b', 'c']` for `{'a': 1, 'b': -2, 'c': -5, 'd': 4}` implies non-empty.
    # So, we should compare against the minimum sum of all non-empty subsets.
    
    # Recalculate min_possible_sum considering only non-empty subsets
    # Initialize with a very large number, or the sum of the first element
    min_possible_sum_non_empty = float('inf')
    if data: # Ensure data is not empty, though min_size=1 prevents this
        for i in range(1, len(data) + 1):
            for subset_keys in itertools.combinations(data.keys(), i):
                current_sum = sum(data[key] for key in subset_keys)
                if current_sum < min_possible_sum_non_empty:
                    min_possible_sum_non_empty = current_sum
    
    assert actual_sum == min_possible_sum_non_empty

@settings(max_examples=50, deadline=None)
@given(key=st.text(alphabet=st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=1),
       value=st.integers(min_value=-100, max_value=100))
def test_single_element_dict_returns_that_key(key, value):
    data = {key: value}
    result = task_func(data)
    assert result == [key]

@settings(max_examples=50, deadline=None)
@given(data=st.dictionaries(
    keys=st.text(alphabet=st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=1),
    values=st.integers(min_value=0, max_value=0), # All zero values
    min_size=1,
    max_size=12
))
def test_all_zero_values_returns_single_key(data):
    result = task_func(data)
    assert len(result) == 1
    assert data[result[0]] == 0

@settings(max_examples=50, deadline=None)
@given(data=st.dictionaries(
    keys=st.text(alphabet=st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=1),
    values=st.integers(min_value=-100, max_value=100),
    min_size=2, # Ensure at least two elements
    max_size=12
))
def test_adding_positive_value_does_not_change_negative_min_sum(data):
    # Find the current minimum sum for the original data
    min_sum_original = float('inf')
    for i in range(1, len(data) + 1):
        for subset_keys in itertools.combinations(data.keys(), i):
            current_sum = sum(data[key] for key in subset_keys)
            if current_sum < min_sum_original:
                min_sum_original = current_sum
    
    # If the original min_sum is positive, this test might not be meaningful.
    # We are looking for cases where adding a positive value doesn't change a *negative* min sum.
    # Let's filter for cases where the original min_sum is negative or zero.
    if min_sum_original > 0:
        # This test is specifically for when the minimum sum is negative or zero.
        # If all values are positive, adding another positive value will still result in a positive min sum.
        # We want to test the robustness of finding negative sums.
        return # Skip this example if min_sum_original is positive

    # Add a new key with a positive value
    new_key_char = st.text(alphabet=st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=1).example()
    while new_key_char in data: # Ensure unique key
        new_key_char = st.text(alphabet=st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=1).example()
    
    new_value = st.integers(min_value=1, max_value=100).example()
    data_modified = data.copy()
    data_modified[new_key_char] = new_value

    result_original = task_func(data)
    result_modified = task_func(data_modified)

    sum_original_result = sum(data[k] for k in result_original)
    sum_modified_result = sum(data_modified[k] for k in result_modified)

    # If the original minimum sum was negative, adding a positive value should not make the minimum sum larger (less negative or positive)
    # unless the positive value itself is part of a new minimum sum (which is unlikely if the original min sum was negative).
    # The minimum sum should remain the same as the original negative minimum sum.
    assert sum_modified_result <= sum_original_result
    # More precisely, if the original minimum sum was negative, and we add a positive value,
    # the new minimum sum should be exactly the original minimum sum, as including the positive value would increase the sum.
    assert sum_modified_result == sum_original_result

@settings(max_examples=50, deadline=None)
@given(data=st.dictionaries(
    keys=st.text(alphabet=st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=1),
    values=st.integers(min_value=-100, max_value=100),
    min_size=1,
    max_size=12
))
def test_output_keys_are_unique(data):
    result = task_func(data)
    assert len(result) == len(set(result))

@settings(max_examples=50, deadline=None)
@given(data=st.dictionaries(
    keys=st.text(alphabet=st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=1),
    values=st.integers(min_value=-100, max_value=100),
    min_size=1,
    max_size=12
))
def test_adding_negative_value_can_reduce_min_sum(data):
    # Find the current minimum sum for the original data
    min_sum_original = float('inf')
    for i in range(1, len(data) + 1):
        for subset_keys in itertools.combinations(data.keys(), i):
            current_sum = sum(data[key] for key in subset_keys)
            if current_sum < min_sum_original:
                min_sum_original = current_sum
    
    # Add a new key with a negative value
    new_key_char = st.text(alphabet=st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=1).example()
    while new_key_char in data: # Ensure unique key
        new_key_char = st.text(alphabet=st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=1).example()
    
    new_value = st.integers(min_value=-100, max_value=-1).example()
    data_modified = data.copy()
    data_modified[new_key_char] = new_value

    result_original = task_func(data)
    result_modified = task_func(data_modified)

    sum_original_result = sum(data[k] for k in result_original)
    sum_modified_result = sum(data_modified[k] for k in result_modified)

    # The new minimum sum should be less than or equal to the original minimum sum.
    # It should be strictly less if the new negative value helps form a new, smaller sum.
    assert sum_modified_result <= sum_original_result

@settings(max_examples=50, deadline=None)
@given(data=st.dictionaries(
    keys=st.text(alphabet=st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=1),
    values=st.integers(min_value=-100, max_value=100),
    min_size=1,
    max_size=12
))
def test_output_is_not_empty(data):
    result = task_func(data)
    assert len(result) > 0