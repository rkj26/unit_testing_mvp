from candidate import task_func
from hypothesis import given, settings, strategies as st
import math
import itertools
from functools import reduce
import operator

# Helper function to compute the expected result, avoiding direct re-implementation of task_func's structure
# but rather focusing on the mathematical properties.
def _expected_log_sum_products(numbers):
    if not numbers:
        return 0.0

    # Filter out non-positive numbers as math.log is undefined for them.
    # If the input contains non-positive numbers, the function should ideally raise an error or handle it.
    # For testing, we'll assume valid inputs for the log operation.
    # If the problem implies 0 or negative numbers are valid inputs, then the function should handle them.
    # Given the `math.log` step, we'll generate positive numbers for most tests.
    positive_numbers = [n for n in numbers if n > 0]

    if not positive_numbers: # If all numbers were non-positive
        return 0.0 # Or raise an error, depending on specification. For now, assume 0.0 for empty positive set.

    total_sum_logs = 0.0
    for i in range(1, len(positive_numbers) + 1):
        for combination in itertools.combinations(positive_numbers, i):
            product = reduce(operator.mul, combination, 1)
            # If product is 0 (due to 0 in combination, though we filtered positive_numbers), log(0) is error.
            # If product is 1, log(1) is 0.
            # If product is negative (due to negative numbers, though we filtered positive_numbers), log(negative) is error.
            if product > 0:
                total_sum_logs += math.log(product)
            else:
                # This case should ideally not be reached if positive_numbers only contains positive integers.
                # If it does, it implies an issue with input generation or an edge case not fully specified.
                # For robustness, we might want to raise an error here in a canonical implementation.
                pass
    return total_sum_logs

# Strategy for generating lists of positive integers, suitable for math.log
positive_ints_strategy = st.lists(st.integers(min_value=1, max_value=100), min_size=0, max_size=10)

# Strategy for generating lists of integers including zero and negative numbers, to test robustness
all_ints_strategy = st.lists(st.integers(min_value=-10, max_value=10), min_size=0, max_size=10)

# Strategy for generating lists of floats, to test type handling (though problem states int)
# This is a boundary/unusual input test, as the problem specifies `list of int`.
# If the function is robust, it might convert or handle floats. If not, it might raise an error.
# We'll stick to integers as per problem statement for most tests.

@settings(max_examples=50, deadline=None)
@given(numbers=positive_ints_strategy)
def test_output_type_is_float(numbers):
    """
    Test that the function always returns a float.
    """
    try:
        result = task_func(numbers)
        assert isinstance(result, float), f"Expected float, got {type(result)} for input {numbers}"
    except Exception as e:
        assert False, f"Function raised an unexpected exception {type(e).__name__}: {e} for input {numbers}"

@settings(max_examples=50, deadline=None)
@given(numbers=positive_ints_strategy)
def test_empty_list_returns_zero(numbers):
    """
    Test that an empty list of numbers results in 0.0.
    """
    if not numbers:
        try:
            result = task_func(numbers)
            assert result == 0.0, f"Expected 0.0 for empty list, got {result}"
        except Exception as e:
            assert False, f"Function raised an unexpected exception {type(e).__name__}: {e} for empty input"

@settings(max_examples=50, deadline=None)
@given(numbers=positive_ints_strategy)
def test_single_element_list(numbers):
    """
    Test behavior with a single element list. The result should be log(element).
    """
    if len(numbers) == 1:
        num = numbers[0]
        try:
            result = task_func(numbers)
            expected = math.log(num) if num > 0 else 0.0 # Assuming positive numbers for log
            assert math.isclose(result, expected, rel_tol=1e-9), \
                f"For input {numbers}, expected {expected}, got {result}"
        except Exception as e:
            assert False, f"Function raised an unexpected exception {type(e).__name__}: {e} for input {numbers}"

