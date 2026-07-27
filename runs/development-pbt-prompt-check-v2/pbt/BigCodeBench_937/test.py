from candidate import task_func
from hypothesis import given, settings, strategies as st
from collections import Counter
import re

# Helper oracle function, derived directly from the unambiguous specification.
# This oracle is used to verify the correctness of the task_func's output
# based on the explicit rules for filtering and case-insensitivity.
def _reference_oracle(input_str):
    """
    Reference implementation based on the problem specification:
    - Remove non-alphanumeric characters.
    - Convert remaining characters to lowercase.
    - Count frequencies.
    """
    # "removing all non-alphanumeric characters"
    # Using re.sub to remove anything that is NOT alphanumeric.
    filtered_str = re.sub(r'[^a-zA-Z0-9]', '', input_str)
    
    # "treating uppercase and lowercase letters as the same."
    # "characters as keys (all lowercase)"
    lower_str = filtered_str.lower()
    
    # "Count the frequency of each alphanumeric character"
    return Counter(lower_str)

@given(input_str=st.text(
    alphabet=st.characters(min_codepoint=1, max_codepoint=127, blacklist_categories=('Cs',)),
    min_size=0, max_size=12
))
@settings(max_examples=50, deadline=None)
def test_output_is_dict(input_str: str):
    """
    SPEC BASIS: "Returns: - dict"
    PROPERTY: The return value must be an instance of dict.
    """
    result = task_func(input_str)
    assert isinstance(result, dict)

@given(input_str=st.text(
    alphabet=st.characters(min_codepoint=1, max_codepoint=127, blacklist_categories=('Cs',)),
    min_size=0, max_size=12
))
@settings(max_examples=50, deadline=None)
def test_all_keys_are_lowercase(input_str: str):
    """
    SPEC BASIS: "characters as keys (all lowercase)"
    PROPERTY: All keys in the returned dictionary must be lowercase strings.
    """
    result = task_func(input_str)
    for key in result.keys():
        assert isinstance(key, str)
        assert key.islower() or not key # Empty string key is not expected for alphanumeric chars, but handles edge cases.

@given(input_str=st.text(
    alphabet=st.characters(min_codepoint=1, max_codepoint=127, blacklist_categories=('Cs',)),
    min_size=0, max_size=12
))
@settings(max_examples=50, deadline=None)
def test_all_values_are_non_negative_integers(input_str: str):
    """
    SPEC BASIS: "frequencies in the input string as values"
    PROPERTY: All values in the returned dictionary must be non-negative integers.
    """
    result = task_func(input_str)
    for value in result.values():
        assert isinstance(value, int)
        assert value >= 0

@given(input_str=st.text(
    alphabet=st.characters(min_codepoint=1, max_codepoint=127, blacklist_categories=('Cs',)),
    min_size=0, max_size=12
))
@settings(max_examples=50, deadline=None)
def test_only_alphanumeric_keys_present(input_str: str):
    """
    SPEC BASIS: "after removing all non-alphanumeric characters"
    PROPERTY: All keys in the returned dictionary must be alphanumeric characters.
    """
    result = task_func(input_str)
    for key in result.keys():
        assert key.isalnum()

@given(input_str=st.text(
    alphabet=st.characters(min_codepoint=1, max_codepoint=127, blacklist_categories=('Cs',)),
    min_size=0, max_size=12
))
@settings(max_examples=50, deadline=None)
def test_output_matches_reference_oracle(input_str: str):
    """
    SPEC BASIS: "Count the frequency of each alphanumeric character in a given string after removing all non-alphanumeric characters, treating uppercase and lowercase letters as the same."
    PROPERTY: The output dictionary must exactly match the result of the unambiguous reference oracle.
    """
    expected = _reference_oracle(input_str)
    actual = task_func(input_str)
    assert actual == expected

@given(input_str=st.just("Hello, World!"))
@settings(max_examples=50, deadline=None)
def test_example_case_exact_match(input_str: str):
    """
    SPEC BASIS: `task_func("Hello, World!")` returns `Counter({'l': 3, 'o': 2, 'h': 1, 'e': 1, 'w': 1, 'r': 1, 'd': 1})`
    PROPERTY: The function output for the specific example input must exactly match the example output.
    """
    expected_output = Counter({'l': 3, 'o': 2, 'h': 1, 'e': 1, 'w': 1, 'r': 1, 'd': 1})
    actual_output = task_func(input_str)
    assert actual_output == expected_output

@given(input_str=st.just(""))
@settings(max_examples=50, deadline=None)
def test_empty_string_input(input_str: str):
    """
    SPEC BASIS: "Count the frequency of each alphanumeric character..." (implies an empty string should result in an empty count)
    PROPERTY: An empty input string should result in an empty dictionary.
    """
    expected = Counter()
    actual = task_func(input_str)
    assert actual == expected

@given(input_str=st.just("!@#$%^&*()"))
@settings(max_examples=50, deadline=None)
def test_only_special_characters_input(input_str: str):
    """
    SPEC BASIS: "after removing all non-alphanumeric characters"
    PROPERTY: An input string containing only non-alphanumeric characters should result in an empty dictionary.
    """
    expected = Counter()
    actual = task_func(input_str)
    assert actual == expected

@given(input_str=st.just("123 ABC def"))
@settings(max_examples=50, deadline=None)
def test_mixed_case_and_numbers_input(input_str: str):
    """
    SPEC BASIS: "treating uppercase and lowercase letters as the same." and "Count the frequency of each alphanumeric character"
    PROPERTY: The function correctly counts mixed case letters and numbers, treating letters case-insensitively.
    """
    # "123 ABC def" -> "123ABCdef" -> "123abcdef" -> Counter({'1': 1, '2': 1, '3': 1, 'a': 1, 'b': 1, 'c': 1, 'd': 1, 'e': 1, 'f': 1})
    expected = Counter({'1': 1, '2': 1, '3': 1, 'a': 1, 'b': 1, 'c': 1, 'd': 1, 'e': 1, 'f': 1})
    actual = task_func(input_str)
    assert actual == expected

@given(input_str=st.just("AaBbCc1122"))
@settings(max_examples=50, deadline=None)
def test_repeated_mixed_case_and_numbers(input_str: str):
    """
    SPEC BASIS: "treating uppercase and lowercase letters as the same." and "Count the frequency of each alphanumeric character"
    PROPERTY: The function correctly aggregates counts for repeated characters regardless of case.
    """
    # "AaBbCc1122" -> "aabbcc1122" -> Counter({'a': 2, 'b': 2, 'c': 2, '1': 2, '2': 2})
    expected = Counter({'a': 2, 'b': 2, 'c': 2, '1': 2, '2': 2})
    actual = task_func(input_str)
    assert actual == expected