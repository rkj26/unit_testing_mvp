from candidate import task_func
from hypothesis import given, settings, strategies as st
import json
import string
import re
from collections import defaultdict

@st.composite
def json_text_strategy(draw):
    """
    Strategy for generating JSON strings with a 'text' field.
    Includes various characters to test punctuation and non-alphanumeric removal.
    """
    text_parts = draw(st.lists(
        st.text(
            alphabet=string.ascii_letters + string.digits + string.punctuation + " _-€§",
            min_size=1, max_size=5
        ),
        min_size=1, max_size=5
    ))
    text = " ".join(text_parts)
    return json.dumps({"text": text})

@st.composite
def json_missing_text_strategy(draw):
    """
    Strategy for generating JSON strings that are valid but lack the 'text' field.
    """
    keys = draw(st.lists(st.text(min_size=1, max_size=5, alphabet=string.ascii_letters), min_size=0, max_size=3))
    # Ensure 'text' is not in keys
    keys = [k for k in keys if k != 'text']
    values = draw(st.lists(st.text(min_size=1, max_size=5), min_size=len(keys), max_size=len(keys)))
    data = {k: v for k, v in zip(keys, values)}
    return json.dumps(data)

@st.composite
def malformed_json_strategy(draw):
    """
    Strategy for generating malformed JSON strings.
    """
    return draw(st.text(min_size=1, max_size=12).filter(lambda s: not s.startswith('{') or not s.endswith('}')))

@settings(max_examples=50, deadline=None)
@given(json_input=json_text_strategy())
def test_all_non_alphanumeric_removed(json_input):
    """
    SPEC BASIS: "removing all punctuation and non-alphanumeric characters (except spaces)"
                "Notes: Punctuation is removed using the `string.punctuation` constant."
    PROPERTY: All characters that are not lowercase alphanumeric (a-z, 0-9) should be removed from words.
              This includes characters in `string.punctuation` and other non-alphanumeric symbols like '€' or '§'.
              The final word counts should match those derived solely from the regex cleaning.
    STRATEGY: Targets the interaction and redundancy of `re.sub` and `word.translate` by including various non-alphanumeric characters.
    """
    try:
        result = task_func(json_input)
    except Exception:
        result = None

    assert result is not None, f"task_func raised an exception for input: {json_input}"
    assert isinstance(result, dict), "Result should be a dictionary"

    # Extract original text from JSON to verify processing
    data = json.loads(json_input)
    original_text = data.get('text', '')
    
    # Manually process the text as per the expected behavior (regex-driven cleaning, which is the dominant one)
    expected_counts = defaultdict(int)
    for token in original_text.lower().strip().split():
        cleaned_word = re.sub(r'[^a-z0-9]', '', token)
        if cleaned_word: # Only add non-empty words
            expected_counts[cleaned_word] += 1

    # Check that all keys in the result are purely alphanumeric
    for word in result.keys():
        assert word.isalnum() or word == '', f"Word '{word}' contains non-alphanumeric characters after processing."

    # Check that the counts are consistent with the regex-driven cleaning, confirming the redundancy of the translate step.
    assert result == dict(expected_counts), f"Word counts do not match expected regex-cleaned output for input: {json_input}"


@settings(max_examples=50, deadline=None)
@given(json_input=json_missing_text_strategy())
def test_missing_text_field_returns_empty_dict(json_input):
    """
    SPEC BASIS: "If the "text" field is missing, returns an empty dictionary."
                "If the JSON string is malformed or the "text" field is missing, an empty dictionary is returned."
    PROPERTY: If the input JSON is valid but lacks a "text" field, an empty dictionary is returned.
    STRATEGY: Generates valid JSON strings that explicitly do not contain a "text" field.
    """
    try:
        result = task_func(json_input)
    except Exception:
        result = None

    assert result == {}, f"Expected empty dict for missing 'text' field, got {result} for input: {json_input}"


@settings(max_examples=50, deadline=None)
@given(json_input=malformed_json_strategy())
def test_malformed_json_returns_empty_dict(json_input):
    """
    SPEC BASIS: "If the JSON string is malformed or the "text" field is missing, an empty dictionary is returned."
    PROPERTY: If the input JSON string is malformed, an empty dictionary is returned.
    STRATEGY: Generates various malformed JSON strings.
    """
    try:
        result = task_func(json_input)
    except Exception:
        result = None

    assert result == {}, f"Expected empty dict for malformed JSON, got {result} for input: {json_input}"


@settings(max_examples=50, deadline=None)
@given(text_content=st.text(alphabet=string.ascii_letters + string.digits + " ", min_size=0, max_size=10))
def test_case_insensitivity(text_content):
    """
    SPEC BASIS: "The function is case-insensitive and treats words like "Hello" and "hello" as the same word."
    PROPERTY: Words with different casing but identical alphanumeric content should be counted as the same word.
    STRATEGY: Generates text with mixed casing and verifies that the counts reflect case-insensitivity.
    """
    # Create a JSON string with mixed-case versions of the same words
    words = text_content.split()
    if not words:
        json_input = json.dumps({"text": ""})
    else:
        mixed_case_words = []
        for i, word in enumerate(words):
            if i % 2 == 0:
                mixed_case_words.append(word.lower())
            else:
                mixed_case_words.append(word.upper())
        json_input = json.dumps({"text": " ".join(mixed_case_words)})

    try:
        result = task_func(json_input)
    except Exception:
        result = None

    assert result is not None, f"task_func raised an exception for input: {json_input}"
    
    # All keys in the result should be lowercase
    for word in result.keys():
        assert word == word.lower(), f"Word '{word}' is not lowercase in the result."

    # Verify counts by comparing with a fully lowercased version
    expected_counts = defaultdict(int)
    for word in words:
        cleaned_word = re.sub(r'[^a-z0-9]', '', word.lower()) # Apply the same cleaning logic
        if cleaned_word:
            expected_counts[cleaned_word] += 1
    
    assert result == dict(expected_counts), f"Case-insensitivity failed for input: {json_input}"