from candidate import task_func
from hypothesis import given, settings, strategies as st
import math
import itertools
from functools import reduce
import operator

# Helper oracle function based on the specification
def _oracle_task_func(numbers):
    """
    Reference implementation of the task_func logic for testing.
    Assumes numbers are positive integers, as required by math.log.
    """
    total_log_sum = 0.0
    # Iterate through all possible lengths of combinations, from 0 to len(numbers)
    for r in range(len(numbers) + 1):
        for combination in itertools.combinations(numbers, r):
            if not combination:
                # The product of an empty set of numbers is the multiplicative identity, 1.
                # math.log(1) is 0.0.
                product = 1
            else:
                product = reduce(operator.mul, combination)

            # The problem implies natural logarithm (base e) as no base is specified.
            # Inputs are constrained to positive integers to avoid math.log errors.
            total_log_sum += math.log(product)
    return total_log_sum

@given(numbers=st.lists(st.integers(min_value=1, max_value=10), min_size=0, max_size=5))
@settings(max_examples=50, deadline=None)
def test_return_type_is_float(numbers):
    """
    SPEC BASIS: "Returns: float: The sum of the logarithms of the products of all combinations of numbers."
                "type(task_func(numbers)) == float" (example)
                "isinstance(task_func(numbers), float)" (example)
    PROPERTY: The function must return a float.
    """
    result = task_func(numbers)
    assert isinstance(result, float)

@given(numbers=st.lists(st.integers(min_value=1, max_value=10), min_size=0, max_size=5))
@settings(max_examples=50, deadline=None)
def test_output_matches_oracle(numbers):
    """
    SPEC BASIS: "Generates all possible combinations of the provided numbers in a given list for
                 each possible length. For each combination, it computes the product of the numbers
                 in the combination. It then computes the logarithm of each product and sums these
                 logarithms to produce the final result."
    PROPERTY: The function's output matches the precisely specified calculation.
    """
    expected_result = _oracle_task_func(numbers)
    actual_result = task_func(numbers)
    # Use math.isclose for float comparisons due to potential precision differences.
    # The problem does not specify precision, so a reasonable relative tolerance is used.
    assert math.isclose(actual_result, expected_result, rel_tol=1e-9, abs_tol=1e-12)

@given(numbers=st.lists(st.integers(min_value=1, max_value=10), min_size=0, max_size=5))
@settings(max_examples=50, deadline=None)
def test_determinism_for_same_input(numbers):
    """
    SPEC BASIS: The problem describes a pure mathematical function.
    PROPERTY: Calling the function with the same input multiple times should yield the same result.
    """
    result1 = task_func(numbers)
    result2 = task_func(numbers)
    assert math.isclose(result1, result2, rel_tol=1e-9, abs_tol=1e-12)

@given(numbers=st.lists(st.integers(min_value=1, max_value=10), min_size=0, max_size=5))
@settings(max_examples=50, deadline=None)
def test_empty_list_input(numbers=st.just([])):
    """
    SPEC BASIS: "Generates all possible combinations of the provided numbers in a given list for
                 each possible length." (This includes length 0 for an empty list).
    PROPERTY: An empty list input should result in 0.0 (sum of logs of products of empty combinations).
    """
    expected_result = 0.0 # Oracle for [] is 0.0
    actual_result = task_func(numbers)
    assert math.isclose(actual_result, expected_result, rel_tol=1e-9, abs_tol=1e-12)

@given(numbers=st.lists(st.integers(min_value=1, max_value=10), min_size=1, max_size=1))
@settings(max_examples=50, deadline=None)
def test_single_element_list(numbers):
    """
    SPEC BASIS: "Generates all possible combinations of the provided numbers in a given list for
                 each possible length."
    PROPERTY: For a single-element list [x], the result should be log(1) + log(x) = log(x).
    """
    x = numbers[0]
    expected_result = math.log(1) + math.log(x) # Combinations: (), (x)
    actual_result = task_func(numbers)
    assert math.isclose(actual_result, expected_result, rel_tol=1e-9, abs_tol=1e-12)

@given(numbers=st.lists(st.integers(min_value=1, max_value=10), min_size=2, max_size=2))
@settings(max_examples=50, deadline=None)
def test_two_element_list(numbers):
    """
    SPEC BASIS: "Generates all possible combinations of the provided numbers in a given list for
                 each possible length."
    PROPERTY: For a two-element list [x, y], the result should be log(1) + log(x) + log(y) + log(x*y).
    """
    x, y = numbers[0], numbers[1]
    expected_result = math.log(1) + math.log(x) + math.log(y) + math.log(x * y)
    actual_result = task_func(numbers)
    assert math.isclose(actual_result, expected_result, rel_tol=1e-9, abs_tol=1e-12)

@given(numbers=st.lists(st.integers(min_value=1, max_value=10), min_size=0, max_size=5))
@settings(max_examples=50, deadline=None)
def test_order_of_input_does_not_matter(numbers):
    """
    SPEC BASIS: "Generates all possible combinations of the provided numbers..." (combinations are order-agnostic).
    PROPERTY: The order of elements in the input list should not affect the final result.
    """
    if len(numbers) < 2:
        # Cannot meaningfully shuffle a list with less than 2 elements
        return

    original_result = task_func(numbers)
    shuffled_numbers = sorted(numbers, reverse=True) # A simple way to get a different order
    if numbers == shuffled_numbers: # Ensure it's actually different if possible
        shuffled_numbers = sorted(numbers)
        if numbers == shuffled_numbers: # If still same (e.g., all elements identical), skip
            return

    shuffled_result = task_func(shuffled_numbers)
    assert math.isclose(original_result, shuffled_result, rel_tol=1e-9, abs_tol=1e-12)

@given(numbers=st.lists(st.just(1), min_size=1, max_size=5))
@settings(max_examples=50, deadline=None)
def test_list_of_ones(numbers):
    """
    SPEC BASIS: "computes the logarithm of each product and sums these logarithms".
                math.log(1) is 0.
    PROPERTY: If all numbers are 1, all products will be 1, and all logarithms will be 0, so the sum should be 0.0.
    """
    expected_result = 0.0
    actual_result = task_func(numbers)
    assert math.isclose(actual_result, expected_result, rel_tol=1e-9, abs_tol=1e-12)

@given(numbers=st.lists(st.integers(min_value=2, max_value=2), min_size=1, max_size=5))
@settings(max_examples=50, deadline=None)
def test_list_of_twos(numbers):
    """
    SPEC BASIS: "computes the logarithm of each product and sums these logarithms".
    PROPERTY: Test with a list containing only the number 2, verifying the oracle's behavior.
    """
    expected_result = _oracle_task_func(numbers)
    actual_result = task_func(numbers)
    assert math.isclose(actual_result, expected_result, rel_tol=1e-9, abs_tol=1e-12)

@given(numbers=st.lists(st.integers(min_value=1, max_value=10), min_size=0, max_size=5))
@settings(max_examples=50, deadline=None)
def test_output_is_finite(numbers):
    """
    SPEC BASIS: "Returns: float: The sum of the logarithms..." (implies a finite number).
    PROPERTY: The result should be a finite floating-point number (not infinity or NaN).
    """
    result = task_func(numbers)
    assert math.isfinite(result)