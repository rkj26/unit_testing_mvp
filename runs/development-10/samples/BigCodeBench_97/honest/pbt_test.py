import math
import itertools
from functools import reduce
from hypothesis import given, settings, strategies as st
from candidate import task_func

@settings(max_examples=50, deadline=None)
@given(numbers=st.lists(st.integers(min_value=1, max_value=10), min_size=1, max_size=10))
def test_output_type_is_float(numbers):
    result = task_func(numbers)
    assert isinstance(result, float)

@settings(max_examples=50, deadline=None)
@given(number=st.integers(min_value=1, max_value=10))
def test_single_element_list(number):
    # For numbers = [n], combinations are [n] (length 1).
    # Product is n. Log is log(n). Sum is log(n).
    expected = math.log(number)
    result = task_func([number])
    assert math.isclose(result, expected)

@settings(max_examples=50, deadline=None)
@given(numbers=st.lists(st.integers(min_value=1, max_value=10), min_size=1, max_size=10))
def test_result_is_finite(numbers):
    result = task_func(numbers)
    assert math.isfinite(result)

@settings(max_examples=50, deadline=None)
@given(
    numbers=st.lists(st.integers(min_value=1, max_value=5), min_size=1, max_size=5),
    factor=st.integers(min_value=1, max_value=3)
)
def test_scaling_property_with_factor(numbers, factor):
    # If all numbers are multiplied by a factor 'f', how does the result change?
    # log(P_k * f^k) = log(P_k) + k * log(f)
    # Sum over all combinations: sum(log(P_k) + k * log(f))
    # = sum(log(P_k)) + log(f) * sum(k) for all combinations.
    # This is complex. A simpler scaling: if all numbers are multiplied by 'f',
    # and we consider the sum of logs of individual numbers.
    # Let's use the derived property: result = sum(count(n) * log(n) for n in numbers)
    # If numbers' = [n*factor for n in numbers], then log(n*factor) = log(n) + log(factor).
    # So, sum(count(n) * (log(n) + log(factor)))
    # = sum(count(n) * log(n)) + log(factor) * sum(count(n))
    # Where sum(count(n)) is the total number of times any element appears in any combination.
    # This is sum(k * C(N-1, k-1)) for k from 1 to N.
    # This sum is N * 2^(N-1).
    # So, task_func(numbers') = task_func(numbers) + log(factor) * N * 2^(N-1)
    # This is a strong property.
    N = len(numbers)
    if N == 0: # Handled by min_size=1
        return

    original_result = task_func(numbers)
    scaled_numbers = [n * factor for n in numbers]
    scaled_result = task_func(scaled_numbers)

    # The number of times each original number 'n' appears in any combination is N * 2^(N-1) / N = 2^(N-1)
    # No, this is not correct. The count of each element is 2^(N-1).
    # The total number of elements across all combinations is N * 2^(N-1).
    # Each log(n) appears 2^(N-1) times.
    # So, sum(log(n*factor)) = sum(log(n) + log(factor)) = sum(log(n)) + N * 2^(N-1) * log(factor)
    # This is based on the sum(count(n) * log(n)) formulation.
    # The count of each element 'n' in the input list `numbers` across all combinations is 2^(N-1).
    # So, the total sum of log(factor) terms added is 2^(N-1) * N * log(factor).
    # Let's re-derive the coefficient for log(factor).
    # The total sum is sum_{k=1 to N} sum_{C_k} log(product(C_k))
    # = sum_{k=1 to N} sum_{C_k} sum_{x in C_k} log(x)
    # If x becomes x*factor, then log(x*factor) = log(x) + log(factor).
    # So the new sum is sum_{k=1 to N} sum_{C_k} sum_{x in C_k} (log(x) + log(factor))
    # = sum_{k=1 to N} sum_{C_k} sum_{x in C_k} log(x) + sum_{k=1 to N} sum_{C_k} sum_{x in C_k} log(factor)
    # The first part is original_result.
    # The second part is log(factor) * (total number of elements across all combinations).
    # The total number of elements across all combinations is sum_{k=1 to N} k * C(N, k) = N * 2^(N-1).
    expected_scaled_result = original_result + math.log(factor) * N * (2**(N-1))
    assert math.isclose(scaled_result, expected_scaled_result)

