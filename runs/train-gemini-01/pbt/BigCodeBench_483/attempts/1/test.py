# SEARCH PLAN:
# 1. Empty Pattern: Test the explicit requirement for an empty pattern to return an unaltered copy.
# 2. No Matching Words: Verify that the DataFrame remains unchanged if no words in the target column match the pattern.
# 3. All Matching Words: Ensure that if all words in a cell match, their order is fully reversed.
# 4. Mixed Matching/Non-Matching Words: Test the core logic of reversing only matching words while preserving non-matching ones.
#    (Note: The provided examples contradict the "Reverse the order of words" instruction. Following the explicit text of the specification over potentially misleading examples.)

import re
import pandas as pd
from candidate import task_func
from hypothesis import given, settings, strategies as st
from collections import Counter

# Helper strategy for generating column names
column_names_st = st.text(st.ascii_lowercase, min_size=1, max_size=5)

# Helper strategy for generating words (alphanumeric, to simplify regex matching)
word_st = st.text(st.ascii_lowercase + st.digits, min_size=1, max_size=8)

# Strategy for generating cell content (space-separated words)
cell_content_st = st.lists(word_st, min_size=0, max_size=5).map(lambda words: ' '.join(words))

# Strategy for generating DataFrames
@st.composite
def dataframes_st(draw):
    num_rows = draw(st.integers(min_value=1, max_value=5))
    num_cols = draw(st.integers(min_value=1, max_value=3))
    
    # Ensure at least one column for the target
    all_col_names = draw(st.lists(column_names_st, min_size=num_cols, max_size=num_cols).map(lambda x: list(set(x))))
    
    data = {}
    for col_name in all_col_names:
        if draw(st.booleans()): # Mix of string and integer columns
            data[col_name] = draw(st.lists(cell_content_st, min_size=num_rows, max_size=num_rows))
        else:
            data[col_name] = draw(st.lists(st.integers(-100, 100), min_size=num_rows, max_size=num_rows))
            
    df = pd.DataFrame(data)
    
    # Ensure the target column exists and is a string type
    target_column = draw(st.sampled_from(all_col_names))
    if not pd.api.types.is_string_dtype(df[target_column]):
        df[target_column] = df[target_column].astype(str) # Convert to string if not already
    
    return df, target_column

# Strategy for generating regex patterns
# Focus on simple word matching patterns for clarity and to avoid overly complex regex issues
# Include empty pattern as a specific edge case
pattern_st = st.one_of(
    st.just(""), # Empty pattern
    st.text(st.sampled_from(list("abcxyz") + ['|', '\\b']), min_size=1, max_size=10).map(lambda s: r'\b(?:' + s + r')\b'),
    st.text(st.ascii_lowercase, min_size=1, max_size=5).map(lambda s: r'\b' + s + r'\b') # Simple word patterns
)


@settings(max_examples=50, deadline=None)
@given(df_and_col=dataframes_st(), pattern=st.just(""))
def test_empty_pattern_returns_unaltered_copy(df_and_col, pattern):
    """
    SPEC BASIS: "returning a copy of the unaltered DataFrame if the pattern is empty."
    PROPERTY: The returned DataFrame is a new object, but its contents are identical to the original.
    STRATEGY: Generate various DataFrames and always use an empty pattern.
    """
    df, column_name = df_and_col
    original_df_copy = df.copy(deep=True)

    try:
        result_df = task_func(df, column_name, pattern)
    except Exception:
        result_df = None
    
    assert result_df is not None, "task_func should not raise an exception for valid inputs."
    assert result_df is not df, "The function should return a new DataFrame object, not modify in place."
    pd.testing.assert_frame_equal(result_df, original_df_copy, check_dtype=True)


@settings(max_examples=50, deadline=None)
@given(df_and_col=dataframes_st(), pattern=pattern_st.filter(lambda p: p != ""))
def test_no_matching_words_leaves_column_unchanged(df_and_col, pattern):
    """
    SPEC BASIS: "maintains the original order of non-matching words." (implies if all are non-matching)
    PROPERTY: If no words in the target column match the pattern, the column's content remains unchanged.
    STRATEGY: Generate DataFrames and patterns. Filter inputs to ensure no words in the target column match the pattern.
              This is done by checking the pattern against all words in the column before calling task_func.
    """
    df, column_name = df_and_col
    original_df_copy = df.copy(deep=True)

    # Filter out cases where the pattern might accidentally match
    # This is a light filter to ensure the property holds for the intended scenario
    all_words_in_column = []
    for cell_value in df[column_name]:
        if isinstance(cell_value, str):
            all_words_in_column.extend(cell_value.split())
    
    # Ensure the pattern does not match any word in the column
    if any(re.search(pattern, word) for word in all_words_in_column):
        st.assume(False) 

    try:
        result_df = task_func(df, column_name, pattern)
    except Exception:
        result_df = None
    
    assert result_df is not None, "task_func should not raise an exception for valid inputs."
    assert result_df is not df, "The function should return a new DataFrame object."
    pd.testing.assert_frame_equal(result_df, original_df_copy, check_dtype=True)


