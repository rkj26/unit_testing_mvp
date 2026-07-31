# SEARCH PLAN:
# 1. Length boundaries: Test `length` at 0, 1, and small positive values to catch off-by-one errors in string generation.
# 2. Predicate evaluation: Verify that the characteristics dictionary accurately reflects the generated string's properties for various predicate combinations, including deduplication.
# 3. Error handling: Ensure `ValueError` is raised for negative length and `KeyError` for unrecognized predicates as specified.
# 4. Reproducibility: Confirm that identical inputs (including seed) yield identical outputs, as guaranteed by the seed parameter.
# 5. Empty predicates: Explicitly check that an empty predicate list results in an empty characteristics dictionary.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import string
import collections

# Define common strategies for reuse
_valid_predicates = ['has_uppercase', 'has_lowercase', 'has_special_chars', 'has_numbers']
# max_size must be an integer literal. len(_valid_predicates) is 4, so 4 + 2 = 6.
_predicate_strategy = st.lists(st.sampled_from(_valid_predicates), min_size=0, max_size=6)
_length_strategy = st.one_of(st.just(0), st.integers(min_value=1, max_value=12))
_seed_strategy = st.integers(min_value=0, max_value=10000) # Constrain seed for smaller range, but any int is fine

@settings(max_examples=50, deadline=None)
@given(length=_length_strategy, predicates=_predicate_strategy, seed=_seed_strategy)
def test_length_and_basic_structure(length, predicates, seed):
    """
    SPEC BASIS: "Generates a random string of specified length", "Returns: - string: the generated random text - dict: the text's characteristics", "If no predicates are provided, the result dictionary will be empty."
    PROPERTY: The generated string's length matches the input `length`. The return type is a tuple of (string, dict). If the input predicates list is empty, the characteristics dictionary is empty.
    STRATEGY: Target `length` boundaries (0, 1, small positive up to 12) and various predicate lists (including empty) to check basic return structure and length invariant.
    """
    try:
        result_string, result_dict = task_func(length, predicates, seed=seed)
    except Exception as e:
        # For valid inputs, any exception is a failure.
        assert False, f"task_func raised an unexpected exception for valid input: {e}"

    assert isinstance(result_string, str), "First element of result must be a string."
    assert isinstance(result_dict, dict), "Second element of result must be a dictionary."
    assert len(result_string) == length, f"Generated string length {len(result_string)} does not match requested length {length}."

    if not predicates:
        assert not result_dict, "Result dictionary should be empty when no predicates are provided."
    else:
        # If predicates are provided, the dict should not be empty unless all unique predicates are invalid,
        # but this test only uses valid predicates.
        assert result_dict is not None, "Result dictionary should not be None for non-empty predicates."


@settings(max_examples=50, deadline=None)
@given(length=_length_strategy.filter(lambda x: x > 0), predicates=_predicate_strategy, seed=_seed_strategy)
def test_predicate_evaluation_and_deduplication(length, predicates, seed):
    """
    SPEC BASIS: "predicates (list of strings): Conditions to evaluate the string.", "Returns: - dict: the text's characteristics", "Notes: - Predicates are deduplicated."
    PROPERTY: For each unique predicate in the input list, the corresponding key exists in the output dictionary, and its value (True/False) correctly reflects the presence or absence of the character type in the generated string. The keys in the output dictionary are exactly the unique input predicates.
    STRATEGY: Generate various `predicates` lists (including duplicates) and positive `length` values. Verify that the reported characteristics match the actual string content and that predicate deduplication is correctly applied to the output dictionary keys.
    """
    # Skip if predicates are empty, as this is covered by test_length_and_basic_structure
    if not predicates:
        return

    try:
        result_string, result_dict = task_func(length, predicates, seed=seed)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for valid input: {e}"

    unique_predicates = sorted(list(set(predicates)))
    assert sorted(list(result_dict.keys())) == unique_predicates, \
        f"Result dictionary keys {sorted(list(result_dict.keys()))} do not match unique input predicates {unique_predicates}."

    # Helper functions to check string characteristics
    def has_uppercase(s): return any(c.isupper() for c in s)
    def has_lowercase(s): return any(c.islower() for c in s)
    def has_numbers(s): return any(c.isdigit() for c in s)
    def has_special_chars(s): return any(c in string.punctuation for c in s)

    char_checkers = {
        'has_uppercase': has_uppercase,
        'has_lowercase': has_lowercase,
        'has_numbers': has_numbers,
        'has_special_chars': has_special_chars,
    }

    for pred in unique_predicates:
        assert pred in result_dict, f"Predicate '{pred}' missing from result dictionary."
        expected_value = char_checkers[pred](result_string)
        assert result_dict[pred] == expected_value, \
            f"Predicate '{pred}' evaluation incorrect. Expected {expected_value}, got {result_dict[pred]} for string '{result_string}'."


