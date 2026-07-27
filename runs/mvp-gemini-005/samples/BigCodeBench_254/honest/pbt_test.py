from candidate import task_func
from hypothesis import given, settings, strategies as st
import json
import math
from decimal import Decimal, getcontext

# Strategy for Decimal values suitable for square root (non-negative)
# We'll use floats for math.sqrt, so we need to ensure the Decimal can be converted without issues.
# Limiting magnitude to avoid overflow/underflow issues with float conversion and sqrt.
# Also, ensuring non-negative for sqrt.
st_decimal_value = st.decimals(
    min_value=Decimal('0'),
    max_value=Decimal('1e100'),  # Large enough but not excessively large for float conversion
    allow_nan=False,
    allow_infinity=False,
    places=st.integers(min_value=0, max_value=10) # Limit places for reasonable precision
).map(lambda d: d.normalize()) # Normalize to remove trailing zeros if not significant

# Strategy for precision (integer)
# Precision should be non-negative. A reasonable upper bound to avoid excessively long strings.
st_precision = st.integers(min_value=0, max_value=15)

# Helper to parse the JSON string and convert to Decimal for comparison
def parse_and_convert_to_decimal(json_str):
    try:
        parsed_value = json.loads(json_str)
        return Decimal(str(parsed_value))
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        raise AssertionError(f"Failed to parse or convert JSON string '{json_str}': {e}")

# Test 1: Basic property - result is a valid JSON string representing a number
@settings(max_examples=50, deadline=None)
@given(decimal_value=st_decimal_value, precision=st_precision)
def test_result_is_valid_json_number(decimal_value, precision):
    try:
        result = task_func(decimal_value, precision)
        assert isinstance(result, str), f"Expected string, got {type(result)}"
        parsed_value = json.loads(result)
        assert isinstance(parsed_value, (int, float)), f"JSON content is not a number: {parsed_value}"
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for input ({decimal_value}, {precision}): {e}"

# Test 2: Invariant - square of the result is approximately the input value
# This checks the core square root calculation and rounding.
@settings(max_examples=50, deadline=None)
@given(decimal_value=st_decimal_value, precision=st_precision)
def test_square_of_result_approximates_input(decimal_value, precision):
    if decimal_value == Decimal('0'):
        # Special case for 0, sqrt(0) is 0.
        # The rounding might make it '0.00' etc.
        try:
            result_str = task_func(decimal_value, precision)
            parsed_val = parse_and_convert_to_decimal(result_str)
            assert parsed_val == Decimal('0'), f"For input 0, expected 0, got {parsed_val}"
        except Exception as e:
            assert False, f"task_func raised an unexpected exception for input ({decimal_value}, {precision}): {e}"
        return

    try:
        result_str = task_func(decimal_value, precision)
        parsed_val = parse_and_convert_to_decimal(result_str)

        # Use Decimal context for precise comparison
        with getcontext() as ctx:
            ctx.prec = precision + 5 # Set precision higher for intermediate calculations
            squared_val = parsed_val * parsed_val

            # Calculate expected square root using math.sqrt and then round
            # Convert Decimal to float for math.sqrt, then back to Decimal for comparison
            expected_sqrt_float = math.sqrt(float(decimal_value))
            
            # Round the expected float result to the specified precision
            # This is tricky because float rounding is not exact.
            # We'll compare the squared result to the original input within a tolerance.
            # The tolerance should account for the rounding done by task_func.
            # The maximum error introduced by rounding to 'precision' places is 0.5 * 10^-precision.
            # When squared, this error propagates.
            # A simpler approach is to check if the original value is between (result - epsilon)^2 and (result + epsilon)^2
            # Or, compare the squared result to the original input within a tolerance related to the precision.
            
            # Let's use a relative tolerance for non-zero values, and absolute for values near zero.
            # The rounding error is 0.5 * 10^-precision.
            # If x is the true sqrt, and x_rounded is the rounded result, then |x - x_rounded| <= 0.5 * 10^-precision.
            # We want to check if x_rounded^2 is close to decimal_value.
            # x_rounded^2 = (x +/- delta)^2 = x^2 +/- 2x*delta + delta^2
            # So, |x_rounded^2 - x^2| approx 2x*delta.
            # Here x^2 is decimal_value.
            
            # A simpler check: the true sqrt should be close to the parsed_val.
            # Convert both to float for comparison with a small epsilon.
            # This is less precise but often sufficient for property testing.
            # The problem implies float arithmetic for sqrt, then rounding.
            
            # Let's calculate the expected rounded value using Decimal for better control.
            # Convert float result to Decimal, then round.
            expected_sqrt_decimal = Decimal(str(expected_sqrt_float))
            
            # Rounding strategy: round half up (common for 'round' in many contexts)
            # Python's round() rounds to nearest, with ties going to the even integer.
            # We need to match task_func's internal rounding.
            # For now, let's assume standard rounding and check if the squared value is close.
            
            # The tolerance should be related to the precision.
            # The value `parsed_val` is rounded to `precision` decimal places.
            # The maximum error in `parsed_val` compared to the true square root is `0.5 * 10**(-precision)`.
            # So, `abs(parsed_val - true_sqrt) <= 0.5 * 10**(-precision)`.
            # Squaring this, `abs(parsed_val**2 - true_sqrt**2)` should be approximately `2 * true_sqrt * (0.5 * 10**(-precision))`.
            # `true_sqrt**2` is `decimal_value`.
            
            # Let's use a relative tolerance for the squared value.
            # For very small numbers, absolute tolerance is better.
            tolerance = Decimal('1e-') + Decimal(str(precision + 2)) # A bit more than the precision
            
            # Check if the squared value is close to the original decimal_value
            # This is a robust check for the overall calculation.
            if decimal_value > Decimal('1e-10'): # Use relative tolerance for larger numbers
                assert abs(squared_val - decimal_value) / decimal_value < tolerance, \
                    f"Squared result {squared_val} not close to input {decimal_value} (relative error too high) for ({decimal_value}, {precision}). Parsed: {parsed_val}"
            else: # Use absolute tolerance for numbers close to zero
                assert abs(squared_val - decimal_value) < Decimal('1e-') + Decimal(str(precision + 5)), \
                    f"Squared result {squared_val} not close to input {decimal_value} (absolute error too high) for ({decimal_value}, {precision}). Parsed: {parsed_val}"

    except Exception as e:
        assert False, f"task_func raised an unexpected exception for input ({decimal_value}, {precision}): {e}"

