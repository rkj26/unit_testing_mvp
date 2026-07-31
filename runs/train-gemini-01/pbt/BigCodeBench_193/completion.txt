# SEARCH PLAN:
# 1. Boundary values for `rows` and `columns` (0, 1, small positive integers) to catch off-by-one errors in shape or column naming.
# 2. Invariant checks for DataFrame shape and type, as well as column naming convention.
# 3. Detailed content validation for individual cells, ensuring generated data adheres to type-specific rules (e.g., string length, integer ranges, collection sizes and element ranges).

from candidate import task_func
from hypothesis import given, settings, strategies as st
import pandas as pd
import string

# Constants from the problem description
DATA_TYPES = [str, int, float, list, tuple, dict, set]


@settings(max_examples=50, deadline=None)
@given(
    rows=st.one_of(st.just(0), st.just(1), st.integers(min_value=2, max_value=5)),
    columns=st.one_of(st.just(0), st.just(1), st.integers(min_value=2, max_value=5)),
)
def test_dataframe_shape_and_type(rows, columns):
    """
    SPEC BASIS: "Generates a DataFrame with a specified number of rows and columns",
                "Returns: pd.DataFrame: A DataFrame with the specified number of rows and columns".
    PROPERTY: The returned object is a pandas DataFrame and its shape matches the input (rows, columns).
    STRATEGY: Target boundary values for rows and columns (0, 1) and small positive integers
              to catch off-by-one errors in DataFrame construction or shape reporting.
    """
    try:
        df = task_func(rows, columns)
    except Exception:
        df = None

    assert df is not None, f"task_func({rows}, {columns}) raised an exception."
    assert isinstance(df, pd.DataFrame), f"Expected a pandas DataFrame, got {type(df)}"
    assert df.shape == (
        rows,
        columns,
    ), f"Expected shape ({rows}, {columns}), but got {df.shape}"


@settings(max_examples=50, deadline=None)
@given(
    rows=st.one_of(st.just(0), st.just(1), st.integers(min_value=2, max_value=5)),
    columns=st.one_of(st.just(0), st.just(1), st.integers(min_value=2, max_value=5)),
)
def test_column_naming_convention(rows, columns):
    """
    SPEC BASIS: "columns named 'col0', 'col1', etc."
    PROPERTY: The DataFrame's columns are named 'col0', 'col1', ..., 'col(columns-1)'.
    STRATEGY: Target boundary values for columns (0, 1) and small positive integers
              to catch errors in column naming logic, especially for empty or single-column cases.
    """
    try:
        df = task_func(rows, columns)
    except Exception:
        df = None

    assert df is not None, f"task_func({rows}, {columns}) raised an exception."

    expected_columns = [f"col{i}" for i in range(columns)]
    assert list(df.columns) == expected_columns, (
        f"Expected columns {expected_columns}, but got {list(df.columns)}"
    )


@settings(max_examples=50, deadline=None)
@given(
    rows=st.integers(min_value=1, max_value=3),  # At least one row to check content
    columns=st.integers(min_value=1, max_value=3),  # At least one column
)
def test_cell_content_adherence_to_type_rules(rows, columns):
    """
    SPEC BASIS: Detailed descriptions of content for each DATA_TYPE (str, int, float, list, tuple, dict, set).
    PROPERTY: For each cell, its Python type must be one of DATA_TYPES, and its content must adhere
              to the specified rules (e.g., string length 5, integers 0-9, collection sizes 1-5, elements 0-9).
    STRATEGY: Use small, non-zero rows and columns to ensure content generation logic for various types
              is exercised and validated without excessive runtime. This catches subtle errors in data generation.
    """
    try:
        df = task_func(rows, columns)
    except Exception:
        df = None

    assert df is not None, f"task_func({rows}, {columns}) raised an exception."

    for r in range(rows):
        for c in range(columns):
            cell_value = df.iloc[r, c]
            cell_type = type(cell_value)

            assert (
                cell_type in DATA_TYPES
            ), f"Cell at ({r}, {c}) has unexpected type {cell_type}. Value: {cell_value}"

            if cell_type is str:
                assert len(cell_value) == 5, (
                    f"String at ({r}, {c}) has length {len(cell_value)}, expected 5. Value: '{cell_value}'"
                )
                assert all(
                    char in string.ascii_lowercase for char in cell_value
                ), f"String at ({r}, {c}) contains non-lowercase alphabetic characters. Value: '{cell_value}'"
            elif cell_type is int:
                assert (
                    0 <= cell_value <= 9
                ), f"Integer at ({r}, {c}) is {cell_value}, expected 0-9."
            elif cell_type is float:
                # Floats are derived from integers 0-9, so they should be exact integers as floats
                assert (
                    0.0 <= cell_value <= 9.0 and cell_value == int(cell_value)
                ), f"Float at ({r}, {c}) is {cell_value}, expected 0.0-9.0 and integer value."
            elif cell_type in (list, tuple, set):
                assert (
                    1 <= len(cell_value) <= 5
                ), f"Collection at ({r}, {c}) has size {len(cell_value)}, expected 1-5. Value: {cell_value}"
                for item in cell_value:
                    assert isinstance(item, int), (
                        f"Item '{item}' in collection at ({r}, {c}) is not an int. Value: {cell_value}"
                    )
                    assert (
                        0 <= item <= 9
                    ), f"Item '{item}' in collection at ({r}, {c}) is not in 0-9. Value: {cell_value}"
            elif cell_type is dict:
                assert (
                    1 <= len(cell_value) <= 5
                ), f"Dictionary at ({r}, {c}) has size {len(cell_value)}, expected 1-5. Value: {cell_value}"
                for key, value in cell_value.items():
                    assert isinstance(key, int), (
                        f"Key '{key}' in dict at ({r}, {c}) is not an int. Value: {cell_value}"
                    )
                    assert (
                        0 <= key <= 9
                    ), f"Key '{key}' in dict at ({r}, {c}) is not in 0-9. Value: {cell_value}"
                    assert isinstance(value, int), (
                        f"Value '{value}' in dict at ({r}, {c}) is not an int. Value: {cell_value}"
                    )
                    assert (
                        0 <= value <= 9
                    ), f"Value '{value}' in dict at ({r}, {c}) is not in 0-9. Value: {cell_value}"