@settings(max_examples=50, deadline=None)
@given(numbers=positive_ints_strategy)
def test_invariance_to_order(numbers):
    """
    Test that the order of numbers in the input list does not affect the result.
    This is a metamorphic property.
    """
    if len(numbers) > 1:
        shuffled_numbers = list(numbers)
        import random
        random.shuffle(shuffled_numbers)
        if numbers == shuffled_numbers: # Ensure it's actually shuffled if possible
            shuffled_numbers = list(numbers)
            if len(shuffled_numbers) > 1:
                shuffled_numbers[0], shuffled_numbers[1] = shuffled_numbers[1], shuffled_numbers[0]

        try:
            result1 = task_func(numbers)
            result2 = task_func(shuffled_numbers)
            assert math.isclose(result1, result2, rel_tol=1e-9), \
                f"Order changed result: {numbers} -> {result1}, {shuffled_numbers} -> {result2}"
        except Exception as e:
            assert False, f"Function raised an unexpected exception {type(e).__name__}: {e} for input {numbers} or {shuffled_numbers}"

@settings(max_examples=50, deadline=None)
@given(numbers=positive_ints_strategy)
def test_mathematical_identity_log_product_is_sum_logs(numbers):
    """
    Test the mathematical identity: log(a*b) = log(a) + log(b).
    The sum of logs of products should be equal to the sum of logs of individual numbers,
    multiplied by the number of times each number appears in a product.
    This is a core mathematical property.
    """
    if not numbers:
        try:
            assert task_func(numbers) == 0.0
        except Exception as e:
            assert False, f"Exception for empty list: {e}"
        return

    try:
        actual_result = task_func(numbers)

        # Calculate expected result using the identity:
        # Sum of log(product(combination))
        # = Sum over all combinations (Sum over elements in combination (log(element)))
        # This means each log(n) for n in numbers appears in 2^(len(numbers)-1) combinations.
        # For example, for [a, b, c]:
        # Combos: [a], [b], [c], [a,b], [a,c], [b,c], [a,b,c]
        # Products: a, b, c, ab, ac, bc, abc
        # Logs: log(a), log(b), log(c), log(a)+log(b), log(a)+log(c), log(b)+log(c), log(a)+log(b)+log(c)
        # Sum of logs:
        # log(a) appears 1 (from [a]) + 1 (from [a,b]) + 1 (from [a,c]) + 1 (from [a,b,c]) = 4 times
        # For N elements, each element appears in 2^(N-1) combinations.
        # So, expected_sum = sum(log(n) * 2^(len(numbers)-1) for n in numbers)

        num_elements = len(numbers)
        if num_elements == 0:
            expected_result = 0.0
        else:
            multiplier = 2**(num_elements - 1)
            expected_result = sum(math.log(n) * multiplier for n in numbers if n > 0)

        assert math.isclose(actual_result, expected_result, rel_tol=1e-9), \
            f"Mathematical identity failed for {numbers}: Expected {expected_result}, Got {actual_result}"
    except ValueError as ve:
        # If numbers contain non-positive values, math.log will raise ValueError.
        # This test specifically relies on positive numbers.
        assert all(n > 0 for n in numbers), f"ValueError for non-positive number in {numbers}: {ve}"
        assert False, f"Function raised ValueError for valid positive input {numbers}: {ve}"
    except Exception as e:
        assert False, f"Function raised an unexpected exception {type(e).__name__}: {e} for input {numbers}"

@settings(max_examples=50, deadline=None)
@given(numbers=st.lists(st.integers(min_value=1, max_value=2), min_size=0, max_size=10))
def test_small_numbers_exact_calculation(numbers):
    """
    Test with very small numbers (1s and 2s) where products are less likely to overflow
    and calculations can be verified more easily.
    """
    try:
        actual_result = task_func(numbers)
        expected_result = _expected_log_sum_products(numbers)
        assert math.isclose(actual_result, expected_result, rel_tol=1e-9), \
            f"Mismatch for small numbers {numbers}: Expected {expected_result}, Got {actual_result}"
    except Exception as e:
        assert False, f"Function raised an unexpected exception {type(e).__name__}: {e} for input {numbers}"

