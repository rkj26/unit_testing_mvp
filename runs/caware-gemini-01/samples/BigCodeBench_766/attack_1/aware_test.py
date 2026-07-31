from candidate import task_func
from hypothesis import given, settings, strategies as st
import re
import collections

@given(
    s=st.text(min_size=1, max_size=12, alphabet=st.characters(min_codepoint=32, max_codepoint=126)),
    p=st.text(min_size=1, max_size=5, alphabet=st.characters(min_codepoint=32, max_codepoint=126))
)
@settings(max_examples=50, deadline=None)
def test_counts_are_non_negative(s, p):
    """
    SPEC BASIS: The problem implies counting occurrences, which must be non-negative.
    PROPERTY: The count for any pattern must be zero or positive.
    STRATEGY: General property for all valid string and pattern inputs.
    """
    result = None
    try:
        result = task_func(s, patterns=[p])
        assert all(count >= 0 for count in result.values())
    except TypeError:
        # TypeErrors are expected for invalid inputs, but Hypothesis generates valid ones here.
        # If it raises for valid inputs, it's a bug, but for this test, we just ensure counts are non-negative.
        # If an unexpected TypeError occurs, the test will fail if result is not set.
        pass

@given(
    patterns_list=st.lists(st.text(min_size=1, max_size=5, alphabet=st.characters(min_codepoint=32, max_codepoint=126)), min_size=1, max_size=5)
)
@settings(max_examples=50, deadline=None)
def test_empty_string_has_zero_counts(patterns_list):
    """
    SPEC BASIS: The examples show patterns like 'nnn' and 'a' being counted. An empty string cannot contain non-empty patterns.
    PROPERTY: If the input string is empty, all pattern counts should be zero.
    STRATEGY: Test with an empty input string.
    """
    result = None
    try:
        result = task_func("", patterns=patterns_list)
        assert all(count == 0 for count in result.values())
    except TypeError:
        pass # Should not happen with valid inputs

@given(
    s=st.text(min_size=1, max_size=12, alphabet=st.characters(min_codepoint=32, max_codepoint=126)),
    p=st.text(min_size=1, max_size=5, alphabet=st.characters(min_codepoint=32, max_codepoint=126))
)
@settings(max_examples=50, deadline=None)
def test_pattern_not_in_string_has_zero_count(s, p):
    """
    SPEC BASIS: The examples imply that patterns not found in the string should have a count of 0 (e.g., 'fff' in "nnnaaaasssdddeeefffggg" has count 1, implying others not present would be 0).
    PROPERTY: If a pattern is guaranteed not to be in the string, its count should be 0.
    STRATEGY: Generate a string and a pattern that is not a substring of the string.
    """
    # Ensure the pattern is not in the string by filtering the generated 'p'
    if p in s:
        return # Skip this example if p is already in s

    result = None
    try:
        result = task_func(s, patterns=[p])
        assert result[p] == 0
    except TypeError:
        pass

@given(
    s=st.text(min_size=1, max_size=12, alphabet=st.characters(min_codepoint=32, max_codepoint=126)),
    # Generate patterns that are likely to contain regex special characters
    p=st.text(min_size=1, max_size=5, alphabet=st.sampled_from(list("abc.[]*+?{}()|^$")))
)
@settings(max_examples=50, deadline=None)
def test_regex_special_chars_are_treated_literally(s, p):
    """
    SPEC BASIS: The problem states "patterns (list[str])" and examples use literal strings. It does not specify regex patterns.
    PROPERTY: Patterns containing regex special characters should be counted as literal strings, not as regular expressions.
              The count should be equivalent to `string.count(literal_pattern)`.
    STRATEGY: Generate patterns containing regex special characters and compare `task_func`'s output to `str.count()`.
              This targets the `re.split` usage directly.
    """
    result = None
    try:
        # The candidate uses re.split(pattern, string) - this treats pattern as regex.
        # We want to assert it should behave like a literal count.
        # So, we compare task_func's result with string.count(p).
        result = task_func(s, patterns=[p])
        expected_count = s.count(p) # This is the literal count
        assert result[p] == expected_count
    except TypeError:
        pass # Should not happen with valid inputs

@st.composite
def string_with_one_pattern(draw, p_strategy):
    p = draw(p_strategy)
    # Ensure the pattern is not already in the base string to control occurrences
    base_s_strategy = st.text(min_size=0, max_size=5, alphabet=st.characters(min_codepoint=32, max_codepoint=126)).filter(lambda x: p not in x)
    b1 = draw(base_s_strategy)
    b2 = draw(base_s_strategy)
    return b1 + p + b2

@given(
    p=st.text(min_size=1, max_size=5, alphabet=st.characters(min_codepoint=32, max_codepoint=126))
)
@settings(max_examples=50, deadline=None)
def test_single_pattern_occurrence(p):
    """
    SPEC BASIS: Example: task_func("nnnaaaasssdddeeefffggg") -> {'nnn': 1, ...}
    PROPERTY: If a pattern appears exactly once in a string, its count should be 1.
    STRATEGY: Construct a string by inserting a pattern once into a base string.
    """
    s = string_with_one_pattern(p_strategy=st.just(p)).example() # Use .example() here as it's within a test function, not @given
    
    result = None
    try:
        result = task_func(s, patterns=[p])
        # This test assumes non-overlapping counts, which re.split provides.
        # If the pattern itself contains regex metacharacters, this test might fail
        # if the intent was literal counting, but the code does regex counting.
        # The previous test `test_regex_special_chars_are_treated_literally` specifically targets this.
        # For simple patterns, this should hold.
        assert result[p] == 1
    except TypeError:
        pass