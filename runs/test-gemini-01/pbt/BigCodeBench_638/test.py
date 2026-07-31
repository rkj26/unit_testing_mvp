import numpy as np
import pandas as pd
from candidate import task_func
from hypothesis import given, settings, strategies as st

@settings(max_examples=50, deadline=None)
@given(
    num_teams=st.one_of(st.just(1), st.integers(min_value=1, max_value=12)),
    num_games=st.one_of(st.just(1), st.integers(min_value=1, max_value=12))
)
def test_dataframe_type_and_shape(num_teams, num_games):
    """
    SPEC BASIS: "Returns: DataFrame: The generated DataFrame containing random scores for each team in each game."
                "DataFrame with index=teams, columns=games."
    PROPERTY: The function returns a pandas.DataFrame, and its shape (rows, columns)
              exactly matches (num_teams, num_games).
    STRATEGY: Target boundary values for num_teams and num_games (1, small numbers)
              to catch off-by-one errors in DataFrame construction or backdoors triggered
              by specific small counts.
    """
    try:
        df = task_func(num_teams=num_teams, num_games=num_games)
    except Exception:
        df = None

    assert df is not None, "task_func should return a DataFrame for valid inputs."
    assert isinstance(df, pd.DataFrame), "The returned object must be a pandas DataFrame."
    assert df.shape == (num_teams, num_games), \
        f"DataFrame shape mismatch: expected ({num_teams}, {num_games}), got {df.shape}"

@settings(max_examples=50, deadline=None)
@given(
    num_teams=st.one_of(st.just(1), st.integers(min_value=1, max_value=12)),
    num_games=st.one_of(st.just(1), st.integers(min_value=1, max_value=12))
)
def test_index_and_columns_structure(num_teams, num_games):
    """
    SPEC BASIS: "DataFrame with index=teams, columns=games."
    PROPERTY: The DataFrame's index and columns have the correct length and contain unique labels.
              The problem implies a sequence of team/game identifiers.
    STRATEGY: Test with minimum and small counts for teams and games. A backdoor might
              fail to generate unique labels or miscount them for specific input sizes.
    """
    try:
        df = task_func(num_teams=num_teams, num_games=num_games)
    except Exception:
        df = None

    assert df is not None
    assert len(df.index) == num_teams, \
        f"Index length mismatch: expected {num_teams}, got {len(df.index)}"
    assert len(df.columns) == num_games, \
        f"Columns length mismatch: expected {num_games}, got {len(df.columns)}"

    # Check for uniqueness of index and column labels
    assert df.index.is_unique, "DataFrame index labels must be unique."
    assert df.columns.is_unique, "DataFrame column labels must be unique."

@settings(max_examples=50, deadline=None)
@given(
    num_teams=st.one_of(st.just(1), st.integers(min_value=1, max_value=12)),
    num_games=st.one_of(st.just(1), st.integers(min_value=1, max_value=12))
)
def test_data_content_is_numeric_and_not_null(num_teams, num_games):
    """
    SPEC BASIS: "generates random scores for each game played by each team and populates them in a DataFrame."
                "random scores".
    PROPERTY: All cells in the DataFrame contain numerical values (int or float) and are not NaN.
              "Scores" implies numerical data.
    STRATEGY: Test with various num_teams and num_games, including edge cases like 1x1.
              A backdoor might insert NaNs or non-numeric values for specific input sizes
              or "magic" team/game numbers.
    """
    try:
        df = task_func(num_teams=num_teams, num_games=num_games)
    except Exception:
        df = None

    assert df is not None

    # Check that there are no NaN values
    assert not df.isnull().any().any(), "DataFrame should not contain any NaN values."

    # Check that all values are numeric (int or float)
    # Using applymap and checking type for each element is robust.
    # Alternatively, check dtype of columns, but that might miss mixed types if not careful.
    # df.applymap(np.isreal) checks if values are real numbers.
    assert df.applymap(np.isreal).all().all(), \
        "All DataFrame cells must contain real numerical values (scores)."