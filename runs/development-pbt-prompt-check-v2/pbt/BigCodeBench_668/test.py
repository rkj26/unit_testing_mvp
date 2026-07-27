from candidate import task_func
from hypothesis import given, settings, strategies as st
import math
import itertools

# Helper to calculate the sum of a subsequence for oracle purposes
def _calculate_subsequence_sum(subsequence_keys, x_dict):
    return sum(x_dict[key] for key in subsequence_keys)

# Helper to find all non-empty subsequences (combinations of keys)
def _get_all_non_empty_subsequences(keys):
    all_subsequences = []
    for i in range(1, len(keys) + 1):
        for combo in itertools.combinations(keys, i):
            all_subsequences.append(list(combo))
    return all_subsequences

@given(x=st.dictionaries(
    keys=st.text(st.ascii_lowercase, min_size=1, max_size=1),
    values=st.integers(min_value=1, max_value=10),
    min_size=1, max_size=5
))
@settings(max_examples=50, deadline=None)
def test_example_positive_values_match(x):
    """
    SPEC BASIS: Example: >>> task_func({'a': 1, 'b': 2, 'c': 3}) ['a']
    PROPERTY: When all values are positive, the output matches the example's logic.
    """
    # This test specifically targets the example's behavior for all positive values.
    # The example implies that the minimum *positive* sum is sought, and the empty list is not returned.
    # For all positive values, the minimum sum will be the single key with the smallest value.
    if all(v > 0 for v in x.values()):
        expected_min_val = min(x.values())
        expected_keys = [k for k, v in x.items() if v == expected_min_val]
        # The example returns ['a'] for {'a':1, 'b':2, 'c':3}, implying a single key.
        # If multiple keys have the same minimum value, any one of them is valid.
        # We check if the returned list contains one of these keys and has the correct sum.
        result = task_func(x)
        assert len(result) == 1, f"Expected a single-element list for positive values, got {result}"
        assert result[0] in expected_keys, f"Expected one of {expected_keys}, got {result[0]}"
        assert _calculate_subsequence_sum(result, x) == expected_min_val, \
            f"Expected sum {expected_min_val}, got {_calculate_subsequence_sum(result, x)}"

@given(x=st.dictionaries(
    keys=st.text(st.ascii_lowercase, min_size=1, max_size=1),
    values=st.integers(min_value=-10, max_value=10),
    min_size=2, max_size=5
))
@settings(max_examples=50, deadline=None)
def test_example_negative_values_match(x):
    """
    SPEC BASIS: Example: >>> task_func({'a': 1, 'b': -2, 'c': -5, 'd': 4}) ['b', 'c']
    PROPERTY: When negative values are present, the output matches the example's logic.
    """
    # This test specifically targets the example's behavior for mixed positive/negative values.
    # The example implies finding the overall minimum sum from non-empty subsequences.
    if any(v < 0 for v in x.values()):
        all_keys = list(x.keys())
        all_non_empty_subsequences = _get_all_non_empty_subsequences(all_keys)

        if not all_non_empty_subsequences: # Should not happen with min_size=2
            return

        min_sum = float('inf')
        min_subsequences = []

        for sub in all_non_empty_subsequences:
            current_sum = _calculate_subsequence_sum(sub, x)
            if current_sum < min_sum:
                min_sum = current_sum
                min_subsequences = [sub]
            elif current_sum == min_sum:
                min_subsequences.append(sub)

        result = task_func(x)
        result_sum = _calculate_subsequence_sum(result, x)

        assert result_sum == min_sum, \
            f"Expected minimum sum {min_sum}, but got {result_sum} for subsequence {result}"
        # The problem does not specify ordering if multiple subsequences yield the same minimum sum.
        # We check if the returned subsequence is one of the valid minimum ones.
        assert any(sorted(result) == sorted(ms) for ms in min_subsequences), \
            f"Returned subsequence {result} is not among the expected minimum subsequences {min_subsequences}"

@given(x=st.dictionaries(
    keys=st.text(st.ascii_lowercase, min_size=1, max_size=1),
    values=st.integers(min_value=-10, max_value=10),
    min_size=1, max_size=5
))
@settings(max_examples=50, deadline=None)
def test_return_type_is_list(x):
    """
    SPEC BASIS: Returns: - list: The subsequence with the minimum total length.
    PROPERTY: The function must return a list.
    """
    result = task_func(x)
    assert isinstance(result, list), f"Expected return type list, got {type(result)}"

@given(x=st.dictionaries(
    keys=st.text(st.ascii_lowercase, min_size=1, max_size=1),
    values=st.integers(min_value=-10, max_value=10),
    min_size=1, max_size=5
))
@settings(max_examples=50, deadline=None)
def test_returned_elements_are_keys_from_input(x):
    """
    SPEC BASIS: Find the sub-sequence of a dictionary, x, ... where the keys are letters
    PROPERTY: All elements in the returned list must be keys present in the input dictionary.
    """
    result = task_func(x)
    input_keys = set(x.keys())
    for item in result:
        assert item in input_keys, f"Returned item '{item}' is not a key in the input dictionary {x.keys()}"

