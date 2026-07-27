import itertools
import math
import string
import pytest
from hypothesis import given, settings, strategies as st

from candidate import task_func

@given(x=st.just({'a': 1, 'b': 2, 'c': 3}))
@settings(max_examples=50, deadline=None)
def test_example_one(x):
    """
    SPEC BASIS: Example 1 in problem description.
    PROPERTY: The function correctly identifies the single minimum positive length.
    """
    assert task_func(x) == ['a']

@given(x=st.just({'a': 1, 'b': -2, 'c': -5, 'd': 4}))
@settings(max_examples=50, deadline=None)
def test_example_two(x):
    """
    SPEC BASIS: Example 2 in problem description.
    PROPERTY: The function correctly identifies the minimum total length from multiple negative values.
    """
    # The problem does not specify the order of keys in the output list.
    # We sort both for comparison to ensure the content is correct.
    assert sorted(task_func(x)) == sorted(['b', 'c'])

@given(x=st.just({}))
@settings(max_examples=50, deadline=None)
def test_empty_dictionary(x):
    """
    SPEC BASIS: Boundary case (implicit).
    PROPERTY: An empty dictionary should result in an empty list, as its sum (0) is the minimum possible.
    """
    assert task_func(x) == []

@given(
    x=st.dictionaries(
        keys=st.sampled_from(string.ascii_lowercase),
        values=st.integers(min_value=-100, max_value=-1), # All values are negative
        min_size=1,
        max_size=10
    )
)
@settings(max_examples=50, deadline=None)
def test_all_negative_values(x):
    """
    SPEC BASIS: Output invariant (derived from "minimum total length").
    PROPERTY: If all values in the dictionary are negative, the subsequence with the minimum total length must include all keys.
    """
    # If all values are negative, adding any key will decrease the sum.
    # Therefore, to achieve the minimum sum, all keys must be included.
    assert sorted(task_func(x)) == sorted(list(x.keys()))

@given(
    x=st.dictionaries(
        keys=st.sampled_from(string.ascii_lowercase),
        values=st.integers(min_value=-10, max_value=10), # Keep values small for sum calculation
        min_size=0,
        max_size=5 # Keep dictionary small to make iterating all subsequences feasible
    )
)
@settings(max_examples=50, deadline=None)
def test_output_sum_is_minimal(x):
    """
    SPEC BASIS: "Find the sub-sequence ... with the minimum total length."
    PROPERTY: The sum of lengths for the returned subsequence must be less than or equal to the sum of lengths for any other possible subsequence.
    """
    result_subsequence = task_func(x)
    result_sum = sum(x[key] for key in result_subsequence)

    # Generate all possible subsequences of keys
    all_keys = list(x.keys())
    min_overall_sum = float('inf')

    # An empty subsequence has a sum of 0. This is important if all values are positive.
    min_overall_sum = 0

    # Iterate through all combinations of keys to find the true minimum sum
    for r in range(1, len(all_keys) + 1):
        for combo in itertools.combinations(all_keys, r):
            current_sum = sum(x[key] for key in combo)
            if current_sum < min_overall_sum:
                min_overall_sum = current_sum
    
    assert result_sum == min_overall_sum