# SEARCH PLAN:
# 1. Incomplete Input: Target inputs with fewer than 5 fields per line to ensure ValueError is raised as specified.
# 2. Product Name Consistency: Generate inputs with duplicate codes to verify that the same product name is assigned consistently per unique code for a given seed.
# 3. Data Type and Column Integrity: Verify that 'Quantity' and 'Price' columns are integers and all specified columns are present.
# 4. Whitespace Handling: Test inputs with leading/trailing whitespace in fields, especially the description, to ensure correct stripping and preservation.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import pandas as pd
import re

@settings(max_examples=50, deadline=None)
@given(s_parts=st.lists(st.lists(st.text(st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=10), min_size=1, max_size=4), min_size=1, max_size=12))
def test_incomplete_line_raises_value_error(s_parts):
    """
    SPEC BASIS: "If incomplete, this function raises ValueError."
    PROPERTY: An input string containing at least one line with fewer than 5 whitespace-separated parts must raise a ValueError.
    STRATEGY: Generate lists of parts for lines, ensuring at least one line has 1 to 4 parts. Join these parts and lines to form the input string.
    """
    s = "\n".join([" ".join(parts) for parts in s_parts])
    
    # Ensure at least one line is incomplete for the test to be meaningful
    has_incomplete_line = any(len(parts) < 5 for parts in s_parts)
    
    if not has_incomplete_line:
        # If Hypothesis somehow generates only complete lines, skip or adjust.
        # For this strategy, it's designed to always produce incomplete lines.
        # If it doesn't, it means the strategy needs adjustment or the test is not targeting the right region.
        # For now, we assume the strategy will produce incomplete lines.
        # If this assert fails, it means the strategy is not working as intended.
        assert False, "Hypothesis strategy failed to generate an incomplete line."

    try:
        task_func(s)
        assert False, "ValueError was not raised for incomplete input."
    except ValueError as e:
        assert isinstance(e, ValueError), f"Expected ValueError, but got {type(e).__name__}"
    except Exception as e:
        assert False, f"Expected ValueError, but caught unexpected exception: {type(e).__name__}: {e}"


@settings(max_examples=50, deadline=None)
@given(
    product_data=st.lists(
        st.tuples(
            st.text(st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=5), # ID
            st.integers(min_value=1, max_value=100), # Quantity
            st.text(st.characters(min_codepoint=65, max_codepoint=90), min_size=1, max_size=4), # Code
            st.integers(min_value=1, max_value=1000), # Price
            st.text(st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=20) # Description
        ),
        min_size=1, max_size=12
    ),
    seed=st.integers(min_value=0, max_value=1000)
)
def test_product_name_consistency_and_validity(product_data, seed):
    """
    SPEC BASIS: "Product name is randomly sampled from: ['Apple', 'Banana', 'Orange', 'Pear', 'Grape'].
                 The same product name will be assigned to each code for each input s, however different codes can be mapped to the same name."
    PROPERTY: For a given input string and seed, all rows with the same 'Code' must have the identical 'Product' name.
              Additionally, all assigned 'Product' names must be from the specified list.
    STRATEGY: Generate valid multi-line inputs, including potential duplicate codes. Check consistency of product names per code and against the allowed list.
    """
    s_lines = []
    for pid, qty, code, price, desc in product_data:
        s_lines.append(f"{pid} {qty} {code} {price} {desc}")
    s = "\n".join(s_lines)

    allowed_products = ['Apple', 'Banana', 'Orange', 'Pear', 'Grape']

    try:
        df = task_func(s, seed=seed)
    except Exception:
        df = None
    assert df is not None, "task_func raised an unexpected exception for valid input."

    # Check if all product names are from the allowed list
    assert df['Product'].isin(allowed_products).all(), "Product names are not from the allowed list."

    # Check consistency of product names per code
    code_to_product_map = {}
    for _, row in df.iterrows():
        code = row['Code']
        product = row['Product']
        if code not in code_to_product_map:
            code_to_product_map[code] = product
        else:
            assert code_to_product_map[code] == product, \
                f"Inconsistent product name for code '{code}': expected '{code_to_product_map[code]}', got '{product}'"