# Test 3: Metamorphic relation - increasing precision should yield a more precise result
# This is hard to test directly because rounding can make results look the same.
# Instead, let's test that the result with higher precision, when rounded to lower precision, matches the lower precision result.
@settings(max_examples=50, deadline=None)
@given(
    decimal_value=st_decimal_value,
    precision_low=st_precision,
    precision_high=st_precision.map(lambda p: p + 1) # Ensure high is at least low + 1
)
def test_higher_precision_rounds_to_lower_precision(decimal_value, precision_low, precision_high):
    if precision_high <= precision_low: # Ensure high is strictly greater
        precision_high = precision_low + 1
    
    try:
        result_low_str = task_func(decimal_value, precision_low)
        result_high_str = task_func(decimal_value, precision_high)

        parsed_low = parse_and_convert_to_decimal(result_low_str)
        parsed_high = parse_and_convert_to_decimal(result_high_str)

        # Round the higher precision result to the lower precision
        # Use Decimal's quantize for controlled rounding
        # Rounding to nearest, ties to even (ROUND_HALF_EVEN) is Python's default for round()
        # If task_func uses a different rounding, this test might fail.
        # Let's assume standard rounding (ROUND_HALF_EVEN or similar).
        # The example "1.97" for 3.9 suggests standard rounding.
        
        # Create a quantize target for the lower precision
        quantize_target = Decimal('1') / (Decimal('10') ** precision_low)
        rounded_high_to_low = parsed_high.quantize(quantize_target, rounding='ROUND_HALF_EVEN')

        assert rounded_high_to_low == parsed_low, \
            f"Higher precision result ({parsed_high}) rounded to lower precision ({rounded_high_to_low}) does not match lower precision result ({parsed_low}) for ({decimal_value}, {precision_low}, {precision_high})"
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for input ({decimal_value}, {precision_low}, {precision_high}): {e}"

# Test 4: Boundary condition - decimal_value = 0
@settings(max_examples=50, deadline=None)
@given(precision=st_precision)
def test_zero_decimal_value(precision):
    decimal_value = Decimal('0')
    try:
        result_str = task_func(decimal_value, precision)
        parsed_val = parse_and_convert_to_decimal(result_str)
        assert parsed_val == Decimal('0'), f"Expected 0 for input 0, got {parsed_val}"
        # Check the number of decimal places in the string representation
        # This is a bit implementation-specific but common for JSON numbers.
        # "0" or "0.0" or "0.00" etc.
        if '.' in result_str:
            num_decimals = len(result_str.split('.')[-1])
            assert num_decimals == precision, f"For 0, expected {precision} decimal places, got {num_decimals} in '{result_str}'"
        elif precision > 0:
            # If precision > 0, it should have a decimal point.
            assert False, f"For 0 with precision {precision}, expected decimal point, got '{result_str}'"
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for input (0, {precision}): {e}"

