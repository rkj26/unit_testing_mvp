# SEARCH PLAN:
# 1. Boundary: Empty list input must return empty lists as specified.
# 2. Invariant: All factorial sums for a given input must be identical, and the count of sums/permutations must be `len(numbers)!`.
# 3. Structural: Each generated permutation must be a valid rearrangement of the input, and all generated permutations must be unique.
# 4. Error Handling: Input lists containing negative numbers must raise a ValueError.
from candidate import task_func
from hypothesis import given, settings, strategies as st
import math
from collections import Counter

# Helper to check if all elements in an iterable are identical
def all_equal(iterable):
    g = iter(iterable)
    try:
        first = next(g)
    except StopIteration:
        return True
    return all(first == x for x in g)

@settings(max_examples=50, deadline=None)
@given(numbers=st.just([]))
def test_empty_list_returns_empty(numbers):
    """
    SPEC BASIS: "If an empty list is given, the function returns empty lists."
    PROPERTY: For an empty input list, the function must return a tuple of two empty lists.
    STRATEGY: Directly targets the empty list boundary condition, where an implementation might
              incorrectly return None, raise an error, or return non-empty lists.
    """
    try:
        fac_sums, permutations_list = task_func(numbers)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for empty list: {e}"

    assert fac_sums == [], "Factorial sums list should be empty for empty input."
    assert permutations_list == [], "Permutations list should be empty for empty input."

@settings(max_examples=50, deadline=None)
@given(numbers=st.lists(st.integers(min_value=0, max_value=5), min_size=0, max_size=5))
def test_factorial_sums_are_consistent_and_correct_length(numbers):
    """
    SPEC BASIS: "Generate all permutations of a given list of numbers and calculate the sum
                 of the factorials of each number in each permutation."
                "Returns: list of int: A list containing the sums of the factorials of each number
                 in each permutation."
                "list of list of int: A list containing all permutations of numbers."
    PROPERTY: All calculated factorial sums must be identical for a given input list,
              and the number of sums must match the number of permutations, which must be
              `len(numbers)!`.
    STRATEGY: Generates lists of small non-negative integers (including 0 and 1, and duplicates).
              This targets cases where sums might differ across permutations (e.g., due to
              incorrect factorial calculation or permutation generation logic) or where the
              count of permutations/sums is incorrect (off-by-one errors, missing permutations).
    """
    try:
        fac_sums, permutations_list = task_func(numbers)
    except Exception:
        fac_sums, permutations_list = None, None # Turn crash into failed assert

    assert fac_sums is not None and permutations_list is not None, \
        f"task_func raised an unexpected exception for input: {numbers}"

    expected_num_permutations = math.factorial(len(numbers))

    assert len(fac_sums) == expected_num_permutations, \
        f"Expected {expected_num_permutations} factorial sums, got {len(fac_sums)} for input {numbers}."
    assert len(permutations_list) == expected_num_permutations, \
        f"Expected {expected_num_permutations} permutations, got {len(permutations_list)} for input {numbers}."
    assert len(fac_sums) == len(permutations_list), \
        f"Length of factorial sums ({len(fac_sums)}) does not match length of permutations ({len(permutations_list)}) for input {numbers}."

    if numbers: # Only check consistency if there are permutations to sum
        assert all_equal(fac_sums), \
            f"Not all factorial sums are identical for input {numbers}. Sums: {fac_sums}"

@settings(max_examples=50, deadline=None)
@given(numbers=st.lists(st.integers(min_value=0, max_value=5), min_size=0, max_size=5))
def test_permutations_are_valid_and_unique(numbers):
    """
    SPEC BASIS: "Generate all permutations of a given list of numbers."
                "Returns: list of list of int: A list containing all permutations of numbers."
    PROPERTY: Each generated permutation must be a valid permutation of the original input
              (i.e., contain the same elements with the same counts), and all generated
              permutations must be unique.
    STRATEGY: Generates lists of small non-negative integers, including duplicates. This targets
              implementations that might generate incorrect permutations (e.g., missing or extra
              elements, wrong element counts) or fail to generate all unique permutations.
              Using Counter ensures order-agnostic comparison for permutation validity.
    """
    try:
        _, permutations_list = task_func(numbers)
    except Exception:
        permutations_list = None # Turn crash into failed assert

    assert permutations_list is not None, \
        f"task_func raised an unexpected exception for input: {numbers}"

    # Check if each permutation is valid (contains the same elements as the original list)
    original_counts = Counter(numbers)
    for p in permutations_list:
        assert isinstance(p, tuple), \
            f"Permutation element {p} is not a tuple as per example for input {numbers}."
        assert Counter(p) == original_counts, \
            f"Permutation {p} is not a valid permutation of {numbers}."

    # Check if all permutations are unique
    assert len(permutations_list) == len(set(permutations_list)), \
        f"Duplicate permutations found for input {numbers}. Permutations: {permutations_list}"

@settings(max_examples=50, deadline=None)
@given(numbers=st.lists(st.integers(min_value=-5, max_value=5), min_size=1, max_size=5)
          .filter(lambda l: any(n < 0 for n in l)))
def test_raises_value_error_for_negative_numbers(numbers):
    """
    SPEC BASIS: "Raises: ValueError: If input numbers are negative."
    PROPERTY: Calling task_func with a list containing any negative number must raise ValueError.
    STRATEGY: Generates lists that are guaranteed to contain at least one negative integer.
              This directly tests the specified error handling for negative inputs.
    """
    with_negative = False
    for n in numbers:
        if n < 0:
            with_negative = True
            break
    assert with_negative, "Strategy failed to generate a list with negative numbers."

    try:
        task_func(numbers)
        assert False, f"ValueError was not raised for input with negative numbers: {numbers}"
    except ValueError:
        pass # Expected exception
    except Exception as e:
        assert False, f"Expected ValueError but got {type(e).__name__} for input: {numbers}"