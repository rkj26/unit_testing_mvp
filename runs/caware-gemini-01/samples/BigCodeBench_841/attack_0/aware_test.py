from candidate import task_func
from hypothesis import given, settings, strategies as st
import json
import string
import re
from collections import defaultdict

# Helper to create valid JSON strings
@st.composite
def json_text_strategy(draw, text_strategy=st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=127), min_size=0, max_size=10)):
    text_content = draw(text_strategy)
    json_dict = {"text": text_content}
    return json.dumps(json_dict)

@st.composite
def json_text_with_missing_field(draw):
    keys = draw(st.lists(st.text(min_size=1, max_size=5, alphabet=string.ascii_lowercase), min_size=0, max_size=5).map(set).map(list))
    # Ensure 'text' is not in keys
    keys = [k for k in keys if k != 'text']
    
    data = {k: draw(st.text(max_size=5)) for k in keys}
    return json.dumps(data)

@st.composite
def json_malformed_strategy(draw):
    # Generate a string that is not valid JSON
    s = draw(st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=127), min_size=1, max_size=10))
    # Ensure it's not valid JSON by adding a common malformation
    return s + "{" + s # e.g., "abc{abc"

@st.composite
def json_text_with_punctuation_only(draw):
    # Generate text consisting only of punctuation characters
    punctuation_chars = list(string.punctuation)
    text_content = draw(st.text(alphabet=punctuation_chars, min_size=1, max_size=10))
    json_dict = {"text": text_content}
    return json.dumps(json_dict)

@st.composite
def json_text_with_non_alphanumeric_non_punctuation(draw):
    # Generate text consisting of characters that are non-alphanumeric,
    # not whitespace, and not in string.punctuation.
    # Example: currency symbols, mathematical symbols, control characters (excluding whitespace)
    # We'll filter characters to ensure they fit this criteria.
    
    # All printable ASCII characters
    all_printable_ascii = [chr(i) for i in range(32, 127)]
    
    # Characters to exclude: alphanumeric, whitespace, and punctuation
    exclude_chars = set(string.ascii_letters + string.digits + string.whitespace + string.punctuation)
    
    # Filtered alphabet
    filtered_alphabet = [c for c in all_printable_ascii if c not in exclude_chars]
    
    if not filtered_alphabet: # Fallback if no such characters exist in the chosen range
        return json.dumps({"text": ""})

    text_content = draw(st.text(alphabet=filtered_alphabet, min_size=1, max_size=10))
    json_dict = {"text": text_content}
    return json.dumps(json_dict)


@given(json_string=json_text_strategy())
@settings(max_examples=50, deadline=None)
def test_output_is_dict_and_keys_are_lowercase(json_string):
    """
    SPEC BASIS: "Returns: - dict: A dictionary with words as keys and their frequency counts as values."
                "The function is case-insensitive and treats words like "Hello" and "hello" as the same word."
    PROPERTY: The function always returns a dictionary, and all keys (words) in the dictionary are lowercase strings.
    STRATEGY: General valid JSON input.
    """
    try:
        result = task_func(json_string)
        assert isinstance(result, dict)
        for word, count in result.items():
            assert isinstance(word, str)
            assert word.islower()
            assert isinstance(count, int)
            assert count >= 0
    except Exception:
        assert False, f"task_func raised an exception for input: {json_string}"


@given(json_string=json_text_with_missing_field())
@settings(max_examples=50, deadline=None)
def test_missing_text_field_returns_empty_dict(json_string):
    """
    SPEC BASIS: "If the "text" field is missing, returns an empty dictionary."
    PROPERTY: If the input JSON does not contain a "text" field, the function returns an empty dictionary.
    STRATEGY: JSON strings guaranteed not to have a "text" field.
    """
    try:
        result = task_func(json_string)
        assert result == {}
    except Exception:
        assert False, f"task_func raised an exception for input: {json_string}"


@given(json_string=json_malformed_strategy())
@settings(max_examples=50, deadline=None)
def test_malformed_json_returns_empty_dict(json_string):
    """
    SPEC BASIS: "If the JSON string is malformed or the "text" field is missing, an empty dictionary is returned."
    PROPERTY: If the input string is not valid JSON, the function returns an empty dictionary.
    STRATEGY: Malformed JSON strings.
    """
    try:
        result = task_func(json_string)
        assert result == {}
    except Exception:
        assert False, f"task_func raised an exception for input: {json_string}"


@given(json_string=json_text_with_punctuation_only())
@settings(max_examples=50, deadline=None)
def test_punctuation_only_text_results_in_empty_dict(json_string):
    """
    SPEC BASIS: "remove punctuation, and non-alphanumeric characters (except spaces)"
                "Punctuation is removed using the `string.punctuation` constant."
    PROPERTY: If the "text" field contains only punctuation characters (from string.punctuation),
              the resulting word count dictionary should be empty, as all characters should be removed.
    STRATEGY: JSON strings where the 'text' field consists solely of characters from `string.punctuation`.
              This targets the suspicious redundancy of `re.sub` followed by `translate(string.punctuation)`.
    """
    try:
        result = task_func(json_string)
        assert result == {}
    except Exception:
        assert False, f"task_func raised an exception for input: {json_string}"


@given(json_string=json_text_with_non_alphanumeric_non_punctuation())
@settings(max_examples=50, deadline=None)
def test_non_alphanumeric_non_punctuation_chars_are_removed(json_string):
    """
    SPEC BASIS: "remove punctuation, and non-alphanumeric characters (except spaces)"
    PROPERTY: If the "text" field contains only characters that are non-alphanumeric, not whitespace,
              and not in `string.punctuation` (e.g., currency symbols, mathematical symbols),
              the resulting word count dictionary should be empty, as these characters should be removed.
              This confirms the broader scope of the `re.sub` beyond just `string.punctuation`.
    STRATEGY: JSON strings where the 'text' field consists solely of characters that are non-alphanumeric,
              not whitespace, and not in `string.punctuation`.
    """
    try:
        result = task_func(json_string)
        assert result == {}
    except Exception:
        assert False, f"task_func raised an exception for input: {json_string}"