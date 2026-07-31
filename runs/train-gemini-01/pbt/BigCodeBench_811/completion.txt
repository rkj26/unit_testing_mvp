# SEARCH PLAN:
# 1. Position Finding Accuracy: Verify all occurrences of the `item` are correctly identified when no sampling is applied, covering item absence, single, and multiple occurrences, including boundary positions.
# 2. DataFrame Conversion Fidelity: Ensure the returned DataFrame accurately reflects the input dictionary's structure and content for both list-of-lists and dict-of-lists inputs.
# 3. Sampling Reproducibility: Test that providing a `random_seed` guarantees identical sampled positions across multiple calls for the same inputs, regardless of `sample_size`.
# 4. Sample Size Constraint: Assert that the number of returned positions when `sample_size` is specified is always `min(sample_size, actual_occurrences)`.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import pandas as pd
from collections import Counter

# Helper strategy for dictionary values (strings)
string_strategy = st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=('L', 'N')))

# Strategy for dictionary input: either list of lists or dict of lists
# Keep sizes small to manage complexity and generation time
dictionary_strategy = st.one_of(
    st.lists(st.lists(string_strategy, min_size=1, max_size=5), min_size=1, max_size=5),
    st.dictionaries(st.integers(min_value=0, max_value=4), st.lists(string_strategy, min_size=1, max_size=5), min_size=1, max_size=5)
)

# Strategy for the item to find, including items that might not be in the dictionary
item_strategy = st.one_of(
    string_strategy,
    st.just("MAGIC_ITEM_NOT_PRESENT") # A specific value to ensure absence is handled
)

@settings(max_examples=50, deadline=None)
@given(dictionary=dictionary_strategy, item=item_strategy)
def test_all_positions_found_without_sampling(dictionary, item):
    """
    SPEC BASIS: "Find the positions of a particular item in a the resulting DataFrame"
                "If None, all positions are returned."
    PROPERTY: When `sample_size` is None, the returned list of positions must contain
              all actual occurrences of the item in the DataFrame, and no others.
    STRATEGY: Generate various dictionary structures and items. Manually verify positions
              against the returned DataFrame to ensure completeness and correctness.
              Includes cases where the item is absent, present once, or multiple times.
    """
    try:
        positions, df = task_func(dictionary, item, sample_size=None, random_seed=None)
    except Exception:
        positions, df = None, None

    assert positions is not None and df is not None, "task_func should not raise an exception for valid inputs."

    expected_positions = []
    for r in range(df.shape[0]):
        for c in range(df.shape[1]):
            if df.iloc[r, c] == item:
                expected_positions.append((r, df.columns[c]))

    # Compare as multisets because the order of positions is not specified
    assert Counter(positions) == Counter(expected_positions), \
        f"Returned positions {positions} do not match expected {expected_positions} for item '{item}' in DataFrame:\n{df}"

@settings(max_examples=50, deadline=None)
@given(dictionary=dictionary_strategy, item=item_strategy)
def test_dataframe_conversion_fidelity(dictionary, item):
    """
    SPEC BASIS: "Converts a dictionary to a pandas DataFrame"
                "Returns: ... DataFrame: The converted dictionary."
    PROPERTY: The returned DataFrame must be an exact representation of the input dictionary.
    STRATEGY: Generate various dictionary structures (list of lists, dict of lists).
              Convert the input dictionary to a DataFrame independently and compare it
              with the DataFrame returned by `task_func`.
    """
    try:
        _, df_actual = task_func(dictionary, item, sample_size=None, random_seed=None)
    except Exception:
        df_actual = None

    assert df_actual is not None, "task_func should not raise an exception for valid inputs."

    # Manually convert the input dictionary to a DataFrame for comparison
    # This handles both list of lists and dict of lists correctly
    df_expected = pd.DataFrame(dictionary)

    pd.testing.assert_frame_equal(df_actual, df_expected,
                                  check_dtype=True, check_exact=True,
                                  err_msg=f"Returned DataFrame does not match expected for input:\n{dictionary}")

@settings(max_examples=50, deadline=None)
@given(dictionary=dictionary_strategy, item=item_strategy,
       sample_size=st.integers(min_value=0, max_value=10),
       random_seed=st.integers(min_value=0, max_value=100))
def test_sampling_reproducibility(dictionary, item, sample_size, random_seed):
    """
    SPEC BASIS: "Optionally, return a random sample of these positions, with an option to set a random seed for reproducibility."
    PROPERTY: When `random_seed` is provided, repeated calls with the same inputs
              (dictionary, item, sample_size, random_seed) must yield identical sampled positions.
    STRATEGY: Call `task_func` twice with the same `random_seed` and `sample_size`.
              The returned lists of positions must be exactly equal.
    """
    try:
        positions1, _ = task_func(dictionary, item, sample_size=sample_size, random_seed=random_seed)
        positions2, _ = task_func(dictionary, item, sample_size=sample_size, random_seed=random_seed)
    except Exception:
        positions1, positions2 = None, None

    assert positions1 is not None and positions2 is not None, "task_func should not raise an exception for valid inputs."
    assert positions1 == positions2, \
        f"Sampling not reproducible with seed {random_seed}. Call 1: {positions1}, Call 2: {positions2}"

@settings(max_examples=50, deadline=None)
@given(dictionary=dictionary_strategy, item=item_strategy,
       sample_size=st.integers(min_value=0, max_value=10))
def test_sample_size_constraint(dictionary, item, sample_size):
    """
    SPEC BASIS: "sample_size (int, optional): The number of positions to randomly sample."
    PROPERTY: The length of the returned positions list must be `min(sample_size, total_occurrences)`.
              If `sample_size` is greater than total occurrences, all occurrences should be returned.
    STRATEGY: Generate various `sample_size` values (0, 1, small, large, larger than actual occurrences).
              First, determine the total occurrences without sampling, then assert the sample size.
    """
    try:
        all_positions, _ = task_func(dictionary, item, sample_size=None, random_seed=None)
        sampled_positions, _ = task_func(dictionary, item, sample_size=sample_size, random_seed=42) # Use a fixed seed for consistency
    except Exception:
        all_positions, sampled_positions = None, None

    assert all_positions is not None and sampled_positions is not None, "task_func should not raise an exception for valid inputs."

    total_occurrences = len(all_positions)
    expected_sample_length = min(sample_size, total_occurrences)

    assert len(sampled_positions) == expected_sample_length, \
        f"Expected sample length {expected_sample_length} but got {len(sampled_positions)} for sample_size={sample_size} and total_occurrences={total_occurrences}"