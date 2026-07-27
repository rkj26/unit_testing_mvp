from candidate import task_func
from hypothesis import given, settings, strategies as st
import collections
import math
import io
import sys

@settings(max_examples=50, deadline=None)
@given(l=st.lists(st.integers(min_value=-100, max_value=100), min_size=0, max_size=12))
def test_return_type_is_deque(l):
    result = task_func(l)
    assert isinstance(result, collections.deque)

@settings(max_examples=50, deadline=None)
@given(l=st.lists(st.integers(min_value=-100, max_value=100), min_size=0, max_size=12))
def test_deque_length_is_preserved(l):
    result = task_func(l)
    assert len(result) == len(l)

@settings(max_examples=50, deadline=None)
@given(l=st.lists(st.integers(min_value=-100, max_value=100), min_size=0, max_size=12))
def test_deque_elements_are_preserved(l):
    result = task_func(l)
    # Convert to sorted lists to compare elements regardless of order
    assert sorted(list(result)) == sorted(l)

@settings(max_examples=50, deadline=None)
@given(l=st.lists(st.integers(min_value=-100, max_value=100), min_size=0, max_size=12))
def test_rotation_logic(l):
    expected_deque = collections.deque(l)
    expected_deque.rotate(3)
    result = task_func(l)
    assert result == expected_deque

@settings(max_examples=50, deadline=None)
@given(l=st.lists(st.integers(min_value=-100, max_value=100), min_size=0, max_size=12))
def test_rotation_with_empty_list(l):
    if not l:
        result = task_func(l)
        assert result == collections.deque([])

@settings(max_examples=50, deadline=None)
@given(l=st.lists(st.integers(min_value=-100, max_value=100), min_size=1, max_size=2))
def test_rotation_with_small_lists(l):
    # For lists of size 1 or 2, rotation by 3 is equivalent to rotation by 3 % len(l)
    expected_deque = collections.deque(l)
    expected_deque.rotate(3)
    result = task_func(l)
    assert result == expected_deque

@settings(max_examples=50, deadline=None)
@given(l=st.lists(st.one_of(st.integers(min_value=-100, max_value=100), st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False)), min_size=0, max_size=12))
def test_numeric_sum_and_sqrt_output(l):
    numeric_elements = [x for x in l if isinstance(x, (int, float))]
    
    captured_output = io.StringIO()
    sys.stdout = captured_output
    
    task_func(l)
    
    sys.stdout = sys.__stdout__ # Reset stdout
    
    output = captured_output.getvalue()
    
    if numeric_elements:
        sum_numeric = sum(numeric_elements)
        if sum_numeric >= 0:
            expected_sqrt = math.sqrt(sum_numeric)
            # Check if the expected string is present in the output
            assert f"The square root of the sum of numeric elements: {expected_sqrt}" in output
        else:
            # If sum is negative, math.sqrt would raise ValueError, but the problem implies
            # it's for demonstration and doesn't specify behavior for negative sums.
            # Assuming it might print NaN or an error, or just not print the sqrt line.
            # The most robust check is that if sum_numeric is non-negative, the sqrt is printed.
            # If sum_numeric is negative, the problem doesn't specify what should be printed.
            # We'll assume it won't print a valid sqrt for negative sums.
            assert "The square root of the sum of numeric elements:" not in output or "nan" in output.lower()
    else:
        # If no numeric elements, no square root line should be printed
        assert "The square root of the sum of numeric elements:" not in output

@settings(max_examples=50, deadline=None)
@given(l=st.lists(st.text(alphabet="abc", min_size=1, max_size=5), min_size=0, max_size=12))
def test_rotation_with_non_numeric_elements(l):
    # Ensure rotation works correctly even if no numeric elements are present
    expected_deque = collections.deque(l)
    expected_deque.rotate(3)
    result = task_func(l)
    assert result == expected_deque

@settings(max_examples=50, deadline=None)
@given(l=st.lists(st.one_of(st.integers(min_value=0, max_value=100), st.text(alphabet="xyz", min_size=1, max_size=5)), min_size=0, max_size=12))
def test_mixed_types_rotation(l):
    # Test rotation with a mix of numeric and non-numeric types
    expected_deque = collections.deque(l)
    expected_deque.rotate(3)
    result = task_func(l)
    assert result == expected_deque

@settings(max_examples=50, deadline=None)
@given(l=st.lists(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False, places=4), min_size=0, max_size=12))
def test_numeric_sum_and_sqrt_with_floats(l):
    # Test specifically with floats for the numeric sum part
    captured_output = io.StringIO()
    sys.stdout = captured_output
    
    task_func(l)
    
    sys.stdout = sys.__stdout__ # Reset stdout
    
    output = captured_output.getvalue()
    
    if l:
        sum_numeric = sum(l)
        expected_sqrt = math.sqrt(sum_numeric)
        assert f"The square root of the sum of numeric elements: {expected_sqrt}" in output
    else:
        assert "The square root of the sum of numeric elements:" not in output