# Test 5: Boundary condition - precision = 0
@settings(max_examples=50, deadline=None)
@given(decimal_value=st_decimal_value)
def test_zero_precision(decimal_value):
    precision = 0
    try:
        result_str = task_func(decimal_value, precision)
        parsed_val = parse_and_convert_to_decimal(result_str)
        
        # The result should be an integer (or a Decimal with no fractional part)
        assert parsed_val == parsed_val.to_integral_value(rounding='ROUND_HALF_EVEN'), \
            f"With precision 0, expected integer result, got {parsed_val}"
        
        # Check that the JSON string does not contain a decimal point if it's an integer
        # This is a common JSON serialization behavior for integers.
        if parsed_val == parsed_val.to_integral_value(): # Check if it's exactly an integer
            assert '.' not in result_str, f"With precision 0, expected no decimal point in JSON string for integer result, got '{result_str}'"
        else: # If it's a rounded value like 1.0, it might still have a decimal.
            # The important part is that the value itself has no fractional component.
            pass # The previous assertion `parsed_val == parsed_val.to_integral_value()` covers this.

    except Exception as e:
        assert False, f"task_func raised an unexpected exception for input ({decimal_value}, {precision}): {e}"

# Test 6: Invariant - result is always non-negative
@settings(max_examples=50, deadline=None)
@given(decimal_value=st_decimal_value, precision=st_precision)
def test_result_is_non_negative(decimal_value, precision):
    try:
        result_str = task_func(decimal_value, precision)
        parsed_val = parse_and_convert_to_decimal(result_str)
        assert parsed_val >= Decimal('0'), f"Expected non-negative result, got {parsed_val}"
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for input ({decimal_value}, {precision}): {e}"

# Test 7: Metamorphic relation - scaling input scales output (sqrt(k*x) = sqrt(k)*sqrt(x))
# This is tricky due to rounding. A more robust check: sqrt(x*x) = x
@settings(max_examples=50, deadline=None)
@given(
    base_value=st.decimals(min_value=Decimal('0.1'), max_value=Decimal('1e50'), places=st.integers(min_value=0, max_value=10)),
    precision=st_precision
)
def test_sqrt_of_square_is_original_value(base_value, precision):
    # Test sqrt(x^2) = x
    # We need to ensure x^2 doesn't overflow float or Decimal limits.
    # base_value is already constrained.
    decimal_value = base_value * base_value
    
    # If decimal_value becomes too large for float, math.sqrt might return inf.
    # Let's cap base_value to avoid this. Max float is ~1.8e308, so max base_value is ~1.3e154.
    # Our st_decimal_value goes up to 1e100, so base_value up to 1e50 is fine.
    
    try:
        result_str = task_func(decimal_value, precision)
        parsed_val = parse_and_convert_to_decimal(result_str)

        # Compare parsed_val to base_value, considering rounding.
        # The parsed_val is rounded to 'precision' places.
        # The true value is 'base_value'.
        # We need to check if parsed_val is 'base_value' rounded to 'precision' places.
        
        # Round base_value to the same precision for comparison
        quantize_target = Decimal('1') / (Decimal('10') ** precision)
        expected_rounded_base = base_value.quantize(quantize_target, rounding='ROUND_HALF_EVEN')

        # Allow a small tolerance for float conversion inaccuracies before rounding
        # The comparison should be between the result and the *expected rounded* value.
        # Due to float conversion in math.sqrt, there might be slight differences.
        # Let's check if the absolute difference is within a very small epsilon.
        # The primary check is that the result is the rounded version of the true sqrt.
        
        # The `test_square_of_result_approximates_input` already covers the overall accuracy.
        # This test specifically checks the `sqrt(x^2) = x` property.
        # The `parsed_val` should be very close to `base_value`.
        
        # Let's use a small absolute tolerance for the comparison,
        # as `parsed_val` is already rounded.
        # The tolerance should be slightly larger than the rounding error.
        tolerance = Decimal('1e-') + Decimal(str(precision + 2))
        
        assert abs(parsed_val - base_value) <= tolerance, \
            f"sqrt(x^2) != x for x={base_value}, x^2={decimal_value}, precision={precision}. Got {parsed_val}"

    except Exception as e:
        assert False, f"task_func raised an unexpected exception for input ({decimal_value}, {precision}): {e}"