@settings(max_examples=50, deadline=None)
@given(numbers=st.lists(st.integers(min_value=1, max_value=100), min_size=0, max_size=10))
def test_consistency_with_reference_implementation(numbers):
    """
    Test the function's output against a simple, direct reference implementation.
    This is a general correctness check.
    """
    try:
        actual_result = task_func(numbers)
        expected_result = _expected_log_sum_products(numbers)
        assert math.isclose(actual_result, expected_result, rel_tol=1e-9), \
            f"Mismatch for {numbers}: Expected {expected_result}, Got {actual_result}"
    except Exception as e:
        assert False, f"Function raised an unexpected exception {type(e).__name__}: {e} for input {numbers}"

@settings(max_examples=50, deadline=None)
@given(numbers=st.lists(st.integers(min_value=1, max_value=100), min_size=0, max_size=10))
def test_adding_one_to_all_numbers_metamorphic(numbers):
    """
    Metamorphic test: If we add 1 to all numbers, how does the result change?
    This is complex due to combinations, but we can check against the reference.
    """
    if not numbers:
        try:
            assert task_func(numbers) == 0.0
        except Exception as e:
            assert False, f"Exception for empty list: {e}"
        return

    numbers_plus_one = [n + 1 for n in numbers]
    try:
        result_original = task_func(numbers)
        result_plus_one = task_func(numbers_plus_one)

        expected_original = _expected_log_sum_products(numbers)
        expected_plus_one = _expected_log_sum_products(numbers_plus_one)

        assert math.isclose(result_original, expected_original, rel_tol=1e-9), \
            f"Original mismatch for {numbers}: Expected {expected_original}, Got {result_original}"
        assert math.isclose(result_plus_one, expected_plus_one, rel_tol=1e-9), \
            f"Plus one mismatch for {numbers_plus_one}: Expected {expected_plus_one}, Got {result_plus_one}"
    except Exception as e:
        assert False, f"Function raised an unexpected exception {type(e).__name__}: {e} for input {numbers} or {numbers_plus_one}"

@settings(max_examples=50, deadline=None)
@given(numbers=st.lists(st.integers(min_value=1, max_value=100), min_size=0, max_size=10))
def test_numbers_containing_one(numbers):
    """
    Test behavior when the list contains the number 1.
    Products involving 1 should not change the product value. log(1) is 0.
    """
    numbers_with_one = numbers + [1] * st.integers(min_value=0, max_value=3).example()
    if not numbers_with_one: # Ensure it's not empty after adding 1s
        numbers_with_one = [1]

    try:
        actual_result = task_func(numbers_with_one)
        expected_result = _expected_log_sum_products(numbers_with_one)
        assert math.isclose(actual_result, expected_result, rel_tol=1e-9), \
            f"Mismatch for numbers including 1: {numbers_with_one}: Expected {expected_result}, Got {actual_result}"
    except Exception as e:
        assert False, f"Function raised an unexpected exception {type(e).__name__}: {e} for input {numbers_with_one}"

@settings(max_examples=50, deadline=None)
@given(numbers=st.lists(st.integers(min_value=1, max_value=100), min_size=0, max_size=10))
def test_duplicate_numbers(numbers):
    """
    Test behavior with duplicate numbers in the input list.
    The combinations should still be distinct based on position, but values are the same.
    """
    if len(numbers) > 0:
        # Add some duplicates
        duplicate_numbers = numbers + [numbers[0]] * st.integers(min_value=0, max_value=2).example()
        if len(duplicate_numbers) > 10: # Keep size bounded
            duplicate_numbers = duplicate_numbers[:10]
    else:
        duplicate_numbers = [2, 2, 3] # Ensure a non-empty list with duplicates

    try:
        actual_result = task_func(duplicate_numbers)
        expected_result = _expected_log_sum_products(duplicate_numbers)
        assert math.isclose(actual_result, expected_result, rel_tol=1e-9), \
            f"Mismatch for duplicate numbers {duplicate_numbers}: Expected {expected_result}, Got {actual_result}"
    except Exception as e:
        assert False, f"Function raised an unexpected exception {type(e).__name__}: {e} for input {duplicate_numbers}"