@settings(max_examples=50, deadline=None)
@given(length=st.integers(min_value=-10, max_value=-1), predicates=_predicate_strategy, seed=_seed_strategy)
def test_error_handling_negative_length(length, predicates, seed):
    """
    SPEC BASIS: "Raises: - ValueError: If the specified length is negative."
    PROPERTY: `task_func` raises a `ValueError` when `length` is negative.
    STRATEGY: Generate negative `length` values while keeping `predicates` valid. This targets the explicit error handling for invalid length.
    """
    try:
        task_func(length, predicates, seed=seed)
        assert False, "ValueError was expected but no exception was raised for negative length."
    except ValueError as e:
        assert "negative" in str(e).lower() or "length" in str(e).lower(), \
            f"ValueError message for negative length did not contain expected keywords: {e}"
    except Exception as e:
        assert False, f"Expected ValueError but got {type(e).__name__} for negative length: {e}"


@settings(max_examples=50, deadline=None)
@given(length=_length_strategy.filter(lambda x: x > 0),
       predicates=st.lists(st.one_of(st.sampled_from(_valid_predicates), st.just("invalid_predicate")),
                           min_size=1, max_size=5).filter(lambda x: "invalid_predicate" in x),
       seed=_seed_strategy)
def test_error_handling_unrecognized_predicate(length, predicates, seed):
    """
    SPEC BASIS: "Raises: - KeyError: If any predicate is not recognized."
    PROPERTY: `task_func` raises a `KeyError` when `predicates` contains an unrecognized string.
    STRATEGY: Generate `predicates` lists that include at least one unrecognized predicate (e.g., 'invalid_predicate'). This targets the explicit error handling for invalid predicates.
    """
    try:
        task_func(length, predicates, seed=seed)
        assert False, "KeyError was expected but no exception was raised for unrecognized predicate."
    except KeyError as e:
        assert "not recognized" in str(e).lower() or "invalid_predicate" in str(e).lower(), \
            f"KeyError message for unrecognized predicate did not contain expected keywords: {e}"
    except Exception as e:
        assert False, f"Expected KeyError but got {type(e).__name__} for unrecognized predicate: {e}"


@settings(max_examples=50, deadline=None)
@given(length=_length_strategy, predicates=_predicate_strategy, seed=_seed_strategy)
def test_reproducibility_with_seed(length, predicates, seed):
    """
    SPEC BASIS: "seed (int, optional): Seed for the random number generator for reproducibility."
    PROPERTY: Calling `task_func` twice with the same `length`, `predicates`, and `seed` produces identical results (string and characteristics dictionary).
    STRATEGY: Call `task_func` twice with identical inputs and assert that both the generated string and the characteristics dictionary are exactly equal. This catches implementations that don't correctly use the seed or have other sources of non-determinism.
    """
    try:
        result1_string, result1_dict = task_func(length, predicates, seed=seed)
        result2_string, result2_dict = task_func(length, predicates, seed=seed)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception during reproducibility test: {e}"

    assert result1_string == result2_string, \
        f"Strings are not identical for the same seed. First: '{result1_string}', Second: '{result2_string}'."
    assert result1_dict == result2_dict, \
        f"Characteristic dictionaries are not identical for the same seed. First: {result1_dict}, Second: {result2_dict}."