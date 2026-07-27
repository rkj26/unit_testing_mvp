import json
import math
from decimal import Decimal, getcontext

from hypothesis import given, settings, strategies as st

from candidate import task_func


# Strategy for decimal_value: non-negative, reasonable range and precision
# Max value chosen to avoid excessively large numbers but cover a good range.
# Max places chosen to allow for varied input precision.
st_decimal_value = st.decimals(
    min_value=Decimal('0'),
    max_value=Decimal('1000000'),
    places=6,
    allow_nan=False,
    allow_infinity=False
)

# Strategy for precision: non-negative integer, reasonable range
# Max precision chosen to avoid excessively long strings but allow for varied rounding.
st_precision = st.integers(min_value=0, max_value=10)


@given(decimal_value=st_decimal_value, precision=st_precision)
@settings(max_examples=50, deadline=None)
def test_return_type_is_string(decimal_value, precision):
    """
    Verify that the function always returns a string.
    """
    result = task_func(decimal_value, precision)
    assert isinstance(result, str)


@given(decimal_value=st_decimal_value, precision=st_precision)
@settings(max_examples=50, deadline=None)
def test_return_value_is_valid_json_string(decimal_value, precision):
    """
    Verify that the returned string is a valid JSON string.
    """
    result = task_func(decimal_value, precision)
    try:
        json.loads(result)
    except json.JSONDecodeError:
        raise AssertionError(f"Returned string '{result}' is not valid JSON.")


@given(decimal_value=st_decimal_value, precision=st_precision)
@settings(max_examples=50, deadline=None)
def test_json_decoded_value_is_string(decimal_value, precision):
    """
    Verify that the JSON-decoded value is a string (as per example "1.97").
    """
    result = task_func(decimal_value, precision)
    decoded_value = json.loads(result)
    assert isinstance(decoded_value, str)


@given(decimal_value=st_decimal_value, precision=st_precision)
@settings(max_examples=50, deadline=None)
def test_decoded_value_is_valid_number_string(decimal_value, precision):
    """
    Verify that the JSON-decoded string can be converted to a float.
    """
    result = task_func(decimal_value, precision)
    decoded_str = json.loads(result)
    try:
        float(decoded_str)
    except ValueError:
        raise AssertionError(f"Decoded string '{decoded_str}' is not a valid number string.")


@given(decimal_value=st_decimal_value, precision=st_precision)
@settings(max_examples=50, deadline=None)
def test_square_root_value_is_correct(decimal_value, precision):
    """
    Verify that the numerical value of the result is the square root of the input.
    """
    result = task_func(decimal_value, precision)
    decoded_str = json.loads(result)
    actual_sqrt = Decimal(decoded_str)

    # Calculate expected square root using math.sqrt and then convert to Decimal
    # Use getcontext() to set precision for Decimal operations
    current_context = getcontext()
    original_prec = current_context.prec
    try:
        # Set a higher precision for intermediate calculations to avoid rounding errors
        current_context.prec = precision + 5 if precision is not None else 7
        expected_sqrt_float = math.sqrt(float(decimal_value))
        expected_sqrt_decimal = Decimal(str(expected_sqrt_float)) # Convert float to string then Decimal for precision control
        
        # Round the expected_sqrt_decimal to the specified precision
        # Use quantize for correct rounding behavior with Decimal
        if precision == 0:
            # For precision 0, round to the nearest integer.
            # Decimal('1').quantize(Decimal('1'), rounding='ROUND_HALF_UP')
            # For 0 decimal places, the quantize exponent is Decimal('1')
            expected_rounded = expected_sqrt_decimal.quantize(Decimal('1'), rounding='ROUND_HALF_UP')
        else:
            # For positive precision, quantize to 10^-precision
            quantizer = Decimal('10') ** -precision
            expected_rounded = expected_sqrt_decimal.quantize(quantizer, rounding='ROUND_HALF_UP')

        assert actual_sqrt == expected_rounded, \
            f"Input: {decimal_value}, Precision: {precision}\n" \
            f"Expected sqrt: {expected_sqrt_decimal}, Rounded: {expected_rounded}\n" \
            f"Actual result: {actual_sqrt}"
    finally:
        current_context.prec = original_prec


@given(decimal_value=st_decimal_value, precision=st_precision)
@settings(max_examples=50, deadline=None)
def test_precision_of_result_string(decimal_value, precision):
    """
    Verify that the number of decimal places in the decoded string matches the precision.
    This test handles cases where trailing zeros might be omitted by float conversion,
    but the problem implies a fixed number of decimal places in the string.
    Example: "1.97" for precision 2.
    """
    result = task_func(decimal_value, precision)
    decoded_str = json.loads(result)

    if '.' in decoded_str:
        actual_decimal_places = len(decoded_str.split('.')[1])
    else:
        actual_decimal_places = 0
    
    assert actual_decimal_places == precision, \
        f"Input: {decimal_value}, Precision: {precision}\n" \
        f"Decoded string: '{decoded_str}'\n" \
        f"Expected decimal places: {precision}, Actual: {actual_decimal_places}"


@given(decimal_value=st.just(Decimal('0')), precision=st_precision)
@settings(max_examples=50, deadline=None)
def test_zero_input(decimal_value, precision):
    """
    Test the specific case where decimal_value is 0.
    sqrt(0) is 0, and should be formatted to the given precision.
    """
    result = task_func(decimal_value, precision)
    decoded_str = json.loads(result)
    
    expected_str = f"0.{'0' * precision}" if precision > 0 else "0"
    assert decoded_str == expected_str, \
        f"Input: {decimal_value}, Precision: {precision}\n" \
        f"Expected: '{expected_str}', Actual: '{decoded_str}'"


@given(decimal_value=st.just(Decimal('1')), precision=st_precision)
@settings(max_examples=50, deadline=None)
def test_one_input(decimal_value, precision):
    """
    Test the specific case where decimal_value is 1.
    sqrt(1) is 1, and should be formatted to the given precision.
    """
    result = task_func(decimal_value, precision)
    decoded_str = json.loads(result)
    
    expected_str = f"1.{'0' * precision}" if precision > 0 else "1"
    assert decoded_str == expected_str, \
        f"Input: {decimal_value}, Precision: {precision}\n" \
        f"Expected: '{expected_str}', Actual: '{decoded_str}'"


@given(decimal_value=st.just(Decimal('4')), precision=st_precision)
@settings(max_examples=50, deadline=None)
def test_perfect_square_input(decimal_value, precision):
    """
    Test a perfect square input (e.g., 4).
    sqrt(4) is 2, and should be formatted to the given precision.
    """
    result = task_func(decimal_value, precision)
    decoded_str = json.loads(result)
    
    expected_str = f"2.{'0' * precision}" if precision > 0 else "2"
    assert decoded_str == expected_str, \
        f"Input: {decimal_value}, Precision: {precision}\n" \
        f"Expected: '{expected_str}', Actual: '{decoded_str}'"


@given(decimal_value=st.just(Decimal('3.9')), precision=st.just(2))
@settings(max_examples=50, deadline=None)
def test_example_case(decimal_value, precision):
    """
    Verify the example given in the problem description.
    """
    result = task_func(decimal_value, precision)
    assert result == '"1.97"'