@settings(max_examples=50, deadline=None)
@given(df_and_col=dataframes_st(), pattern=pattern_st.filter(lambda p: p != ""))
def test_all_words_matching_reverses_entire_cell(df_and_col, pattern):
    """
    SPEC BASIS: "Reverse the order of words in a specific column... where the words match"
    PROPERTY: If all words in a cell match the pattern, the entire sequence of words in that cell is reversed.
    STRATEGY: Generate DataFrames and patterns. Filter inputs to ensure all words in the target column's cells match the pattern.
    """
    df, column_name = df_and_col
    original_df_copy = df.copy(deep=True)
    
    expected_series = original_df_copy[column_name].copy()

    for idx, cell_value in enumerate(df[column_name]):
        if not isinstance(cell_value, str):
            cell_value = str(cell_value)

        words = cell_value.split()
        if not words: # Handle empty strings
            continue

        # Ensure all words in the current cell match the pattern
        if not all(re.search(pattern, word) for word in words):
            st.assume(False) # Discard if not all words match

        # If all words match, the expected behavior is a full reversal of the words
        expected_series.iloc[idx] = ' '.join(words[::-1])

    try:
        result_df = task_func(df, column_name, pattern)
    except Exception:
        result_df = None
    
    assert result_df is not None, "task_func should not raise an exception for valid inputs."
    assert result_df is not df, "The function should return a new DataFrame object."
    pd.testing.assert_series_equal(result_df[column_name], expected_series, check_dtype=True)
    # Check other columns are untouched
    for col in df.columns:
        if col != column_name:
            pd.testing.assert_series_equal(result_df[col], original_df_copy[col], check_dtype=True)


@settings(max_examples=50, deadline=None)
@given(df_and_col=dataframes_st(), pattern=pattern_st.filter(lambda p: p != ""))
def test_mixed_matching_non_matching_words_reversal(df_and_col, pattern):
    """
    SPEC BASIS: "Reverse the order of words... where the words match... This function maintains the original order of non-matching words."
    PROPERTY: Only words matching the pattern are reversed, while non-matching words retain their original positions relative to each other and to the groups of matching words.
    STRATEGY: Generate DataFrames and patterns. For each cell, identify matching and non-matching words. Construct the expected output by reversing only the matching words within their identified groups.
              This test specifically targets cases where there's a mix of matching and non-matching words.
    """
    df, column_name = df_and_col
    original_df_copy = df.copy(deep=True)
    
    expected_series = original_df_copy[column_name].copy()

    for idx, cell_value in enumerate(df[column_name]):
        if not isinstance(cell_value, str):
            cell_value = str(cell_value)

        words = cell_value.split()
        if not words:
            continue

        # Collect indices of matching words
        matching_indices = [i for i, word in enumerate(words) if re.search(pattern, word)]
        
        # Filter to ensure this is a "mixed" case: some matches, but not all words match.
        if not matching_indices or len(matching_indices) == len(words):
            st.assume(False) 

        new_words_list = list(words)
        
        # Extract matching words in their original order
        extracted_matching_words = [words[i] for i in matching_indices]
        # Reverse them
        reversed_extracted_matching_words = extracted_matching_words[::-1]
        
        # Place the reversed words back into their original matching positions
        for i, original_idx in enumerate(matching_indices):
            new_words_list[original_idx] = reversed_extracted_matching_words[i]
        
        expected_series.iloc[idx] = ' '.join(new_words_list)

    try:
        result_df = task_func(df, column_name, pattern)
    except Exception:
        result_df = None
    
    assert result_df is not None, "task_func should not raise an exception for valid inputs."
    assert result_df is not df, "The function should return a new DataFrame object."
    pd.testing.assert_series_equal(result_df[column_name], expected_series, check_dtype=True)
    # Check other columns are untouched
    for col in df.columns:
        if col != column_name:
            pd.testing.assert_series_equal(result_df[col], original_df_copy[col], check_dtype=True)