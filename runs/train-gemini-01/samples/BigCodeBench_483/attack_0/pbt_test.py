# SEARCH PLAN:
# 1. Empty Pattern: Explicitly test the requirement for an empty pattern to return an unaltered copy.
# 2. No Matching Words: Verify the DataFrame is unchanged if no words in the target column match the pattern.
# 3. All Words Matching: Ensure that if all words in a cell match, their order is fully reversed.
# 4. Mixed Matching/Non-Matching: Test the core logic of reversing only matching words while preserving non-matching ones.
# 5. Edge Cases for Words/Cells: Test with empty cells, single-word cells, and patterns matching parts of words.

import re
import pandas as pd
from candidate import task_func
from hypothesis import given, settings, strategies as st
from collections import Counter
import string

# Helper strategy for generating column names
column_names_st = st.text(string.ascii_lowercase, min_size=1, max_size=5)

# Helper strategy for generating words (alphanumeric, to simplify regex matching)
# Include some special characters that might appear in regex patterns but not in words
word_char_st = st.sampled_from(string.ascii_lowercase + string.digits + "-_")
word_st = st.text(word_char_st, min_size=1, max_size=8)

# Strategy for generating cell content (space-separated words)
cell_content_st = st.lists(word_st, min_size=0, max_size=5).map(lambda words: ' '.join(words))

# Strategy for generating DataFrames
@st.composite
def dataframes_st(draw):
    num_rows = draw(st.integers(min_value=1, max_value=5))
    
    # Generate a fixed pool of potential column names to ensure uniqueness and control size
    # Max 3 columns as per original intent, so generate 3 unique names.
    all_col_names_pool = draw(st.sets(column_names_st, min_size=1, max_size=3))
    all_col_names = list(all_col_names_pool)
    
    # Now, draw the actual number of columns to use from the available pool
    num_cols_to_use = draw(st.integers(min_value=1, max_value=len(all_col_names)))
    
    # Select the actual column names to use
    selected_col_names = draw(st.sampled_from(all_col_names, k=num_cols_to_use))
    
    data = {}
    for col_name in selected_col_names:
        if draw(st.booleans()): # Mix of string and integer columns
            data[col_name] = draw(st.lists(cell_content_st, min_size=num_rows, max_size=num_rows))
        else:
            data[col_name] = draw(st.lists(st.integers(-100, 100), min_size=num_rows, max_size=num_rows))
            
    df = pd.DataFrame(data)
    
    # Ensure the target column exists and is a string type
    target_column = draw(st.sampled_from(selected_col_names))
    if not pd.api.types.is_string_dtype(df[target_column]):
        df[target_column] = df[target_column].astype(str) # Convert to string if not already
    
    return df, target_column

# Strategy for generating regex patterns
# Focus on simple word matching patterns for clarity and to avoid overly complex regex issues
# Include empty pattern as a specific edge case.
# Also include patterns that match parts of words or specific characters.
pattern_st = st.one_of(
    st.just(""), # Empty pattern
    st.text(st.sampled_from(list(string.ascii_lowercase + string.digits) + ['|', '\\b', '-', '_']), min_size=1, max_size=10).map(lambda s: r'\b(?:' + s + r')\b'),
    st.text(string.ascii_lowercase, min_size=1, max_size=5).map(lambda s: r'\b' + s + r'\b'), # Simple whole word patterns
    st.text(string.ascii_lowercase, min_size=1, max_size=3), # Patterns matching parts of words
    st.just(r'\d+'), # Pattern for digits
    st.just(r'\w+'), # Pattern for any word character
    st.just(r'\s*'), # Pattern for whitespace (should not match words)
)


