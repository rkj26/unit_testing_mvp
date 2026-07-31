# SEARCH PLAN:
# 1. Empty list: Explicitly defined behavior for an empty input, a common boundary case.
# 2. Conservation of total count: The sum of all counts in the input must equal the sum of 'Total Count' in the output.
# 3. Average count correctness: Verify the 'Average Count' for each fruit by recomputing it from the input data.
# 4. Duplicate fruit names: Use a small alphabet for fruit names to ensure high duplication, targeting aggregation logic.
# 5. Single fruit type: Test the edge case where all input entries belong to the same fruit.

import pandas as pd
import numpy as np
from candidate import task_func
from hypothesis import given, settings, strategies as st
import collections
import math

@settings(max_examples=50, deadline=None)
@given(fruit_data=st.just([]))
def test_empty_input_returns_empty_dataframe(fruit_data):
    """
    SPEC BASIS: "If fruit_data is an empty list, an empty dataFrame is returned."
    PROPERTY: The function returns an empty pandas DataFrame with the specified columns.
    STRATEGY: Provide an empty list as input, directly testing the specified edge case.
    """
    try:
        result = task_func(fruit_data)
    except Exception:
        result = None

    assert result is not None, "Function should not raise an exception for an empty list."
    assert isinstance(result, pd.DataFrame), "Result should be a pandas DataFrame."
    assert result.empty, "DataFrame should be empty for empty input."
    assert list(result.columns) == ['Total Count', 'Average Count'], \
        f"Columns should be ['Total Count', 'Average Count'], but got {list(result.columns)}"
    assert result.index.name is None, "Index name should be None for an empty DataFrame."


@settings(max_examples=50, deadline=None)
@given(fruit_data=st.lists(
    st.tuples(
        st.sampled_from(['apple', 'banana', 'cherry', 'date', 'elderberry']), # Small alphabet to encourage duplicates
        st.integers(min_value=0, max_value=100) # Include 0 as a valid count
    ),
    min_size=1, max_size=12 # Ensure non-empty lists for this test
))
def test_total_count_conservation_and_index_names(fruit_data):
    """
    SPEC BASIS: "Calculate and return the total and average counts for each type of fruit."
                "Each row's index is the fruit name."
    PROPERTY: The sum of 'Total Count' in the output DataFrame equals the sum of all input counts.
              The DataFrame index contains all unique fruit names from the input.
              The DataFrame has the correct column names.
    STRATEGY: Generate lists with varying fruit names and counts, including duplicates and zero counts.
              This targets the overall aggregation and correct indexing.
    """
    try:
        result = task_func(fruit_data)
    except Exception:
        result = None

    assert result is not None, "Function should not raise an exception for valid input."
    assert isinstance(result, pd.DataFrame), "Result should be a pandas DataFrame."
    assert not result.empty, "DataFrame should not be empty for non-empty input."

    # Property 1: Sum of 'Total Count' in output equals sum of all input counts
    expected_total_sum = sum(count for _, count in fruit_data)
    actual_total_sum = result['Total Count'].sum()
    assert actual_total_sum == expected_total_sum, \
        f"Total sum of counts mismatch. Expected: {expected_total_sum}, Got: {actual_total_sum}"

    # Property 2: Index contains all unique fruit names from input
    unique_input_fruits = set(fruit for fruit, _ in fruit_data)
    actual_output_fruits = set(result.index)
    assert actual_output_fruits == unique_input_fruits, \
        f"Mismatch in unique fruit names. Expected: {unique_input_fruits}, Got: {actual_output_fruits}"

    # Property 3: Correct column names
    assert list(result.columns) == ['Total Count', 'Average Count'], \
        f"Columns should be ['Total Count', 'Average Count'], but got {list(result.columns)}"


@settings(max_examples=50, deadline=None)
@given(fruit_data=st.lists(
    st.tuples(
        st.sampled_from(['a', 'b', 'c', 'd']), # Very small alphabet to guarantee many duplicates
        st.integers(min_value=0, max_value=100)
    ),
    min_size=1, max_size=12
))
def test_average_count_calculation(fruit_data):
    """
    SPEC BASIS: "Calculate and return the total and average counts for each type of fruit."
    PROPERTY: For each fruit, the 'Average Count' in the output DataFrame is correctly calculated
              as its 'Total Count' divided by the number of times it appeared in the input.
    STRATEGY: Generate lists with high duplication of fruit names to thoroughly test the averaging logic.
              This is a metamorphic check where we recompute the expected average from the input.
    """
    try:
        result = task_func(fruit_data)
    except Exception:
        result = None

    assert result is not None, "Function should not raise an exception for valid input."
    assert isinstance(result, pd.DataFrame), "Result should be a pandas DataFrame."
    assert not result.empty, "DataFrame should not be empty for non-empty input."

    # Calculate expected totals and counts for each fruit from the input
    fruit_totals = collections.defaultdict(int)
    fruit_occurrences = collections.defaultdict(int)
    for fruit, count in fruit_data:
        fruit_totals[fruit] += count
        fruit_occurrences[fruit] += 1

    # Verify 'Total Count' and 'Average Count' for each fruit
    for fruit_name, total_count in fruit_totals.items():
        assert fruit_name in result.index, f"Fruit '{fruit_name}' missing from DataFrame index."

        actual_total_count = result.loc[fruit_name, 'Total Count']
        assert actual_total_count == total_count, \
            f"Total count for '{fruit_name}' mismatch. Expected: {total_count}, Got: {actual_total_count}"

        expected_average_count = total_count / fruit_occurrences[fruit_name]
        actual_average_count = result.loc[fruit_name, 'Average Count']

        # Use math.isclose for float comparison
        assert math.isclose(actual_average_count, expected_average_count, rel_tol=1e-9), \
            f"Average count for '{fruit_name}' mismatch. Expected: {expected_average_count}, Got: {actual_average_count}"


@settings(max_examples=50, deadline=None)
@given(counts=st.lists(st.integers(min_value=0, max_value=100), min_size=1, max_size=12))
def test_single_fruit_type_multiple_entries(counts):
    """
    SPEC BASIS: "Calculate and return the total and average counts for each type of fruit."
                "The results are returned as a pandas DataFrame with each row representing a different fruit."
    PROPERTY: When all input entries are for the same fruit, the output DataFrame has exactly one row,
              and its total and average counts are correct.
    STRATEGY: Generate lists where all tuples share the same fruit name ('apple') but have varying counts.
              This targets the aggregation logic for a single fruit type with multiple data points.
    """
    fruit_data = [('apple', count) for count in counts]
    
    try:
        result = task_func(fruit_data)
    except Exception:
        result = None

    assert result is not None, "Function should not raise an exception for valid input."
    assert isinstance(result, pd.DataFrame), "Result should be a pandas DataFrame."
    assert len(result) == 1, f"DataFrame should have 1 row, but got {len(result)}."
    assert 'apple' in result.index, "DataFrame index should contain 'apple'."

    expected_total_count = sum(counts)
    expected_average_count = sum(counts) / len(counts)

    actual_total_count = result.loc['apple', 'Total Count']
    actual_average_count = result.loc['apple', 'Average Count']

    assert actual_total_count == expected_total_count, \
        f"Total count for 'apple' mismatch. Expected: {expected_total_count}, Got: {actual_total_count}"
    assert math.isclose(actual_average_count, expected_average_count, rel_tol=1e-9), \
        f"Average count for 'apple' mismatch. Expected: {expected_average_count}, Got: {actual_average_count}"