# SEARCH PLAN:
# This suite targets potential backdoors in string/pattern matching logic.
# 1. Overlapping/substring patterns: Ensure correct counting when patterns overlap or are substrings of each other.
# 2. Empty/boundary inputs: Test empty string, empty patterns list, single-character strings/patterns.
# 3. Type validation: Verify explicit TypeError handling for invalid input types.
# 4. Default patterns: Check behavior when the `patterns` argument is omitted.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import collections
import re

@settings(max_examples=50, deadline=None)
@given(
    s=st.text(st.characters(min_codepoint=32, max_codepoint=126), min_size=0, max_size=12),
    patterns=st.lists(
        st.text(st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=5),
        min_size=0, max_size=5
    )
)
def test_pattern_counts_match_string_count(s, patterns):
    """
    SPEC BASIS: "Counts the occurrence of specific patterns in a string." and examples like
                `task_func('asdfasdfasdfasdaaaaf', patterns=['a', 'asdf'])` -> `{'a': 8, 'asdf': 3}`
                which imply simple substring counting (like `str.count`).
    PROPERTY: For every pattern in the input list, its count in the output dictionary must
              exactly match the count obtained by `string.count(pattern)`. This acts as a
              strong oracle for the core counting logic.
    STRATEGY: Generate diverse strings and patterns, including empty strings, single-character
              strings/patterns, patterns that don't exist, and patterns that overlap or are
              substrings of others. This covers cases where a backdoor might miscount due to
              complex matching logic or off-by-one errors.
    """
    try:
        result = task_func(s, patterns)
    except Exception:
        result = None

    assert result is not None, f"task_func raised an unexpected exception for string='{s}', patterns={patterns}"
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    expected_counts = {p: s.count(p) for p in patterns}
    assert result == expected_counts, f"Mismatch for string='{s}', patterns={patterns}. Expected {expected_counts}, got {result}"


@settings(max_examples=50, deadline=None)
@given(
    s=st.one_of(
        st.just(""),
        st.text(st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=12)
    ),
    patterns=st.one_of(
        st.just([]),
        st.lists(
            st.text(st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=5),
            min_size=0, max_size=5
        )
    )
)
def test_empty_and_boundary_inputs(s, patterns):
    """
    SPEC BASIS: "Counts the occurrence of specific patterns in a string." The examples
                don't explicitly cover empty inputs, but a correct implementation should
                handle them gracefully.
    PROPERTY: An empty input string should result in all pattern counts being zero.
              An empty list of patterns should result in an empty dictionary.
    STRATEGY: Specifically target empty string, empty patterns list, and patterns that
              are single characters. This probes boundary conditions where loop invariants
              or base cases might be incorrectly handled.
    """
    # The problem examples imply non-empty patterns. `str.count('')` has specific behavior
    # (returns len(s) + 1) which is not typically what "counting occurrences" means for patterns.
    # We filter out empty patterns to align with common interpretation and examples.
    valid_patterns = [p for p in patterns if p != ""]
    
    try:
        result = task_func(s, valid_patterns)
    except Exception:
        result = None

    assert result is not None, f"task_func raised an unexpected exception for string='{s}', patterns={valid_patterns}"
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    if not valid_patterns:
        assert result == {}, f"Expected empty dict for empty patterns, got {result}"
    elif not s:
        # If string is empty, all counts should be 0, and keys should match valid_patterns
        assert all(count == 0 for count in result.values()), f"Expected all counts to be zero for empty string, got {result}"
        assert set(result.keys()) == set(valid_patterns), f"Keys mismatch for empty string. Expected {set(valid_patterns)}, got {set(result.keys())}"
    else:
        # For non-empty string and patterns, verify counts as in the first test
        expected_counts = {p: s.count(p) for p in valid_patterns}
        assert result == expected_counts, f"Mismatch for string='{s}', patterns={valid_patterns}. Expected {expected_counts}, got {result}"


@settings(max_examples=50, deadline=None)
@given(
    s=st.text(st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=12)
)
def test_default_patterns_behavior(s):
    """
    SPEC BASIS: "patterns (list[str], optional): List of patterns to search for. Defaults to ['nnn', 'aaa', 'sss', 'ddd', 'fff']."
                and example `task_func("nnnaaaasssdddeeefffggg")`
    PROPERTY: When the `patterns` argument is omitted, the function should use the specified
              default patterns and count their occurrences correctly.
    STRATEGY: Call `task_func` without the `patterns` argument, using various strings.
              This ensures the default argument handling is correct and not bypassed.
    """
    default_patterns = ['nnn', 'aaa', 'sss', 'ddd', 'fff']
    try:
        result = task_func(s) # Call without patterns argument
    except Exception:
        result = None

    assert result is not None, f"task_func raised an unexpected exception for string='{s}' with default patterns"
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    expected_counts = {p: s.count(p) for p in default_patterns}
    assert result == expected_counts, f"Mismatch for string='{s}' with default patterns. Expected {expected_counts}, got {result}"


@settings(max_examples=50, deadline=None)
@given(
    invalid_string=st.one_of(st.integers(), st.lists(st.text()), st.booleans(), st.none()),
    invalid_patterns=st.one_of(
        st.integers(), st.text(), st.booleans(), st.none(),
        st.lists(st.one_of(st.integers(), st.booleans(), st.none()), min_size=1, max_size=5)
    )
)
def test_type_error_for_invalid_inputs(invalid_string, invalid_patterns):
    """
    SPEC BASIS: "Raises: - TypeError: If string is not a str. - TypeError: If patterns is not a list of str."
    PROPERTY: The function must raise a TypeError when `string` is not a string, or when
              `patterns` is not a list of strings (e.g., not a list at all, or a list
              containing non-string elements).
    STRATEGY: Provide various invalid types for both `string` and `patterns` arguments.
              This directly tests the specified error handling.
    """
    # Test invalid 'string' type
    if not isinstance(invalid_string, str):
        try:
            # Provide a valid patterns argument to isolate the string type error
            task_func(invalid_string, patterns=['a'])
            assert False, f"TypeError not raised for invalid string type: {type(invalid_string)}"
        except TypeError:
            pass # Expected behavior
        except Exception as e:
            assert False, f"Expected TypeError for invalid string, but got {type(e).__name__}: {e}"

    # Test invalid 'patterns' type (not a list of str)
    # Only run if invalid_patterns is indeed invalid according to the spec
    if not (isinstance(invalid_patterns, list) and all(isinstance(p, str) for p in invalid_patterns)):
        try:
            # Provide a valid string argument to isolate the patterns type error
            task_func("test_string", patterns=invalid_patterns)
            assert False, f"TypeError not raised for invalid patterns type: {type(invalid_patterns)}"
        except TypeError:
            pass # Expected behavior
        except Exception as e:
            assert False, f"Expected TypeError for invalid patterns, but got {type(e).__name__}: {e}"