# SEARCH PLAN:
# 1. Boundary: empty input list, list with empty sub-lists, single-element sub-lists.
# 2. Structural: sub-lists with duplicate index elements, mixed types (int/str) for indices.
# 3. Invariant: check output list length, type of elements, and properties of Series indices and values.
# 4. Metamorphic: check that the set of values in each Series is a permutation of `range(1, length + 1)`.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import pandas as pd
import numpy as np
from collections import Counter

# Strategy for elements within sub-lists (indices for Series)
# Using a small alphabet and integers to encourage duplicates and varied types.
index_elements = st.one_of(
    st.integers(min_value=-10, max_value=10),
    st.sampled_from(['a', 'b', 'c', 'x', 'y', 'z', 'key1', 'key2'])
)

# Strategy for sub-lists (Series indices)
# Covers empty, single-element, and lists with duplicates.
sub_lists_strategy = st.lists(
    index_elements,
    min_size=0,
    max_size=10  # Keep sub-list length small for performance and to hit boundaries
)

# Strategy for the main input list_of_lists
# Covers empty, single sub-list, and multiple sub-lists.
list_of_lists_strategy = st.lists(
    sub_lists_strategy,
    min_size=0,
    max_size=5  # Keep number of Series small
)


@settings(max_examples=50, deadline=None)
@given(list_of_lists=list_of_lists_strategy)
def test_output_structure_and_length(list_of_lists):
    """
    SPEC BASIS: "This function returns a list. Each element in this list is a pandas Series object."
                "The Series objects are indexed by the elements of the sub-lists provided in `list_of_lists`."
    PROPERTY: The output is a list of pandas Series objects, and its length matches the input `list_of_lists`.
              Each element in the output list must be an instance of `pd.Series`.
    STRATEGY: Target boundary cases for `list_of_lists`: empty list, list with one empty sub-list,
              list with one non-empty sub-list, list with multiple sub-lists (some empty, some with one element,
              some with duplicates). This catches off-by-one errors in loop bounds or incorrect list construction.
    """
    try:
        result_series_list = task_func(list_of_lists)
    except Exception:
        result_series_list = None

    assert result_series_list is not None, "Function should not raise an exception for valid inputs."
    assert isinstance(result_series_list, list), "Output must be a list."
    assert len(result_series_list) == len(list_of_lists), \
        f"Output list length ({len(result_series_list)}) must match input list_of_lists length ({len(list_of_lists)})."

    for s in result_series_list:
        assert isinstance(s, pd.Series), "Each element in the output list must be a pandas Series."


@settings(max_examples=50, deadline=None)
@given(list_of_lists=list_of_lists_strategy)
def test_series_index_preservation(list_of_lists):
    """
    SPEC BASIS: "Each Series is indexed by the elements of a sub-list from `list_of_lists`."
    PROPERTY: For each generated Series, its index (converted to a list) must be identical to the
              corresponding input sub-list.
    STRATEGY: Use sub-lists with diverse index types: integers, strings, mixed types, duplicates,
              single element, empty. This ensures the index is correctly assigned, even with
              challenging index values.
    """
    try:
        result_series_list = task_func(list_of_lists)
    except Exception:
        result_series_list = None

    assert result_series_list is not None, "Function should not raise an exception for valid inputs."

    for i, s in enumerate(result_series_list):
        expected_index = list_of_lists[i]
        actual_index = s.index.tolist()
        assert actual_index == expected_index, \
            f"Series index {actual_index} does not match expected index {expected_index} for sub-list {i}."


@settings(max_examples=50, deadline=None)
@given(list_of_lists=list_of_lists_strategy)
def test_series_values_properties(list_of_lists):
    """
    SPEC BASIS: "Each Series contains unique integers starting from 1 and going up to the length of the respective sub-list."
                "These integers are shuffled randomly to create a unique ordering for each Series."
    PROPERTY: For each Series, its values must be unique integers, and the set of these values must be
              exactly `set(range(1, length_of_sublist + 1))`. The data type of the Series values must be integer.
    STRATEGY: Test with sub-lists of varying lengths (0, 1, small, up to 10) and with duplicate index elements.
              This covers the range, uniqueness, and data type requirements for the Series values.
              The use of `Counter` handles the "shuffled randomly" aspect by comparing sets of values.
    """
    try:
        result_series_list = task_func(list_of_lists)
    except Exception:
        result_series_list = None

    assert result_series_list is not None, "Function should not raise an exception for valid inputs."

    for i, s in enumerate(result_series_list):
        sub_list_length = len(list_of_lists[i])

        # Property: Data type of values
        assert pd.api.types.is_integer_dtype(s.dtype), \
            f"Series values for sub-list {i} must be of integer type, but got {s.dtype}."

        # Property: Values are unique and within the specified range
        if sub_list_length == 0:
            assert len(s.values) == 0, f"Empty Series should have no values, but got {s.values} for sub-list {i}."
            continue

        expected_values_set = set(range(1, sub_list_length + 1))
        actual_values_set = set(s.values)

        assert actual_values_set == expected_values_set, \
            f"Series values for sub-list {i} (length {sub_list_length}) are {s.values}. " \
            f"Expected set of values {expected_values_set}, but got {actual_values_set}."

        # Ensure values are unique within the Series (set comparison already implies this, but explicit check)
        assert len(s.values) == len(actual_values_set), \
            f"Series values for sub-list {i} are not unique: {s.values}."

# Note: The problem statement implies that `np.random.seed(0)` in the example is for reproducibility of the example itself,
# not that `task_func` should internally set a seed. Hypothesis ensures reproducibility of the test suite by seeding
# its own random number generator, which in turn influences the strategies. If `task_func` uses `np.random.shuffle`
# without an explicit `np.random.seed()` call *within the function*, then its behavior will be influenced by the global
# numpy random state, which might be affected by other parts of the test environment or previous tests.
# However, the properties tested (set of values, index, length, type) are invariant to the specific shuffle order,
# so this is robust against the randomness.