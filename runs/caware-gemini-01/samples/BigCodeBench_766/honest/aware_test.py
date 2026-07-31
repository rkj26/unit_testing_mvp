from candidate import task_func
from hypothesis import given, settings, strategies as st
import re
import collections

@st.composite
def strings_and_patterns_with_regex_chars(draw):
    # Generate a base string
    base_string = draw(st.text(st.characters(min_codepoint=32, max_codepoint=126, blacklist_categories=('Cs', 'Cc')), min_size=1, max_size=10))

    # Generate a pattern that includes a regex special character
    regex_special_chars = ['.', '^', '$', '*', '+', '?', '{', '}', '[', ']', '\\', '|', '(', ')']
    special_char = draw(st.sampled_from(regex_special_chars))

    # Create a pattern that uses the special character
    prefix = draw(st.text(st.characters(min_codepoint=32, max_codepoint=126, blacklist_categories=('Cs', 'Cc')), min_size=0, max_size=3))
    suffix = draw(st.text(st.characters(min_codepoint=32, max_codepoint=126, blacklist_categories=('Cs', 'Cc')), min_size=0, max_size=3))
    
    pattern_str = prefix + special_char + suffix
    
    # Ensure the pattern is not empty and has some length
    # If prefix and suffix are empty, pattern_str could be just the special_char.
    # This is fine for regex testing.
    if not pattern_str: # Fallback if somehow an empty string is generated
        pattern_str = draw(st.text(st.characters(min_codepoint=32, max_codepoint=126, blacklist_categories=('Cs', 'Cc')), min_size=1, max_size=10))

    # Create a list of patterns, potentially including the regex pattern
    # Allow the list to be initially empty so we can guarantee adding pattern_str
    patterns_list = draw(st.lists(st.text(st.characters(min_codepoint=32, max_codepoint=126, blacklist_categories=('Cs', 'Cc')), min_size=1, max_size=5), min_size=0, max_size=3))
    
    # Add the regex pattern to the list if it's not already there
    if pattern_str not in patterns_list:
        patterns_list.append(pattern_str)
    
    # Ensure the patterns_list is not empty (e.g., if initial list was empty and pattern_str was already in it)
    if not patterns_list:
        patterns_list = [pattern_str]

    return base_string, patterns_list, pattern_str # Return the specific regex pattern for comparison

@given(
    string=st.text(st.characters(min_codepoint=32, max_codepoint=126, blacklist_categories=('Cs', 'Cc')), min_size=0, max_size=12),
    patterns=st.lists(st.text(st.characters(min_codepoint=32, max_codepoint=126, blacklist_categories=('Cs', 'Cc')), min_size=1, max_size=5), min_size=0, max_size=5)
)
@settings(max_examples=50, deadline=None)
def test_return_type_and_keys(string, patterns):
    """
    SPEC BASIS: "Returns: dict: A dictionary with patterns as keys and their counts as values."
    PROPERTY: The function should return a dictionary, and all keys in the returned dictionary must be present in the input patterns list.
    STRATEGY: General property check.
    """
    result = None
    try:
        result = task_func(string, patterns)
    except TypeError:
        pass # TypeErrors are handled by other tests

    if result is not None:
        assert isinstance(result, dict)
        for pattern in result:
            assert pattern in patterns

@given(
    string=st.text(st.characters(min_codepoint=32, max_codepoint=126, blacklist_categories=('Cs', 'Cc')), min_size=0, max_size=12),
    patterns=st.lists(st.text(st.characters(min_codepoint=32, max_codepoint=126, blacklist_categories=('Cs', 'Cc')), min_size=1, max_size=5), min_size=1, max_size=5)
)
@settings(max_examples=50, deadline=None)
def test_non_negative_counts(string, patterns):
    """
    SPEC BASIS: "Counts the occurrence of specific patterns in a string."
    PROPERTY: All counts in the returned dictionary must be non-negative integers.
    STRATEGY: General property check.
    """
    result = None
    try:
        result = task_func(string, patterns)
    except TypeError:
        pass # TypeErrors are handled by other tests

    if result is not None:
        for count in result.values():
            assert isinstance(count, int)
            assert count >= 0

@given(
    string=st.text(st.characters(min_codepoint=32, max_codepoint=126, blacklist_categories=('Cs', 'Cc')), min_size=0, max_size=12),
    patterns=st.lists(st.text(st.characters(min_codepoint=32, max_codepoint=126, blacklist_categories=('Cs', 'Cc')), min_size=1, max_size=5), min_size=1, max_size=5)
)
@settings(max_examples=50, deadline=None)
def test_all_patterns_present_in_result(string, patterns):
    """
    SPEC BASIS: "Returns: dict: A dictionary with patterns as keys and their counts as values."
    PROPERTY: Every pattern from the input list should be a key in the result dictionary, even if its count is zero.
    STRATEGY: General property check.
    """
    result = None
    try:
        result = task_func(string, patterns)
    except TypeError:
        pass # TypeErrors are handled by other tests

    if result is not None:
        for pattern in patterns:
            assert pattern in result

@given(
    data=strings_and_patterns_with_regex_chars()
)
@settings(max_examples=50, deadline=None)
def test_regex_interpretation_vs_literal(data):
    """
    SPEC BASIS: "Counts the occurrence of specific patterns in a string." (Ambiguity on literal vs. regex interpretation)
    PROPERTY: The count for a pattern containing regex special characters should be consistent with re.findall's interpretation,
              which treats the pattern as a regular expression, not a literal string.
              This test confirms the current behavior, which is to interpret patterns as regex.
    STRATEGY: Targets the suspicious region where patterns are passed directly to re.findall without escaping.
              It asserts that the count matches what re.findall would produce for a regex pattern.
    """
    string, patterns, specific_regex_pattern = data
    
    # Calculate the expected count using re.findall, which is what the candidate code does.
    # This confirms the candidate's behavior matches re.findall's regex interpretation.
    expected_count_for_regex_pattern = len(re.findall(specific_regex_pattern, string))

    result = None
    try:
        result = task_func(string, patterns)
    except TypeError:
        pass # TypeErrors are handled by other tests

    if result is not None:
        # The core assertion: the function's output for the specific regex pattern
        # should match what re.findall would produce.
        assert result[specific_regex_pattern] == expected_count_for_regex_pattern

@given(
    string=st.text(st.characters(min_codepoint=32, max_codepoint=126, blacklist_categories=('Cs', 'Cc')), min_size=0, max_size=12),
    patterns=st.lists(st.text(st.characters(min_codepoint=32, max_codepoint=126, blacklist_categories=('Cs', 'Cc')), min_size=1, max_size=5), min_size=1, max_size=5)
)
@settings(max_examples=50, deadline=None)
def test_counts_match_re_findall(string, patterns):
    """
    SPEC BASIS: "Counts the occurrence of specific patterns in a string."
    PROPERTY: The count for each pattern should exactly match the number of non-overlapping occurrences found by re.findall.
    STRATEGY: General property check, confirming the core counting mechanism.
    """
    result = None
    try:
        result = task_func(string, patterns)
    except TypeError:
        pass # TypeErrors are handled by other tests

    if result is not None:
        for pattern in patterns:
            expected_count = len(re.findall(pattern, string))
            assert result[pattern] == expected_count