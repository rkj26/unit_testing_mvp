# SEARCH PLAN:
# 1. Boundary `data_list` sizes: empty list, single-element list, small lists (1-12 elements).
# 2. Boundary string content: single comma-separated value, multiple values, values with leading/trailing whitespace, duplicate values.
# 3. Whitespace handling: strings with leading/trailing whitespace for the whole string, and for individual comma-separated values.
# 4. Reproducibility with seed: ensure identical outputs for identical inputs and seeds.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import pandas as pd
import re

# Helper strategy for generating comma-separated values
# Ensures values are non-empty and can contain spaces
value_strategy = st.text(
    st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')) | st.just(' '),
    min_size=1, max_size=8
).map(lambda s: s.strip()).filter(lambda s: len(s) > 0) # Ensure values are non-empty after stripping

# Strategy for generating a single comma-separated string
# Includes cases for single values, multiple values, and values with internal/external whitespace
comma_separated_string_strategy = st.one_of(
    # Single value string
    value_strategy,
    # Multiple values string
    st.lists(value_strategy, min_size=1, max_size=5).map(lambda l: ','.join(l)),
    # String with leading/trailing whitespace for the whole string
    st.builds(
        lambda s, ws_l, ws_r: ws_l + s + ws_r,
        st.lists(value_strategy, min_size=1, max_size=3).map(lambda l: ','.join(l)),
        st.text(st.just(' '), min_size=1, max_size=3),
        st.text(st.just(' '), min_size=1, max_size=3)
    ),
    # String with whitespace around individual values
    st.lists(
        st.builds(
            lambda v, ws_l, ws_r: ws_l + v + ws_r,
            value_strategy,
            st.text(st.just(' '), min_size=0, max_size=2),
            st.text(st.just(' '), min_size=0, max_size=2)
        ),
        min_size=1, max_size=5
    ).map(lambda l: ','.join(l))
)

# Strategy for the data_list parameter
data_list_strategy = st.lists(comma_separated_string_strategy, min_size=0, max_size=12)

@settings(max_examples=50, deadline=None)
@given(data_list=data_list_strategy, seed=st.integers(min_value=0, max_value=100))
def test_dataframe_structure_and_row_count(data_list, seed):
    """
    SPEC BASIS: "Returns: - DataFrame: a pandas DataFrame with columns 'Original String' and 'Modified String'."
                "Removes a random comma-separated value ... from each string in a list".
    PROPERTY: The output is a pandas DataFrame, has exactly two columns named 'Original String' and 'Modified String',
              and has the same number of rows as the input `data_list`.
    STRATEGY: Generate `data_list` with `min_size=0` to cover empty input, `min_size=1` for single-element input,
              and up to `max_size=12` for typical cases. String content varies to ensure robustness.
    """
    try:
        df = task_func(data_list, seed=seed)
    except Exception:
        df = None

    assert df is not None, "task_func should not raise an exception for valid inputs."
    assert isinstance(df, pd.DataFrame), "Output must be a pandas DataFrame."
    assert list(df.columns) == ['Original String', 'Modified String'], \
        "DataFrame columns must be 'Original String' and 'Modified String'."
    assert len(df) == len(data_list), \
        f"DataFrame must have {len(data_list)} rows, but got {len(df)}."

@settings(max_examples=50, deadline=None)
@given(data_list=st.lists(comma_separated_string_strategy.filter(lambda s: len(s.strip()) > 0), min_size=1, max_size=12),
       seed=st.integers(min_value=0, max_value=100))