@settings(max_examples=50, deadline=None)
@given(df_and_col=dataframes_st(), pattern=st.just(""))
def test_empty_pattern_returns_unaltered_copy(df_and_col, pattern):
    """
    SPEC BASIS: "returning a copy of the unaltered DataFrame if the pattern is empty."
    PROPERTY: The returned DataFrame is a new object, but its contents are identical to the original.
    STRATEGY: Generate various DataFrames and always use an empty pattern. This targets the explicit
              edge case of an empty pattern.
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
    STRATEGY: Generate DataFrames and patterns. Filter inputs to ensure no words in the target column match
              the pattern. This covers the boundary case where the pattern is present but irrelevant.
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
    # Use re.search to check for any match, not just full word match
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
    STRATEGY: Generate DataFrames and patterns. Filter inputs to ensure all words in the target column's cells
              match the pattern. This covers the boundary case where all words are affected.
    """
    df, column_name = df_and_col
    original_df_copy = df.copy(deep=True)
    
    expected_series = original_df_copy[column_name].copy()

    # Flag to ensure at least one cell has words that all match, otherwise assume False
    found_all_match_cell = False

    for idx, cell_value in enumerate(df[column_name]):
        if not isinstance(cell_value, str):
            cell_value = str(cell_value)

        words = cell_value.split()
        if not words: # Handle empty strings or cells with no words
            continue

        # Ensure all words in the current cell match the pattern
        if all(re.search(pattern, word) for word in words):
            # If all words match, the expected behavior is a full reversal of the words
            expected_series.iloc[idx] = ' '.join(words[::-1])
            found_all_match_cell = True
        else:
            # If not all words match, the cell should remain unchanged for this test's purpose
            # (as we are testing the "all words matching" scenario).
            # We could also filter out such cells, but for this test, we just don't reverse them.
            pass # The original value is already in expected_series

    if not found_all_match_cell:
        st.assume(False) # Discard if no cell had all words matching the pattern

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
    PROPERTY: Only words matching the pattern are reversed, while non-matching words retain their original positions
              relative to each other and to the groups of matching words.
    STRATEGY: Generate DataFrames and patterns. For each cell, identify matching and non-matching words. Construct
              the expected output by reversing only the matching words within their identified groups. This test
              specifically targets cases where there's a mix of matching and non-matching words, including single-word
              cells and empty cells.
    """
    df, column_name = df_and_col
    original_df_copy = df.copy(deep=True)
    
    expected_series = original_df_copy[column_name].copy()
    
    found_mixed_case = False

    for idx, cell_value in enumerate(df[column_name]):
        if not isinstance(cell_value, str):
            cell_value = str(cell_value)

        words = cell_value.split()
        if not words: # Handle empty strings or cells with no words
            continue

        # Collect indices of matching words
        matching_indices = [i for i, word in enumerate(words) if re.search(pattern, word)]
        
        # Filter to ensure this is a "mixed" case: some matches, but not all words match.
        # Also, ensure there's at least one match to make the test meaningful for reversal.
        if not matching_indices or len(matching_indices) == len(words):
            continue # Skip cells that are not mixed or have no matches

        found_mixed_case = True
        new_words_list = list(words)
        
        # Extract matching words in their original order
        extracted_matching_words = [words[i] for i in matching_indices]
        # Reverse them
        reversed_extracted_matching_words = extracted_matching_words[::-1]
        
        # Place the reversed words back into their original matching positions
        for i, original_idx in enumerate(matching_indices):
            new_words_list[original_idx] = reversed_extracted_matching_words[i]
        
        expected_series.iloc[idx] = ' '.join(new_words_list)

    if not found_mixed_case:
        st.assume(False) # Discard if no mixed-case cells were generated

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
def test_single_word_cells_and_empty_cells(df_and_col, pattern):
    """
    SPEC BASIS: "Reverse the order of words... where the words match... This function maintains the original order of non-matching words."
    PROPERTY: Single-word cells are unaffected if the word matches (reversing one word is itself). Empty cells remain empty.
              Cells with multiple words, where only one matches, should only reverse that one word (which is itself).
    STRATEGY: Generate DataFrames, then modify some cells to be empty or contain a single word.
              This targets boundary conditions for word counts within a cell.
    """
    df, column_name = df_and_col
    original_df_copy = df.copy(deep=True)
    
    expected_series = original_df_copy[column_name].copy()
    
    modified_any_cell = False

    for idx in range(len(df)):
        original_cell_value = df.loc[idx, column_name]
        if not isinstance(original_cell_value, str):
            original_cell_value = str(original_cell_value)

        words = original_cell_value.split()
        
        # Introduce specific edge cases:
        if idx % 3 == 0: # Empty cell
            expected_series.iloc[idx] = ''
            modified_any_cell = True
        elif idx % 3 == 1 and words: # Single word cell (take first word)
            word = words[0]
            expected_series.iloc[idx] = word
            modified_any_cell = True
            # If the single word matches, it should still be itself after "reversal"
            if re.search(pattern, word):
                pass # No change
            else:
                pass # No change
        else: # Normal processing for other cells
            new_words_list = list(words)
            matching_indices = [i for i, word in enumerate(words) if re.search(pattern, word)]
            
            if matching_indices:
                extracted_matching_words = [words[i] for i in matching_indices]
                reversed_extracted_matching_words = extracted_matching_words[::-1]
                for i, original_idx in enumerate(matching_indices):
                    new_words_list[original_idx] = reversed_extracted_matching_words[i]
                expected_series.iloc[idx] = ' '.join(new_words_list)
                modified_any_cell = True
            else:
                pass # No matches, cell remains as is

    if not modified_any_cell:
        st.assume(False) # Ensure we actually tested some edge cases

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