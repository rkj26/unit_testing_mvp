from candidate import task_func
from hypothesis import given, settings, strategies as st
import string
import itertools

@given(d=st.just({'a': [1, 2, 3, 1], 'b': [3, 4, 5], 'c': [1, 2]}))
@settings(max_examples=50, deadline=None)
def test_example_case(d):
    """
    SPEC BASIS: Example: >>> d = {'a': [1, 2, 3, 1], 'b': [3, 4, 5], 'c': [1, 2]}
                >>> count_dict = task_func(d)
                >>> print(count_dict)
                {1: 3, 2: 2, 3: 2, 4: 1, 5: 1}
    PROPERTY: The function correctly processes the provided example input and produces the exact expected output.
    """
    expected_output = {1: 3, 2: 2, 3: 2, 4: 1, 5: 1}
    assert task_func(d) == expected_output

@given(
    d=st.dictionaries(
        st.text(string.ascii_lowercase, min_size=1, max_size=5),
        st.lists(st.integers(min_value=-10, max_value=10), min_size=0, max_size=10),
        min_size=0,
        max_size=5
    )
)
@settings(max_examples=50, deadline=None)
def test_sum_of_counts_equals_total_elements(d):
    """
    SPEC BASIS: "Count the occurrence of each integer in the values of the input dictionary...
                The resulting dictionary's keys are the integers, and the values are their respective counts across all lists in the input dictionary."
    PROPERTY: The sum of all counts in the output dictionary must equal the total number of integers across all input lists.
    """
    result = task_func(d)
    total_elements_in_input = sum(len(lst) for lst in d.values())
    sum_of_output_counts = sum(result.values())
    assert sum_of_output_counts == total_elements_in_input

@given(d=st.just({}))
@settings(max_examples=50, deadline=None)
def test_empty_input_dictionary(d):
    """
    SPEC BASIS: Implied by "Count the occurrence of each integer...". If there are no integers, there are no occurrences.
    PROPERTY: An empty input dictionary `d` should result in an empty output dictionary.
    """
    assert task_func(d) == {}

@given(
    d=st.dictionaries(
        st.text(string.ascii_lowercase, min_size=1, max_size=5),
        st.lists(st.integers(min_value=-10, max_value=10), min_size=0, max_size=0), # Ensures empty lists
        min_size=1, # Ensures the dictionary itself is not empty
        max_size=5
    )
)
@settings(max_examples=50, deadline=None)
def test_input_with_only_empty_lists(d):
    """
    SPEC BASIS: Implied by "Count the occurrence of each integer...". If lists are empty, no integers are present to count.
    PROPERTY: If the input dictionary contains keys mapping to only empty lists, the output dictionary should be empty.
    """
    assert task_func(d) == {}

@given(
    d=st.dictionaries(
        st.text(string.ascii_lowercase, min_size=1, max_size=5),
        st.lists(st.integers(min_value=-10, max_value=10), min_size=0, max_size=10),
        min_size=0,
        max_size=5
    )
)
@settings(max_examples=50, deadline=None)
def test_output_keys_match_unique_input_integers(d):
    """
    SPEC BASIS: "The resulting dictionary's keys are the integers from any of the input lists"
    PROPERTY: The set of keys in the output dictionary must exactly match the set of unique integers present in the input lists.
    """
    result = task_func(d)
    
    # Collect all unique integers from the input dictionary's values
    all_input_integers = list(itertools.chain.from_iterable(d.values()))
    unique_input_integers = set(all_input_integers)

    # The output keys should be exactly these unique integers
    assert set(result.keys()) == unique_input_integers