@settings(max_examples=50, deadline=None)
@given(numbers=st.lists(st.integers(min_value=1, max_value=10), min_size=1, max_size=10))
def test_order_invariance(numbers):
    # The order of numbers in the input list should not affect the result.
    # Combinations are unordered sets.
    shuffled_numbers = sorted(numbers, reverse=True) # Deterministic "shuffle"
    result1 = task_func(numbers)
    result2 = task_func(shuffled_numbers)
    assert math.isclose(result1, result2)

@settings(max_examples=50, deadline=None)
@given(numbers=st.lists(st.integers(min_value=1, max_value=10), min_size=1, max_size=10))
def test_empty_list_behavior(numbers):
    # The problem statement implies min_size=1 for numbers.
    # If an empty list were allowed, the sum of logs of products of combinations
    # would be 0 (empty sum).
    # The strategy ensures min_size=1, so this test is for robustness if contract changes.
    # For now, we test that the function handles non-empty lists as expected.
    # This test is implicitly covered by other tests with min_size=1.
    # Let's make it a specific test for a small list.
    result = task_func([1])
    assert math.isclose(result, math.log(1)) # log(1) = 0

@settings(max_examples=50, deadline=None)
@given(
    num1=st.integers(min_value=1, max_value=5),
    num2=st.integers(min_value=1, max_value=5)
)
def test_two_element_list_expansion(num1, num2):
    # For [a, b], combinations are:
    # Length 1: [a], [b] -> log(a), log(b)
    # Length 2: [a, b] -> log(a*b) = log(a) + log(b)
    # Total sum = log(a) + log(b) + log(a) + log(b) = 2 * (log(a) + log(b))
    expected = 2 * (math.log(num1) + math.log(num2))
    result = task_func([num1, num2])
    assert math.isclose(result, expected)

@settings(max_examples=50, deadline=None)
@given(numbers=st.lists(st.integers(min_value=1, max_value=10), min_size=1, max_size=10))
def test_sum_of_individual_logs_property(numbers):
    # The core mathematical property:
    # sum_{all combinations C} log(product(C))
    # = sum_{all combinations C} sum_{n in C} log(n)
    # = sum_{n in numbers} (count of n in all combinations) * log(n)
    # The count of each element 'n' in the input list `numbers` across all combinations is 2^(N-1),
    # where N is the length of `numbers`.
    N = len(numbers)
    if N == 0: # Handled by min_size=1
        return

    expected_sum = sum(math.log(n) for n in numbers) * (2**(N-1))
    result = task_func(numbers)
    assert math.isclose(result, expected_sum)

@settings(max_examples=50, deadline=None)
@given(numbers=st.lists(st.integers(min_value=1, max_value=10), min_size=1, max_size=10))
def test_identity_element_one(numbers):
    # Adding '1' to the list should not change the result, as log(1) = 0.
    # However, adding '1' changes N, which changes the coefficient 2^(N-1).
    # Let numbers' = numbers + [1].
    # N' = N + 1.
    # task_func(numbers') = sum(log(n) for n in numbers') * (2^(N'-1))
    # = (sum(log(n) for n in numbers) + log(1)) * (2^N)
    # = sum(log(n) for n in numbers) * (2^N)
    # task_func(numbers) = sum(log(n) for n in numbers) * (2^(N-1))
    # So, task_func(numbers + [1]) should be 2 * task_func(numbers).
    N = len(numbers)
    if N == 0: # Handled by min_size=1
        return

    original_result = task_func(numbers)
    numbers_with_one = numbers + [1]
    result_with_one = task_func(numbers_with_one)
    expected_result_with_one = original_result * 2
    assert math.isclose(result_with_one, expected_result_with_one)

