# SEARCH PLAN:
# 1. Empty/Single Element Dictionary: Test boundary conditions for input size (empty, one element).
# 2. Sum of Values Conservation: Verify that the total sum of values is preserved across aggregation, a strong metamorphic property.
# 3. All Keys Same First Character: Target cases where all keys group into a single category, checking aggregation logic.
# 4. Diverse Keys and Values: Include the example, and generate keys with various first characters (ASCII, digits, symbols) and values (positive, negative, zero) to ensure robust grouping and summation.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import string
from collections import defaultdict

@settings(max_examples=50, deadline=None)
@given(my_dict=st.one_of(
    st.just({}),
    st.dictionaries(
        keys=st.text(string.ascii_lowercase, min_size=1, max_size=5),
        values=st.integers(min_value=-100, max_value=100),
        min_size=1, max_size=1
    )
))
def test_empty_and_single_element_dict(my_dict):
    """
    SPEC BASIS: Implicitly, a function should handle empty inputs gracefully. The example shows aggregation.
    PROPERTY: An empty input dictionary results in an empty output. A single-element dictionary results in an
              output with one entry, key being the first char of input key, value being input value.
    STRATEGY: Explicitly generate an empty dictionary and dictionaries with exactly one entry.
              This targets boundary conditions for input size.
    """
    try:
        result = task_func(my_dict)
    except Exception:
        result = None
    
    assert result is not None, f"task_func raised an exception for input: {my_dict}"

    if not my_dict:
        assert result == {}, f"Expected empty dict for empty input, got {result}"
    else:
        # For a single element dict, the output should be {'first_char': value}
        input_key = list(my_dict.keys())[0]
        input_value = my_dict[input_key]
        expected_key = input_key[0]
        assert result == {expected_key: input_value}, \
            f"Expected {{'{expected_key}': {input_value}}} for input {my_dict}, got {result}"

@settings(max_examples=50, deadline=None)
@given(my_dict=st.dictionaries(
    keys=st.text(st.characters(min_codepoint=1, max_codepoint=127), min_size=1, max_size=5),
    values=st.integers(min_value=-100, max_value=100),
    min_size=0, max_size=12
))
def test_sum_of_values_conservation(my_dict):
    """
    SPEC BASIS: "add the values for each group."
    PROPERTY: The sum of all values in the output dictionary must equal the sum of all values in the input dictionary.
              This is a conservation law that must hold regardless of grouping.
    STRATEGY: Generate dictionaries with diverse keys (including non-alphabetic first characters) and values
              (positive, negative, zero) to ensure the aggregation correctly sums all values.
    """
    try:
        result = task_func(my_dict)
    except Exception:
        result = None
    
    assert result is not None, f"task_func raised an exception for input: {my_dict}"

    input_sum = sum(my_dict.values())
    output_sum = sum(result.values())
    assert output_sum == input_sum, \
        f"Sum of output values ({output_sum}) does not match sum of input values ({input_sum}) for input {my_dict}"

@settings(max_examples=50, deadline=None)
@given(
    first_char=st.sampled_from(string.ascii_lowercase + string.digits + '!@#$'), # Include non-alpha first chars
    other_chars=st.text(string.ascii_lowercase + string.digits, min_size=0, max_size=4),
    values=st.lists(st.integers(min_value=-100, max_value=100), min_size=1, max_size=12)
)
def test_all_keys_same_first_char(first_char, other_chars, values):
    """
    SPEC BASIS: "Group the dictionary entries after the first character of the key and add the values for each group."
    PROPERTY: If all keys start with the same character, the output dictionary must contain exactly one entry,
              with that character as the key and the sum of all input values as its value.
    STRATEGY: Construct input dictionaries where all keys are guaranteed to start with the same character.
              This specifically targets the aggregation logic for a single group.
    """
    # Ensure unique keys for the input dictionary
    keys = [first_char + other_chars + str(i) for i in range(len(values))]
    my_dict = dict(zip(keys, values))

    try:
        result = task_func(my_dict)
    except Exception:
        result = None
    
    assert result is not None, f"task_func raised an exception for input: {my_dict}"

    expected_sum = sum(values)
    assert result == {first_char: expected_sum}, \
        f"Expected {{'{first_char}': {expected_sum}}} for input {my_dict}, got {result}"

@settings(max_examples=50, deadline=None)
@given(my_dict=st.one_of(
    st.just({'apple': 1, 'banana': 2, 'avocado': 3, 'blueberry': 4, 'blackberry': 5}),
    st.dictionaries(
        keys=st.text(st.characters(min_codepoint=1, max_codepoint=127), min_size=1, max_size=5),
        values=st.integers(min_value=-100, max_value=100),
        min_size=1, max_size=12
    )
))
def test_example_and_diverse_keys_aggregation(my_dict):
    """
    SPEC BASIS: The provided example: `{'apple': 1, 'banana': 2, 'avocado': 3, 'blueberry': 4, 'blackberry': 5}` -> `{'a': 4, 'b': 11}`.
                "Group the dictionary entries after the first character of the key and add the values for each group."
    PROPERTY: The function produces the correct aggregated dictionary according to the grouping and summation rules.
              This includes handling the explicit example and various valid key types.
    STRATEGY: Include the exact example dictionary. Also, generate dictionaries with keys that might include
              non-ASCII characters, digits, or symbols as their first character, alongside various integer values.
              This tests the core logic against a broad range of valid inputs.
    """
    try:
        result = task_func(my_dict)
    except Exception:
        result = None
    
    assert result is not None, f"task_func raised an exception for input: {my_dict}"

    # Manually compute the expected output for comparison
    expected_output = defaultdict(int)
    for key, value in my_dict.items():
        if key: # Ensure key is not empty, though st.text(min_size=1) prevents this
            expected_output[key[0]] += value
    
    assert result == dict(expected_output), \
        f"Incorrect aggregation for input {my_dict}. Expected {dict(expected_output)}, got {result}"