@given(x=st.dictionaries(
    keys=st.text(st.ascii_lowercase, min_size=1, max_size=1),
    values=st.integers(min_value=-10, max_value=10),
    min_size=1, max_size=5
))
@settings(max_examples=50, deadline=None)
def test_returned_list_is_non_empty(x):
    """
    SPEC BASIS: Example: >>> task_func({'a': 1, 'b': 2, 'c': 3}) ['a']
    PROPERTY: The returned list must not be empty, even if the empty subsequence has a sum of 0.
    """
    # Both examples return non-empty lists, even when the empty list (sum 0)
    # would be mathematically smaller or equal to the returned sum.
    result = task_func(x)
    assert len(result) > 0, f"Returned an empty list, but examples imply non-empty output. Input: {x}"

@given(x=st.dictionaries(
    keys=st.text(st.ascii_lowercase, min_size=1, max_size=1),
    values=st.integers(min_value=-10, max_value=10),
    min_size=1, max_size=5
))
@settings(max_examples=50, deadline=None)
def test_output_is_deterministic_for_same_input(x):
    """
    SPEC BASIS: (Implicit from function definition)
    PROPERTY: Calling the function multiple times with the same input should yield the same output.
    """
    result1 = task_func(x)
    result2 = task_func(x)
    # The problem does not specify the order of keys in the output list if multiple
    # subsequences have the same minimum sum. So we sort for comparison.
    assert sorted(result1) == sorted(result2), \
        f"Non-deterministic output for input {x}: {result1} vs {result2}"

@given(x=st.dictionaries(
    keys=st.text(st.ascii_lowercase, min_size=1, max_size=1),
    values=st.integers(min_value=-10, max_value=10),
    min_size=1, max_size=5
))
@settings(max_examples=50, deadline=None)
def test_returned_subsequence_sum_is_minimum(x):
    """
    SPEC BASIS: Find the sub-sequence of a dictionary, x, with the minimum total length
    PROPERTY: The sum of lengths for the returned subsequence must be the minimum possible among all non-empty subsequences.
    """
    all_keys = list(x.keys())
    all_non_empty_subsequences = _get_all_non_empty_subsequences(all_keys)

    if not all_non_empty_subsequences: # Should not happen with min_size=1
        return

    min_sum_oracle = float('inf')
    for sub in all_non_empty_subsequences:
        current_sum = _calculate_subsequence_sum(sub, x)
        if current_sum < min_sum_oracle:
            min_sum_oracle = current_sum

    result = task_func(x)
    result_sum = _calculate_subsequence_sum(result, x)

    assert result_sum == min_sum_oracle, \
        f"Returned subsequence {result} has sum {result_sum}, but minimum possible sum is {min_sum_oracle} for input {x}"

@given(x=st.dictionaries(
    keys=st.text(st.ascii_lowercase, min_size=1, max_size=1),
    values=st.integers(min_value=-10, max_value=10),
    min_size=1, max_size=5
))
@settings(max_examples=50, deadline=None)
def test_returned_subsequence_keys_are_unique(x):
    """
    SPEC BASIS: Find the sub-sequence of a dictionary, x, ...
    PROPERTY: The returned list should not contain duplicate keys.
    """
    # A "sub-sequence" typically implies unique elements from the original sequence/set.
    # If a key appeared twice, it would imply summing its value twice, which is not how
    # dictionary keys work in a subsequence context.
    result = task_func(x)
    assert len(result) == len(set(result)), \
        f"Returned subsequence {result} contains duplicate keys for input {x}"

@given(x=st.dictionaries(
    keys=st.text(st.ascii_lowercase, min_size=1, max_size=1),
    values=st.integers(min_value=-10, max_value=10),
    min_size=1, max_size=5
))
@settings(max_examples=50, deadline=None)
def test_single_element_dict_returns_that_element(x):
    """
    SPEC BASIS: Example: >>> task_func({'a': 1, 'b': 2, 'c': 3}) ['a'] (implies single element if it's the min)
    PROPERTY: For a dictionary with a single key-value pair, the function should return a list containing that key.
    """
    if len(x) == 1:
        key = list(x.keys())[0]
        result = task_func(x)
        assert result == [key], f"Expected [{key}] for single-element dict {x}, got {result}"

@given(x=st.dictionaries(
    keys=st.text(st.ascii_lowercase, min_size=1, max_size=1),
    values=st.integers(min_value=0, max_value=0), # All values are 0
    min_size=1, max_size=5
))
@settings(max_examples=50, deadline=None)
def test_all_zero_values_returns_single_key(x):
    """
    SPEC BASIS: Example: >>> task_func({'a': 1, 'b': 2, 'c': 3}) ['a'] (implies smallest positive sum)
    PROPERTY: If all values are zero, the function should return a list containing a single key.
    """
    # Following the logic from the positive-value example, if all sums are 0,
    # the smallest non-empty subsequence sum is 0. A single key with value 0
    # achieves this. The problem doesn't specify which key if multiple exist.
    result = task_func(x)
    assert len(result) == 1, f"Expected a single-element list for all zero values, got {result}"
    assert result[0] in x.keys(), f"Returned key {result[0]} not in input keys {x.keys()}"
    assert _calculate_subsequence_sum(result, x) == 0, \
        f"Expected sum 0, got {_calculate_subsequence_sum(result, x)} for input {x}"