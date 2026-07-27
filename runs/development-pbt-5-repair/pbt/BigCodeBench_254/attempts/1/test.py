import json
import math
from decimal import Decimal, getcontext

import pytest
from hypothesis import given, settings, strategies as st

# Import the function under test
from candidate import task_func

# Set a higher precision for Decimal operations within tests to avoid
# issues with intermediate calculations, especially for square roots.
# The task_func itself should handle its own precision for the final output.
getcontext().prec = 50

@given(
    decimal_value=st.just(Decimal('3.9')),
    precision=st.just(2)
)
@settings(max_examples=50, deadline=None)
def test_example_case(decimal_value, precision):
    """
    SPEC BASIS: "Example: ... decimal_value = Decimal('3.9') ... print(json_str) "1.97""
    PROPERTY: The function produces the exact output specified in the example.
    """
    result = task_func(decimal_value, precision)
    assert result == '"1.97"'

@given(
    decimal_value=st.decimals(min_value=Decimal('0'), max_value=Decimal('1000'), places=4),
    precision=st.integers(min_value=0, max_value=10)
)
@settings(max_examples=50, deadline=None)
def test_output_is_valid_json_string_and_number(decimal_value, precision):
    """
    SPEC BASIS: "Returns: str: The square root of the decimal value encoded as a JSON string."
    PROPERTY: The function returns a string that is valid JSON, and the parsed JSON value is a number.
    """
    result = task_func(decimal_value, precision)

    assert isinstance(result, str)

    try:
        parsed_value = json.loads(result)
    except json.JSONDecodeError:
        pytest.fail(f"Result '{result}' is not valid JSON.")

    assert isinstance(parsed_value, (int, float)), f"Parsed JSON value '{parsed_value}' is not a number."

@given(
    decimal_value=st.decimals(min_value=Decimal('0.0001'), max_value=Decimal('1000'), places=4), # Avoid 0 for relative error check
    precision=st.integers(min_value=0, max_value=10)
)
@settings(max_examples=50, deadline=None)
def test_square_root_and_precision_correctness(decimal_value, precision):
    """
    SPEC BASIS: "Calculate the square root of the given decimal value to a certain precision"
                "precision (int, Optional): The number of decimal places to round the square root to."
    PROPERTY: The parsed JSON value is the square root of the input, rounded to the specified precision.
    """
    result_str = task_func(decimal_value, precision)
    parsed_value = json.loads(result_str)

    # Check if the number of decimal places matches precision
    # Convert to Decimal for precise comparison
    parsed_decimal = Decimal(str(parsed_value))
    
    # Calculate expected square root using math.sqrt and then round it
    # Use Decimal for intermediate calculations to maintain precision
    expected_sqrt_decimal = Decimal(math.sqrt(float(decimal_value)))
    
    # Round the expected value to the specified precision
    # Use a rounding context for Decimal
    if precision == 0:
        # For precision 0, round to an integer
        rounded_expected = expected_sqrt_decimal.quantize(Decimal('1'), rounding='ROUND_HALF_UP')
    else:
        # For positive precision, round to the specified number of decimal places
        quantizer = Decimal('10') ** -precision
        rounded_expected = expected_sqrt_decimal.quantize(quantizer, rounding='ROUND_HALF_UP')

    # Allow a small tolerance for floating point conversion issues, especially when comparing
    # the result of math.sqrt (float) with Decimal.
    # The primary check is that the string representation matches the expected rounding.
    # The problem implies the rounding is done *before* JSON encoding.
    
    # Check the string representation directly for precision
    if precision == 0:
        assert '.' not in str(parsed_value), f"Expected no decimal places for precision 0, got '{parsed_value}'"
    else:
        # Check if the string representation has the correct number of decimal places
        # This is a strong check for the "to a certain precision" requirement.
        if '.' in str(parsed_value):
            actual_decimal_places = len(str(parsed_value).split('.')[1])
            assert actual_decimal_places == precision, \
                f"Expected {precision} decimal places, got {actual_decimal_places} for '{parsed_value}' (input: {decimal_value})"
        else:
            # If precision > 0 but no decimal point, it implies 0 decimal places, which is wrong.
            assert precision == 0, f"Expected {precision} decimal places, but no decimal point found for '{parsed_value}'"

    # Check the numerical value for correctness (within a small tolerance)
    # The parsed_value squared should be close to the original decimal_value
    # Use Decimal for this comparison to avoid float inaccuracies.
    # The tolerance should account for the rounding itself.
    # The value should be close to the *rounded* expected value.
    assert parsed_decimal == rounded_expected, \
        f"Input: {decimal_value}, Precision: {precision}\n" \
        f"Parsed: {parsed_decimal}, Expected rounded: {rounded_expected}"

@given(
    precision=st.integers(min_value=0, max_value=10)
)
@settings(max_examples=50, deadline=None)
def test_zero_input_value(precision):
    """
    SPEC BASIS: Implicit behavior for square root of 0.
    PROPERTY: The square root of 0 is 0, regardless of precision.
              The output should be "0" or "0.00" etc. based on precision.
    """
    decimal_value = Decimal('0')
    result_str = task_func(decimal_value, precision)
    parsed_value = json.loads(result_str)

    # The square root of 0 is 0.
    assert parsed_value == 0

    # Check the string representation for precision
    if precision == 0:
        assert result_str == '"0"', f"Expected '\"0\"' for precision 0, got '{result_str}'"
    else:
        expected_str_value = "0." + "0" * precision
        assert result_str == f'"{expected_str_value}"', \
            f"Expected '\"{expected_str_value}\"' for precision {precision}, got '{result_str}'"