def test_modified_string_content_one_item_removed(data_list, seed):
    """
    SPEC BASIS: "Removes a random comma-separated value (treated as a "substring") from each string in a list".
                "The function will remove leading and trailing whitespaces first before processing."
    PROPERTY: For each original string, the modified string must contain all but one of the original
              comma-separated values. The order of values is not fixed, so compare sets of values.
              If an original string has only one value, the modified string should be empty.
    STRATEGY: Generate `data_list` with at least one non-empty string. Include strings with single values,
              multiple values, and duplicate values to ensure correct removal logic.
    """
    try:
        df = task_func(data_list, seed=seed)
    except Exception:
        df = None

    assert df is not None, "task_func should not raise an exception for valid inputs."
    assert len(df) == len(data_list), "DataFrame row count must match input list length."

    for _, row in df.iterrows():
        original_str = row['Original String']
        modified_str = row['Modified String']

        # Normalize original string: strip overall whitespace, then split and strip each value
        original_values = [v.strip() for v in original_str.split(',')]
        original_values = [v for v in original_values if v] # Filter out empty strings from split if any

        # Normalize modified string: strip overall whitespace, then split and strip each value
        modified_values = [v.strip() for v in modified_str.split(',')]
        modified_values = [v for v in modified_values if v] # Filter out empty strings from split if any

        if not original_values: # If original string was empty or only whitespace
            assert not modified_values, "Modified string should be empty if original was empty/whitespace."
            continue

        # Check if exactly one item was removed
        # Use counts to handle duplicates correctly
        from collections import Counter
        original_counts = Counter(original_values)
        modified_counts = Counter(modified_values)

        # The difference in counts should be exactly one item with a count of 1
        diff_counts = original_counts - modified_counts
        assert sum(diff_counts.values()) == 1, \
            f"Expected exactly one item to be removed. Original: '{original_str}' ({original_values}), Modified: '{modified_str}' ({modified_values}). Difference: {diff_counts}"
        assert all(count == 1 for count in diff_counts.values()), \
            f"Expected exactly one item to be removed, not multiple instances of the same item or different items. Original: '{original_str}' ({original_values}), Modified: '{modified_str}' ({modified_values}). Difference: {diff_counts}"

        # Ensure the removed item was actually present in the original
        removed_item = list(diff_counts.keys())[0]
        assert original_counts[removed_item] > 0, \
            f"Removed item '{removed_item}' was not present in original string '{original_str}'."

@settings(max_examples=50, deadline=None)
@given(data_list=data_list_strategy, seed=st.integers(min_value=0, max_value=100))
def test_whitespace_handling_and_output_format(data_list, seed):
    """
    SPEC BASIS: "The function will remove leading and trailing whitespaces first before processing."
                "Removes a random comma-separated value (treated as a "substring") from each string".
    PROPERTY: Leading/trailing whitespace on the *entire string* and around *individual values*
              should be handled correctly. The modified string should also be properly formatted
              (no extra leading/trailing commas, no double commas, no leading/trailing whitespace).
    STRATEGY: Generate strings with various whitespace patterns: leading/trailing whitespace for
              the whole string, whitespace around individual values.
    """
    try:
        df = task_func(data_list, seed=seed)
    except Exception:
        df = None

    assert df is not None, "task_func should not raise an exception for valid inputs."

    for _, row in df.iterrows():
        modified_str = row['Modified String']

        # Check for overall leading/trailing whitespace in the modified string
        assert modified_str == modified_str.strip(), \
            f"Modified string '{modified_str}' should not have leading/trailing whitespace."

        # Check for empty string case
        if not modified_str:
            continue

        # Check for leading/trailing commas or double commas
        assert not modified_str.startswith(','), \
            f"Modified string '{modified_str}' should not start with a comma."
        assert not modified_str.endswith(','), \
            f"Modified string '{modified_str}' should not end with a comma."
        assert ',,' not in modified_str, \
            f"Modified string '{modified_str}' should not contain double commas."

        # Check for whitespace around individual values in the modified string
        modified_values = modified_str.split(',')
        for val in modified_values:
            assert val == val.strip(), \
                f"Individual value '{val}' in modified string '{modified_str}' should not have leading/trailing whitespace."
            assert len(val) > 0, \
                f"Individual value '{val}' in modified string '{modified_str}' should not be empty."


@settings(max_examples=50, deadline=None)
@given(data_list=data_list_strategy, seed=st.integers(min_value=0, max_value=100))
def test_reproducibility_with_seed(data_list, seed):
    """
    SPEC BASIS: "seed (int, optional): Seed for the random number generator for reproducibility."
    PROPERTY: Calling `task_func` with the same `data_list` and `seed` should always produce
              the exact same DataFrame.
    STRATEGY: Call `task_func` twice with identical inputs and assert deep equality of the DataFrames.
    """
    try:
        df1 = task_func(data_list, seed=seed)
        df2 = task_func(data_list, seed=seed)
    except Exception:
        df1 = None
        df2 = None

    assert df1 is not None and df2 is not None, "task_func should not raise an exception for valid inputs."
    pd.testing.assert_frame_equal(df1, df2), \
        "Calling task_func with the same data_list and seed should produce identical DataFrames."