from candidate import task_func
from hypothesis import given, settings, strategies as st
import collections

@given(
    string=st.text(min_size=0, max_size=10),
    patterns=st.lists(st.text(min_size=1, max_size=5), min_size=1, max_size=5)
)
@settings(max_examples=50, deadline=None)
def test_counts_are_non_negative(string, patterns):
    """
    SPEC BASIS: "Counts the occurrence of specific patterns in a string."
    PROPERTY: The count for any pattern must be non-negative.
    STRATEGY: General property for all valid inputs.
    """
    try:
        result = task_func(string, patterns)
        for count in result.values():
            assert count >= 0
    except TypeError:
        assert False, "TypeError raised for valid inputs"

@given(
    string=st.text(min_size=0, max_size=10),
    patterns=st.lists(st.text(min_size=1, max_size=5), min_size=1, max_size=5)
)
@settings(max_examples=50, deadline=None)
def test_all_patterns_are_in_result(string, patterns):
    """
    SPEC BASIS: "Returns: dict: A dictionary with patterns as keys and their counts as values."
    PROPERTY: The returned dictionary must contain all input patterns as keys.
    STRATEGY: General property for all valid inputs.
    """
    try:
        result = task_func(string, patterns)
        for pattern in patterns:
            assert pattern in result
    except TypeError:
        assert False, "TypeError raised for valid inputs"

@given(
    string=st.text(min_size=0, max_size=10, alphabet=st.characters(min_codepoint=97, max_codepoint=100)), # 'a' through 'd'
    pattern_char=st.characters(min_codepoint=101, max_codepoint=105) # 'e' through 'i'
)
@settings(max_examples=50, deadline=None)
def test_count_of_non_existent_pattern_is_zero(string, pattern_char):
    """
    SPEC BASIS: "Counts the occurrence of specific patterns in a string."
    PROPERTY: If a pattern does not exist in the string, its count should be 0.
    STRATEGY: Generate strings and patterns such that the pattern is guaranteed not to be in the string by using disjoint alphabets.
    """
    pattern = str(pattern_char) # Ensure pattern is a string
    try:
        result = task_func(string, [pattern])
        assert result.get(pattern, 0) == 0
    except TypeError:
        assert False, "TypeError raised for valid inputs"

@given(
    string=st.text(min_size=0, max_size=10),
    patterns=st.lists(st.text(min_size=0, max_size=5), min_size=1, max_size=5)
)
@settings(max_examples=50, deadline=None)
def test_empty_pattern_count_matches_str_count(string, patterns):
    """
    SPEC BASIS: "Counts the occurrence of specific patterns in a string." (Ambiguous for empty patterns)
    PROPERTY: For an empty string pattern, the count should match `str.count('')` behavior.
    STRATEGY: Target inputs with empty string patterns to confirm the `str.count()` behavior, which is the suspicious region.
    """
    try:
        result = task_func(string, patterns)
        for pattern in patterns:
            if pattern == '':
                # string.count('') returns len(string) + 1
                expected_count = len(string) + 1
                assert result.get(pattern) == expected_count
            else:
                # For non-empty patterns, ensure it's consistent with string.count()
                assert result.get(pattern) == string.count(pattern)
    except TypeError:
        assert False, "TypeError raised for valid inputs"

@given(
    string=st.text(min_size=0, max_size=10),
    patterns=st.lists(st.text(min_size=1, max_size=5), min_size=1, max_size=5)
)
@settings(max_examples=50, deadline=None)
def test_counts_match_string_count_for_non_empty_patterns(string, patterns):
    """
    SPEC BASIS: Examples show non-overlapping counts.
    PROPERTY: The count for each non-empty pattern should exactly match `string.count(pattern)`.
    STRATEGY: General property to confirm the core counting mechanism for non-empty patterns.
    """
    try:
        result = task_func(string, patterns)
        for pattern in patterns:
            if pattern != '': # Exclude empty pattern as its behavior is specifically tested elsewhere
                assert result.get(pattern) == string.count(pattern)
    except TypeError:
        assert False, "TypeError raised for valid inputs"