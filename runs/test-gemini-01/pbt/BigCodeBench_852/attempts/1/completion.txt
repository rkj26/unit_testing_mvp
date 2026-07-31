# SEARCH PLAN:
# 1. Boundary `max_length`: Test `max_length=1` and small values, ensuring string lengths are within bounds and characters are lowercase.
# 2. Reproducibility: Verify that identical inputs (including seed) produce identical outputs, catching divergences in random number generation.
# 3. Error Handling: Confirm `ValueError` is raised for `max_length < 1` as specified.
# 4. Output List Length: Assert the number of generated strings exactly matches `n_samples`, especially for small `n_samples`.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import string

@settings(max_examples=50, deadline=None)
@given(
    max_length=st.one_of(st.just(1), st.integers(min_value=1, max_value=12)),
    n_samples=st.one_of(st.just(1), st.integers(min_value=1, max_value=12)),
    seed=st.one_of(st.none(), st.integers(min_value=0, max_value=1000))
)
def test_string_properties_and_boundaries(max_length, n_samples, seed):
    """
    SPEC BASIS: "Each string's length varies from 1 to `max_length`." and "Each string is a random combination of lowercase letters".
    PROPERTY: Every string in the output list must have a length between 1 and `max_length` (inclusive), and all its characters must be lowercase ASCII letters.
    STRATEGY: Target `max_length` at its minimum (1) and small values, and `n_samples` at its minimum (1) and small values. This covers critical boundaries for string length and list size, where off-by-one errors or incorrect character sets might hide.
    """
    try:
        result = task_func(max_length, n_samples, seed)
    except Exception:
        result = None

    assert result is not None, f"task_func unexpectedly raised an exception for valid inputs: max_length={max_length}, n_samples={n_samples}, seed={seed}"
    assert isinstance(result, list), "Output must be a list."
    assert len(result) == n_samples, f"Output list length ({len(result)}) does not match n_samples ({n_samples})."

    for s in result:
        assert isinstance(s, str), "All elements in the list must be strings."
        assert 1 <= len(s) <= max_length, f"String length ({len(s)}) is not between 1 and max_length ({max_length}). String: '{s}'"
        assert all(c in string.ascii_lowercase for c in s), f"String '{s}' contains non-lowercase ASCII characters."

@settings(max_examples=50, deadline=None)
@given(
    max_length=st.integers(min_value=1, max_value=12),
    n_samples=st.integers(min_value=1, max_value=12),
    seed=st.integers(min_value=0, max_value=1000)
)
def test_reproducibility_with_seed(max_length, n_samples, seed):
    """
    SPEC BASIS: "An optional seed can be set for the random number generator for reproducible results."
    PROPERTY: Calling `task_func` twice with the same `max_length`, `n_samples`, and `seed` must produce identical results.
    STRATEGY: Use a fixed seed and call the function twice. This directly tests the reproducibility guarantee, catching any non-deterministic behavior when a seed is provided.
    """
    try:
        result1 = task_func(max_length, n_samples, seed)
        result2 = task_func(max_length, n_samples, seed)
    except Exception:
        result1 = None
        result2 = None

    assert result1 is not None and result2 is not None, f"task_func unexpectedly raised an exception for valid inputs: max_length={max_length}, n_samples={n_samples}, seed={seed}"
    assert result1 == result2, f"Results are not reproducible with seed={seed}. First call: {result1}, Second call: {result2}"

@settings(max_examples=50, deadline=None)
@given(
    max_length=st.integers(max_value=0), # max_length < 1
    n_samples=st.integers(min_value=1, max_value=12),
    seed=st.one_of(st.none(), st.integers(min_value=0, max_value=1000))
)
def test_raises_value_error_for_invalid_max_length(max_length, n_samples, seed):
    """
    SPEC BASIS: "Raises: ValueError: If max_length is smaller than 1."
    PROPERTY: `task_func` must raise a `ValueError` when `max_length` is 0 or negative.
    STRATEGY: Generate `max_length` values that are explicitly invalid (0, -1, small negative numbers). This directly tests the specified error handling for an invalid boundary condition.
    """
    try:
        task_func(max_length, n_samples, seed)
        assert False, f"ValueError was not raised for max_length={max_length}"
    except ValueError as e:
        # Assert that it's indeed a ValueError, as specified.
        assert isinstance(e, ValueError)
    except Exception as e:
        assert False, f"An unexpected exception ({type(e).__name__}) was raised instead of ValueError for max_length={max_length}"

@settings(max_examples=50, deadline=None)
@given(
    max_length=st.integers(min_value=1, max_value=12),
    n_samples=st.one_of(st.just(1), st.integers(min_value=1, max_value=12)),
    seed=st.one_of(st.none(), st.integers(min_value=0, max_value=1000))
)
def test_output_list_length(max_length, n_samples, seed):
    """
    SPEC BASIS: "n_samples (int): The number of strings to return."
    PROPERTY: The returned list must contain exactly `n_samples` strings.
    STRATEGY: Test with various `n_samples` values, including the boundary `n_samples=1` and other small numbers. This catches implementations that might return an incorrect number of samples, especially at edge cases for list generation.
    """
    try:
        result = task_func(max_length, n_samples, seed)
    except Exception:
        result = None

    assert result is not None, f"task_func unexpectedly raised an exception for valid inputs: max_length={max_length}, n_samples={n_samples}, seed={seed}"
    assert isinstance(result, list), "Output must be a list."
    assert len(result) == n_samples, f"Output list length ({len(result)}) does not match n_samples ({n_samples})."