@settings(max_examples=50, deadline=None)
@given(
    product_data=st.lists(
        st.tuples(
            st.text(st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=5), # ID
            st.integers(min_value=1, max_value=100), # Quantity
            st.text(st.characters(min_codepoint=65, max_codepoint=90), min_size=1, max_size=4), # Code
            st.integers(min_value=1, max_value=1000), # Price
            st.text(st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=20) # Description
        ),
        min_size=1, max_size=12
    )
)
def test_data_types_and_column_integrity(product_data):
    """
    SPEC BASIS: "DataFrame with columns: ['ID', 'Quantity', 'Code', 'Price', 'Product', 'Description'].
                 Quantity and Price are expected to be integers."
    PROPERTY: The returned DataFrame must have the exact specified columns, and 'Quantity' and 'Price' columns must have integer data types.
    STRATEGY: Generate valid multi-line inputs. Check the DataFrame's columns and data types.
    """
    s_lines = []
    for pid, qty, code, price, desc in product_data:
        s_lines.append(f"{pid} {qty} {code} {price} {desc}")
    s = "\n".join(s_lines)

    expected_columns = ['ID', 'Quantity', 'Code', 'Price', 'Product', 'Description']

    try:
        df = task_func(s)
    except Exception:
        df = None
    assert df is not None, "task_func raised an unexpected exception for valid input."

    assert list(df.columns) == expected_columns, f"Expected columns {expected_columns}, but got {list(df.columns)}"
    assert pd.api.types.is_integer_dtype(df['Quantity']), "Quantity column is not of integer type."
    assert pd.api.types.is_integer_dtype(df['Price']), "Price column is not of integer type."
    # Other columns are expected to be object/string types, but the spec doesn't strictly enforce 'object' vs 'string' dtype.
    # We only assert on the explicitly specified integer types.


@settings(max_examples=50, deadline=None)
@given(
    product_data=st.lists(
        st.tuples(
            st.text(st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=5), # ID
            st.integers(min_value=1, max_value=100), # Quantity
            st.text(st.characters(min_codepoint=65, max_codepoint=90), min_size=1, max_size=4), # Code
            st.integers(min_value=1, max_value=1000), # Price
            st.text(st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=20) # Description
        ),
        min_size=1, max_size=12
    ),
    leading_trailing_ws=st.text(st.just(' '), min_size=0, max_size=3) # For adding leading/trailing whitespace
)
def test_whitespace_handling_and_description_preservation(product_data, leading_trailing_ws):
    """
    SPEC BASIS: "The function will remove trailing whitespaces in each field and assign a product name per unique code."
                "Expected format per segment: '<ID> <Quantity> <Code> <Price> <Description>'"
    PROPERTY: Leading/trailing whitespace around ID, Quantity, Code, Price fields should be stripped.
              Leading/trailing whitespace around the entire Description field should be stripped, but internal spaces within the description must be preserved.
    STRATEGY: Generate valid inputs with varying amounts of leading/trailing whitespace around each field and within the description.
    """
    s_lines = []
    expected_ids = []
    expected_quantities = []
    expected_codes = []
    expected_prices = []
    expected_descriptions = []

    for pid, qty, code, price, desc in product_data:
        # Add leading/trailing whitespace to each field
        ws_pid = f"{leading_trailing_ws}{pid}{leading_trailing_ws}"
        ws_qty = f"{leading_trailing_ws}{qty}{leading_trailing_ws}"
        ws_code = f"{leading_trailing_ws}{code}{leading_trailing_ws}"
        ws_price = f"{leading_trailing_ws}{price}{leading_trailing_ws}"
        ws_desc = f"{leading_trailing_ws}{desc}{leading_trailing_ws}" # Description itself might have internal spaces

        s_lines.append(f"{ws_pid} {ws_qty} {ws_code} {ws_price} {ws_desc}")

        expected_ids.append(pid)
        expected_quantities.append(qty)
        expected_codes.append(code)
        expected_prices.append(price)
        expected_descriptions.append(desc) # Description should be stripped of its *outer* whitespace

    s = "\n".join(s_lines)

    try:
        df = task_func(s)
    except Exception:
        df = None
    assert df is not None, "task_func raised an unexpected exception for valid input."

    assert list(df['ID']) == expected_ids, "ID field not stripped correctly or value mismatch."
    assert list(df['Quantity']) == expected_quantities, "Quantity field not stripped correctly or value mismatch."
    assert list(df['Code']) == expected_codes, "Code field not stripped correctly or value mismatch."
    assert list(df['Price']) == expected_prices, "Price field not stripped correctly or value mismatch."
    assert list(df['Description']) == expected_descriptions, "Description field not stripped correctly or internal spaces altered."