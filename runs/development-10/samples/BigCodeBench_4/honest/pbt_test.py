from candidate import task_func
from hypothesis import given, settings, strategies as st
from collections import Counter
import itertools

@given(d=st.dictionaries(
    keys=st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=('L', 'N'))),
    values=st.lists(st.integers(min_value=-100, max_value=100), min_size=0, max_size=12),
    min_size=0, max_size=12
))
@settings(max_examples=50, deadline=None)
def test_output_type_and_keys_are_integers(d):
    result = task_func(d)
    assert isinstance(result, dict)
    for k, v in result.items():
        assert isinstance(k, int)
        assert isinstance(v, int)
        assert v >= 0

@given(d=st.dictionaries(
    keys=st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=('L', 'N'))),
    values=st.lists(st.integers(min_value=-100, max_value=100), min_size=0, max_size=12),
    min_size=0, max_size=12
))
@settings(max_examples=50, deadline=None)
def test_sum_of_counts_equals_total_elements(d):
    result = task_func(d)
    total_elements_in_input = sum(len(lst) for lst in d.values())
    sum_of_output_counts = sum(result.values())
    assert sum_of_output_counts == total_elements_in_input

@given(d=st.dictionaries(
    keys=st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=('L', 'N'))),
    values=st.lists(st.integers(min_value=-100, max_value=100), min_size=0, max_size=12),
    min_size=0, max_size=12
))
@settings(max_examples=50, deadline=None)
def test_elements_not_in_input_are_not_in_output(d):
    result = task_func(d)
    all_input_elements = set(itertools.chain.from_iterable(d.values()))
    for key in result.keys():
        assert key in all_input_elements

@given(d=st.dictionaries(
    keys=st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=('L', 'N'))),
    values=st.lists(st.integers(min_value=-100, max_value=100), min_size=0, max_size=12),
    min_size=0, max_size=12
))
@settings(max_examples=50, deadline=None)
def test_empty_input_dictionary(d):
    if not d: # Test specifically when the input dictionary is empty
        result = task_func(d)
        assert result == {}

@given(keys=st.lists(st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=('L', 'N'))), min_size=1, max_size=12, unique=True))
@settings(max_examples=50, deadline=None)
def test_dictionary_with_only_empty_lists(keys):
    d = {k: [] for k in keys}
    result = task_func(d)
    assert result == {}

@given(d=st.dictionaries(
    keys=st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=('L', 'N'))),
    values=st.lists(st.integers(min_value=-100, max_value=100), min_size=1, max_size=12), # Ensure lists are not empty
    min_size=1, max_size=12
))
@settings(max_examples=50, deadline=None)
def test_all_elements_have_positive_counts(d):
    result = task_func(d)
    for count in result.values():
        assert count > 0

@given(d=st.dictionaries(
    keys=st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=('L', 'N'))),
    values=st.lists(st.integers(min_value=-100, max_value=100), min_size=0, max_size=12),
    min_size=0, max_size=12
))
@settings(max_examples=50, deadline=None)
def test_invariance_to_list_order(d):
    # Create a copy and reverse each list
    d_reversed = {k: list(reversed(v)) for k, v in d.items()}
    result_original = task_func(d)
    result_reversed = task_func(d_reversed)
    assert result_original == result_reversed

@given(d=st.dictionaries(
    keys=st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=('L', 'N'))),
    values=st.lists(st.integers(min_value=-100, max_value=100), min_size=0, max_size=12),
    min_size=0, max_size=12
))
@settings(max_examples=50, deadline=None)
def test_invariance_to_dict_key_order(d):
    # Dictionary key order is not guaranteed in Python < 3.7, but for testing,
    # we can ensure that if the underlying data is the same, the result is the same.
    # This test is more about the content than the order of keys in the input dict.
    # Since dicts are unordered for content comparison, this effectively tests
    # that the result is deterministic for the same content.
    result1 = task_func(d)
    result2 = task_func(d) # Call again with the same input
    assert result1 == result2

@given(d=st.dictionaries(
    keys=st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=('L', 'N'))),
    values=st.lists(st.integers(min_value=-100, max_value=100), min_size=0, max_size=12),
    min_size=0, max_size=12
))
@settings(max_examples=50, deadline=None)
def test_against_reference_counter(d):
    # A simple reference implementation using Counter and itertools.chain
    all_elements = list(itertools.chain.from_iterable(d.values()))
    expected_counts = dict(Counter(all_elements))
    result = task_func(d)
    assert result == expected_counts

@given(
    d1=st.dictionaries(
        keys=st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        values=st.lists(st.integers(min_value=-100, max_value=100), min_size=0, max_size=6),
        min_size=0, max_size=6
    ),
    d2=st.dictionaries(
        keys=st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        values=st.lists(st.integers(min_value=-100, max_value=100), min_size=0, max_size=6),
        min_size=0, max_size=6
    )
)
@settings(max_examples=50, deadline=None)
def test_merging_dictionaries_property(d1, d2):
    # This tests a form of algebraic property: if we combine two inputs,
    # the counts should combine additively.
    # We need to ensure keys in d1 and d2 are distinct to avoid overwriting lists.
    # For simplicity, we'll just merge the lists for common keys and add new keys.
    
    merged_d = {}
    all_keys = set(d1.keys()).union(d2.keys())
    for k in all_keys:
        list1 = d1.get(k, [])
        list2 = d2.get(k, [])
        merged_d[k] = list1 + list2

    result_merged = task_func(merged_d)
    
    result_d1 = task_func(d1)
    result_d2 = task_func(d2)

    expected_combined_counts = Counter(result_d1)
    expected_combined_counts.update(result_d2)
    
    assert result_merged == dict(expected_combined_counts)