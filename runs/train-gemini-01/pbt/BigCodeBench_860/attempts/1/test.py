# SEARCH PLAN:
# 1. Boundary `n` values: Test `n=0`, `n=1`, and small `n` to catch off-by-one errors in string generation or matching.
# 2. Pattern edge cases: Include patterns that match nothing, match single characters, or match fixed-length sequences.
# 3. Seed reproducibility: Verify that identical inputs (including seed) yield identical outputs, as explicitly guaranteed.
# 4. Output invariants: Ensure all returned matches conform to the pattern and that their combined length respects the original string length.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import re
import string

# Strategy for 'n': length of the random string. Keep it small as per instructions.
# Include 0 and 1 as boundary conditions.
st_n = st.one_of(st.just(0), st.just(1), st.integers(min_value=2, max_value=12))

# Strategy for 'pattern': regex pattern.
# Include simple character matches, character classes, and quantifiers.
# Ensure patterns are valid regexes and can potentially match the generated character set.
st_pattern = st.one_of(
    st.just(r''), # Empty pattern, matches at every position
    st.just(r'.'), # Matches any single character
    st.just(r'\d'), # Matches a digit
    st.just(r'[A-Z]'), # Matches an uppercase letter
    st.just(r'[a-z]'), # Matches a lowercase letter
    st.just(r'[0-9]{2}'), # Matches two digits
    st.just(r'[A-Za-z]{3}'), # Matches three letters
    st.just(r'X'), # A character unlikely to be in the string (unless n is very large)
    st.text(
        alphabet=string.ascii_letters + string.digits + r'[]{}()*+?.\\',
        min_size=1, max_size=5
    ).map(re.escape).map(lambda s: s if s else r'.'), # Escaped random strings to ensure valid regex
    st.text(
        alphabet=string.ascii_letters + string.digits,
        min_size=1, max_size=5
    ).map(lambda s: s + r'+' if s else r'.+') # Simple patterns with '+' quantifier
)

# Strategy for 'seed': integer for reproducibility.
st_seed = st.integers(min_value=0, max_value=10000)

@settings(max_examples=50, deadline=None)
@given(n=st_n, pattern=st_pattern, seed=st_seed)
def test_reproducibility_with_seed(n, pattern, seed):
    """
    SPEC BASIS: "By providing a seed the results are reproducable."
    PROPERTY: Calling task_func with the same n, pattern, and seed multiple times yields identical results.
    STRATEGY: Use small n, various patterns, and a fixed seed. Call the function twice and assert equality.
              This catches any non-deterministic behavior or incorrect seed usage.
    """
    try:
        result1 = task_func(n, pattern, seed)
        result2 = task_func(n, pattern, seed)
    except Exception:
        result1 = None
        result2 = None

    assert result1 is not None, "task_func should not raise an exception for valid inputs."
    assert result1 == result2, "Results must be identical for the same seed, n, and pattern."

@settings(max_examples=50, deadline=None)
@given(n=st_n, pattern=st_pattern, seed=st_seed)
def test_matches_adhere_to_pattern(n, pattern, seed):
    """
    SPEC BASIS: "find all non-overlapping matches of the regex 'pattern'."
    PROPERTY: Each string in the returned list must itself match the provided regex pattern.
    STRATEGY: Generate various n and pattern values. For each match found, re-check if it
              fully matches the pattern using re.fullmatch. This ensures the returned strings
              are indeed valid matches for the pattern.
    """
    try:
        matches = task_func(n, pattern, seed)
    except Exception:
        matches = None

    assert matches is not None, "task_func should not raise an exception for valid inputs."
    assert isinstance(matches, list), "The function must return a list."

    for match_str in matches:
        # re.fullmatch ensures the entire string matches the pattern, not just a substring.
        # This is appropriate for verifying that each *found match* adheres to the pattern.
        assert re.fullmatch(pattern, match_str) is not None, \
            f"Returned match '{match_str}' does not fully match pattern '{pattern}'."

@settings(max_examples=50, deadline=None)
@given(n=st.just(0), pattern=st_pattern, seed=st_seed)
def test_empty_string_n_zero(n, pattern, seed):
    """
    SPEC BASIS: "Generate a random string of length 'n'". If n=0, the string is empty.
                "Returns: list: A list of all non-overlapping matches".
    PROPERTY: If n=0, the generated string is empty, and thus no matches can be found,
              so the result must be an empty list.
    STRATEGY: Explicitly test with n=0. This is a boundary condition where string generation
              and regex matching logic might have off-by-one errors.
    """
    try:
        matches = task_func(n, pattern, seed)
    except Exception:
        matches = None

    assert matches is not None, "task_func should not raise an exception for valid inputs."
    assert matches == [], f"For n=0, the result should be an empty list, but got {matches}."

@settings(max_examples=50, deadline=None)
@given(n=st_n, pattern=st_pattern, seed=st_seed)
def test_sum_of_match_lengths_less_than_or_equal_to_n(n, pattern, seed):
    """
    SPEC BASIS: "Generate a random string of length 'n'". "find all non-overlapping matches".
    PROPERTY: The sum of the lengths of all non-overlapping matches must be less than or equal to 'n'.
              This is a conservation law, as matches are non-overlapping and come from a string of length 'n'.
    STRATEGY: Generate various n and pattern values. Calculate the sum of lengths of returned matches
              and compare to n. This catches cases where matches might be duplicated, overlap incorrectly,
              or somehow exceed the bounds of the original string.
    """
    try:
        matches = task_func(n, pattern, seed)
    except Exception:
        matches = None

    assert matches is not None, "task_func should not raise an exception for valid inputs."
    assert isinstance(matches, list), "The function must return a list."

    total_match_length = sum(len(m) for m in matches)
    assert total_match_length <= n, \
        f"Sum of match lengths ({total_match_length}) exceeds original string length ({n})."