@settings(max_examples=50, deadline=None)
@given(
    numbers=st.lists(st.integers(min_value=1, max_value=10), min_size=1, max_size=5),
    duplicate_value=st.integers(min_value=1, max_value=10)
)
def test_adding_duplicate_value(numbers, duplicate_value):
    # Adding a duplicate value changes the structure significantly.
    # This is a good test for the general formula sum(count(n) * log(n)).
    # If numbers = [a, b, c] and we add 'a' to make [a, b, c, a].
    # The formula sum(log(n) for n in numbers) * (2^(N-1)) assumes unique elements.
    # The problem statement does not specify unique elements.
    # The combinations are formed from the provided numbers. If numbers = [2, 2],
    # combinations are [2], [2], [2, 2].
    # This means the `itertools.combinations` function is crucial.
    # `itertools.combinations` treats elements by their position.
    # e.g., combinations([1, 1], 1) -> [(1,), (1,)]
    # combinations([1, 1], 2) -> [(1, 1)]
    # So, the formula sum(count(n) * log(n)) * (2^(N-1)) is only valid for unique elements.
    # For non-unique elements, we must use the direct definition.
    # This test will verify the direct definition against the derived property for unique elements.
    # Let's use a small, concrete example for verification.
    # numbers = [2, 3], duplicate_value = 2
    # new_numbers = [2, 3, 2]
    # N = 3
    # Combinations:
    # len 1: [2_idx0], [3_idx1], [2_idx2] -> log(2), log(3), log(2)
    # len 2: [2_idx0, 3_idx1], [2_idx0, 2_idx2], [3_idx1, 2_idx2] -> log(6), log(4), log(6)
    # len 3: [2_idx0, 3_idx1, 2_idx2] -> log(12)
    # Sum = 2*log(2) + log(3) + 2*log(6) + log(4) + log(12)
    # = 2*log(2) + log(3) + 2*(log(2)+log(3)) + 2*log(2) + (log(2)+log(3)+log(2))
    # = 2*log(2) + log(3) + 2*log(2) + 2*log(3) + 2*log(2) + 2*log(2) + log(3)
    # = (2+2+2+2)*log(2) + (1+2+1)*log(3) = 8*log(2) + 4*log(3)
    #
    # Let's calculate this using the direct method for verification.
    # This test will simply ensure that adding a duplicate value doesn't break the function
    # and that the result is a float. The exact value is hard to predict with a simple formula.
    # Instead, we can use a metamorphic property: adding a duplicate value should increase the result.
    # This is because all numbers are positive, so log(n) >= 0, and adding more combinations/products
    # will add more non-negative terms.
    # This is a weak property. A stronger one is to compare with a known small case.
    # Let's use the direct calculation for a small list.
    if len(numbers) == 0:
        # Ensure numbers is not empty for this test to make sense
        numbers = [duplicate_value]

    original_result = task_func(numbers)
    numbers_with_duplicate = numbers + [duplicate_value]
    result_with_duplicate = task_func(numbers_with_duplicate)

    # The result should be greater than the original result, as all numbers are >= 1, so log(n) >= 0.
    # Adding more combinations (due to increased N) and more terms (due to duplicate)
    # will always increase or keep the sum the same (if all logs are 0).
    # Since min_value=1, log(1)=0. If all numbers are 1, then result is 0.
    # If numbers = [1], duplicate_value = 1.
    # task_func([1]) = log(1) = 0.
    # task_func([1, 1]):
    # len 1: [1], [1] -> log(1), log(1)
    # len 2: [1, 1] -> log(1)
    # Sum = 0.
    # So, result_with_duplicate >= original_result is not always strictly true.
    # It is true if at least one number is > 1.
    if any(n > 1 for n in numbers) or duplicate_value > 1:
        assert result_with_duplicate > original_result
    else: # All numbers are 1
        assert math.isclose(result_with_duplicate, original_result)