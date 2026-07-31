from candidate import task_func
from hypothesis import given, settings, strategies as st
import json
import string
import re
from collections import defaultdict

@st.composite
def json_text_strategy(draw):
    """
    STRATEGY: Generates JSON strings with a 'text' field containing various characters,
    including alphanumeric, spaces, punctuation, and other symbols like underscore.
    This targets the character removal logic.
    """
    text_chars = st.text(
        alphabet=string.ascii_letters + string.digits + string.whitespace + string.punctuation + '_-!@#$%^&*()+=',
        min_size=0, max_size=12 # Adjusted max_size to 12
    )
    text_content = draw(text_chars)
    json_data = {'text': text_content}
    return json.dumps(json_data)

@st.composite
def json_text_with_missing_field_strategy(draw):
    """
    STRATEGY: Generates JSON strings that either lack the 'text' field or have it as a non-string.
    This targets the error handling for missing/malformed 'text' field.
    """
    keys = st.text(string.ascii_letters, min_size=1, max_size=5)
    values = st.one_of(st.integers(), st.booleans(), st.lists(st.integers(), max_size=3))
    other_fields = draw(st.dictionaries(keys, values, min_size=0, max_size=3)) # Adjusted max_size to 3

    # Option 1: 'text' field is missing
    if draw(st.booleans()):
        return json.dumps(other_fields)
    # Option 2: 'text' field is present but not a string
    else:
        non_string_value = draw(st.one_of(st.integers(), st.booleans(), st.lists(st.integers(), max_size=3))) # Adjusted max_size to 3
        other_fields['text'] = non_string_value
        return json.dumps(other_fields)

@st.composite
def malformed_json_strategy(draw):
    """
    STRATEGY: Generates malformed JSON strings.
    This targets the `json.JSONDecodeError` handling.
    """
    valid_json_prefix = draw(st.text(string.printable, min_size=0, max_size=10)) # Adjusted max_size to 10
    invalid_suffix = draw(st.text(string.printable, min_size=1, max_size=5)) # Adjusted max_size to 5
    return valid_json_prefix + invalid_suffix + '{' # Ensure it's malformed

@settings(max_examples=50, deadline=None)
@given(json_string=json_text_strategy())
def test_output_words_are_lowercase_and_alphanumeric(json_string):
    """
    SPEC BASIS: "It processes the text by converting it to lowercase, removing all punctuation and non-alphanumeric characters (except spaces)"
                "The function is case-insensitive and treats words like "Hello" and "hello" as the same word."
    PROPERTY: All keys (words) in the returned dictionary must be entirely lowercase and consist only of alphanumeric characters.
    STRATEGY: json_text_strategy, targeting the character removal and lowercasing logic.
    """
    result = None
    try:
        result = task_func(json_string)
    except Exception:
        pass # Allow exceptions, but result will be None

    if result is not None:
        assert isinstance(result, dict)
        for word in result.keys():
            assert word.islower(), f"Word '{word}' is not entirely lowercase."
            assert word.isalnum(), f"Word '{word}' contains non-alphanumeric characters."

@settings(max_examples=50, deadline=None)
@given(json_string=json_text_strategy())
def test_word_counts_are_non_negative(json_string):
    """
    SPEC BASIS: "Returns: - dict: A dictionary with words as keys and their frequency counts as values."
    PROPERTY: All word counts in the returned dictionary must be non-negative integers.
    STRATEGY: json_text_strategy, targeting the word counting logic.
    """
    result = None
    try:
        result = task_func(json_string)
    except Exception:
        pass

    if result is not None:
        assert isinstance(result, dict)
        for count in result.values():
            assert isinstance(count, int), f"Count '{count}' is not an integer."
            assert count >= 0, f"Count '{count}' is negative."

@settings(max_examples=50, deadline=None)
@given(json_string=json_text_with_missing_field_strategy())
def test_missing_text_field_returns_empty_dict(json_string):
    """
    SPEC BASIS: "If the "text" field is missing, returns an empty dictionary."
                "If the JSON string is malformed or the "text" field is missing, an empty dictionary is returned."
    PROPERTY: If the 'text' field is missing or not a string, the function should return an empty dictionary.
    STRATEGY: json_text_with_missing_field_strategy, targeting the handling of missing/malformed 'text' field.
    """
    result = None
    try:
        result = task_func(json_string)
    except Exception:
        pass

    assert result == {}, f"Expected empty dict for missing/non-string 'text' field, got {result}"

@settings(max_examples=50, deadline=None)
@given(json_string=malformed_json_strategy())
def test_malformed_json_returns_empty_dict(json_string):
    """
    SPEC BASIS: "If the JSON string is malformed or the "text" field is missing, an empty dictionary is returned."
    PROPERTY: If the input JSON string is malformed, the function should return an empty dictionary.
    STRATEGY: malformed_json_strategy, targeting the `json.JSONDecodeError` handling.
    """
    result = None
    try:
        result = task_func(json_string)
    except Exception:
        pass

    assert result == {}, f"Expected empty dict for malformed JSON, got {result}"

@settings(max_examples=50, deadline=None)
@given(text_content=st.text(
    alphabet=string.ascii_letters + string.digits + string.whitespace + string.punctuation + '_',
    min_size=0, max_size=12 # Adjusted max_size to 12
))
def test_consistent_word_counting_after_comprehensive_cleaning(text_content):
    """
    SPEC BASIS: "remove all punctuation and non-alphanumeric characters (except spaces)"
                "Punctuation is removed using the `string.punctuation` constant."
    PROPERTY: The word counts should be consistent with a single, comprehensive cleaning step that removes
              all non-alphanumeric characters (except spaces) and converts to lowercase. This targets the
              potential redundancy or subtle interaction between the regex and translate calls.
    STRATEGY: Generates text with various characters, including those covered by both regex and string.punctuation,
              to check the combined effect of `re.sub` and `str.translate`.
    """
    json_string = json.dumps({"text": text_content})

    result = None
    try:
        result = task_func(json_string)
    except Exception:
        pass

    if result is not None:
        # Manually process the text to derive the expected words, mimicking the spec's intent
        # The spec implies a single cleaning goal: "removing all punctuation and non-alphanumeric characters (except spaces)".
        # This can be achieved by removing anything that is NOT alphanumeric or space.
        cleaned_text = re.sub(r'[^\sa-zA-Z0-9]', '', text_content).lower().strip()
        
        expected_word_counts = defaultdict(int)
        for word in cleaned_text.split():
            expected_word_counts[word] += 1
        
        assert result == dict(expected_word_counts), \
            f"Word counts mismatch for text: '{text_content}'\n" \
            f"Expected: {dict(expected_word_counts)}\n" \
            f"Got: {result}"