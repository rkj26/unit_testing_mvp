import math
import itertools
from functools import reduce
from hypothesis import given, settings, strategies as st
from candidate import task_func

# Strategy for generating lists of positive integers suitable for logarithms
# Max size 12 as per instructions. Integers are positive to avoid math.log domain errors.
# Using a reasonable range to prevent extreme values that might lead to overflow/underflow
# in intermediate products or logs, while still covering a good range.
positive_integers_strategy = st.lists(
    st.integers(min_value=2, max_value=100),
    min_size=0,
    max_size=12
)

@given(numbers=positive_integers_strategy)
@settings(max_examples=50, deadline=None)
def test_return_type_is_float(numbers):
    """
    SPEC BASIS: "Returns: float: The sum of the logarithms of the products of all combinations of numbers."
                "Examples: ... type(task_func(numbers)) == float"
    PROPERTY: The function must always return a float.
    """
    result = task_func(numbers)
    assert isinstance(result, float)

@given(numbers=st.just([]))
@settings(max_examples=50, deadline=None)
def test_empty_list_returns_zero(numbers):
    """
    SPEC BASIS: Implicit boundary condition for combinations.
    PROPERTY: When the input list is empty, there are no combinations, so the sum of logarithms should be 0.0.
    """
    result = task_func(numbers)
    assert result == 0.0

@given(number=st.integers(min_value=2, max_value=100))
@settings(max_examples=50, deadline=None)
def test_single_element_list_behavior(number):
    """
    SPEC BASIS: "Generates all possible combinations ... For each combination, it computes the product ...
                 It then computes the logarithm of each product and sums these logarithms..."
    PROPERTY: For a list with a single element [x], the only combination is [x], its product is x,
              and the sum of logarithms is simply log(x).
    """
    numbers = [number]
    result = task_func(numbers)
    expected_result = math.log(number)
    # Using math.isclose for float comparison due to potential precision issues
    assert math.isclose(result, expected_result, rel_tol=1e-9)

@given(numbers=st.lists(st.integers(min_value=2, max_value=100), min_size=0, max_size=12))
@settings(max_examples=50, deadline=None)
def test_invariance_to_sorting(numbers):
    """
    SPEC BASIS: "Generates all possible combinations of the provided numbers..."
    PROPERTY: The order of elements in the input list should not affect the final result,
              as combinations are inherently order-agnostic. Specifically, sorting the input
              list should yield the same result.
    """
    original_result = task_func(numbers)
    sorted_numbers = sorted(numbers)
    sorted_result = task_func(sorted_numbers)
    assert math.isclose(original_result, sorted_result, rel_tol=1e-9)

@given(a=st.integers(min_value=2, max_value=50), b=st.integers(min_value=2, max_value=50))
@settings(max_examples=50, deadline=None)
def test_two_element_list_logarithm_property(a, b):
    """
    SPEC BASIS: "Generates all possible combinations ... computes the product ... computes the logarithm ... sums these logarithms"
    PROPERTY: For a list [a, b], the combinations are [a], [b], [a, b].
              The products are a, b, a*b.
              The sum of logarithms should be log(a) + log(b) + log(a*b).
              Using the logarithm property log(a*b) = log(a) + log(b), this simplifies to
              log(a) + log(b) + (log(a) + log(b)) = 2 * (log(a) + log(b)).
    """
    numbers = [a, b]
    result = task_func(numbers)

    expected_result = math.log(a) + math.log(b) + math.log(a * b)
    # Alternatively, using the property:
    # expected_result = 2 * (math.log(a) + math.log(b))

    assert math.isclose(result, expected_result, rel_tol=1e-9)