# Test 8: Edge case - very small non-zero decimal_value
@settings(max_examples=50, deadline=None)
@given(
    decimal_value=st.decimals(min_value=Decimal('1e-100'), max_value=Decimal('1e-10'), places=st.integers(min_value=0, max_value=10)),
    precision=st_precision
)
def test_very_small_decimal_value(decimal_value, precision):
    try:
        result_str = task_func(decimal_value, precision)
        parsed_val = parse_and_convert_to_decimal(result_str)
        
        # Compare to actual sqrt, rounded
        true_sqrt_float = math.sqrt(float(decimal_value))
        
        # Convert to Decimal and round
        expected_sqrt_decimal = Decimal(str(true_sqrt_float))
        quantize_target = Decimal('1') / (Decimal('10') ** precision)
        expected_rounded = expected_sqrt_decimal.quantize(quantize_target, rounding='ROUND_HALF_EVEN')

        # Allow a small absolute tolerance for comparison due to float conversion
        tolerance = Decimal('1e-') + Decimal(str(precision + 5)) # More tolerance for very small numbers
        assert abs(parsed_val - expected_rounded) <= tolerance, \
            f"Result {parsed_val} not close to expected {expected_rounded} for very small input ({decimal_value}, {precision})"
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for input ({decimal_value}, {precision}): {e}"

# Test 9: Edge case - large decimal_value
@settings(max_examples=50, deadline=None)
@given(
    decimal_value=st.decimals(min_value=Decimal('1e50'), max_value=Decimal('1e100'), places=st.integers(min_value=0, max_value=10)),
    precision=st_precision
)
def test_very_large_decimal_value(decimal_value, precision):
    try:
        result_str = task_func(decimal_value, precision)
        parsed_val = parse_and_convert_to_decimal(result_str)
        
        # Compare to actual sqrt, rounded
        true_sqrt_float = math.sqrt(float(decimal_value))
        
        # Convert to Decimal and round
        expected_sqrt_decimal = Decimal(str(true_sqrt_float))
        quantize_target = Decimal('1') / (Decimal('10') ** precision)
        expected_rounded = expected_sqrt_decimal.quantize(quantize_target, rounding='ROUND_HALF_EVEN')

        # Use relative tolerance for large numbers
        if expected_rounded != Decimal('0'):
            assert abs(parsed_val - expected_rounded) / abs(expected_rounded) < Decimal('1e-') + Decimal(str(precision + 2)), \
                f"Result {parsed_val} not close to expected {expected_rounded} for large input ({decimal_value}, {precision})"
        else: # If expected_rounded is 0, use absolute tolerance
            assert abs(parsed_val - expected_rounded) < Decimal('1e-') + Decimal(str(precision + 5)), \
                f"Result {parsed_val} not close to expected {expected_rounded} for large input ({decimal_value}, {precision})"
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for input ({decimal_value}, {precision}): {e}"

# Test 10: Metamorphic relation - sqrt(x) with precision P should be consistent with sqrt(x) with precision P+1 rounded to P
# This is similar to Test 3 but focuses on the consistency of the rounding itself.
@settings(max_examples=50, deadline=None)
@given(
    decimal_value=st_decimal_value,
    precision_base=st_precision,
    precision_offset=st.integers(min_value=1, max_value=5) # Offset for higher precision
)
def test_rounding_consistency_across_precisions(decimal_value, precision_base, precision_offset):
    precision_higher = precision_base + precision_offset
    
    try:
        result_base_str = task_func(decimal_value, precision_base)
        result_higher_str = task_func(decimal_value, precision_higher)

        parsed_base = parse_and_convert_to_decimal(result_base_str)
        parsed_higher = parse_and_convert_to_decimal(result_higher_str)

        # Round the higher precision result to the base precision
        quantize_target = Decimal('1') / (Decimal('10') ** precision_base)
        rounded_higher_to_base = parsed_higher.quantize(quantize_target, rounding='ROUND_HALF_EVEN')

        assert rounded_higher_to_base == parsed_base, \
            f"Result with higher precision ({parsed_higher}) rounded to base precision ({rounded_higher_to_base}) does not match base precision result ({parsed_base}) for ({decimal_value}, {precision_base}, {precision_higher})"
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for input ({decimal_value}, {precision_base}, {precision_higher}): {e}"