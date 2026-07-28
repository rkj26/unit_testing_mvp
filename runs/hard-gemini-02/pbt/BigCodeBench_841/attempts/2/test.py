# SEARCH PLAN:
# - Missing 'text' field or malformed JSON to test explicit error handling, returning empty dict.
# - Empty/whitespace/punctuation-only 'text' content to test boundary conditions for text processing, returning empty dict.
# - Core word counting logic with mixed case and punctuation to verify total word count invariant and exact counts.
# - Metamorphic relation for case-insensitivity and punctuation removal to ensure robust cleaning.

import re
import json
from collections import Counter
import string
from hypothesis import given, settings, strategies as st

# Import the function under test from the candidate module
from candidate import task_func

# Helper function to clean text for comparison, mimicking task_func's logic
def _clean_and_count_words(text_content):
    if not isinstance(text_content, str):
        return {}
    # Convert to lowercase
    text_content = text_content.lower()
    # Remove punctuation and non-alphanumeric characters (except spaces)
    # The problem states "remove all punctuation and non-alphanumeric characters (except spaces)"
    # string.punctuation covers common punctuation.
    # Let's stick to the problem's hint: "Punctuation is removed using the `string.punctuation` constant."
    # This implies a simple replacement of punctuation characters.
    cleaned_text = text_content
    for char in string.punctuation:
        cleaned_text = cleaned_text.replace(char, ' ')
    # Also remove other non-alphanumeric characters that are not spaces
    # This regex `[^a-z0-9\s]` correctly targets non-alphanumeric characters that are not spaces
    cleaned_text = re.sub(r'[^a-z0-9\s]', '', cleaned_text)

    # Split into words and count
    words = cleaned_text.split()
    return Counter(words)

@settings(max_examples=50, deadline=None)
@given(json_input=st.one_of(
    # Malformed JSON: not a valid JSON string
    st.text(min_size=1, max_len=12, alphabet=string.ascii_letters + string.digits).map(lambda s: s if s.strip() else '{"invalid": "json"}'),
    # Valid JSON but explicitly missing the "text" field
    st.dictionaries(
        keys=st.text(min_size=1, max_len=5, alphabet=string.ascii_lowercase).filter(lambda k: k != "text"),
        values=st.text(max_len=5),
        min_size=1, max_size=3
    ).map(json.dumps)
))
def test_empty_dict_on_missing_or_malformed_json(json_input):
    """
    SPEC BASIS: "If the 'text' field is missing, returns an empty dictionary." and "If the JSON string is malformed or the 'text' field is missing, an empty dictionary is returned."
    PROPERTY: The function returns an empty dictionary `{}`.
    STRATEGY: Generate JSON strings that are either malformed (e.g., not valid JSON) or valid JSON but explicitly missing the "text" key.
    """
    try:
        result = task_func(json_input)
    except Exception:
        result = None # Catch any exception as a failure to return empty dict
    assert result == {}, f"Expected empty dict for input: {json_input}, got {result}"

@settings(max_examples=50, deadline=None)
@given(text_content=st.text(
    alphabet=string.ascii_letters + string.digits + string.punctuation + ' ',
    min_size=0, max_len=12
))
def test_total_word_count_and_exact_counts(text_content):
    """
    SPEC BASIS: "counting the frequency of each word."
    PROPERTY: The sum of all word frequencies in the output dictionary must equal the total number of words obtained by manually cleaning and splitting the input text. Also, the exact word counts must match.
    STRATEGY: Generate JSON strings with varied text content, including punctuation, mixed case, and spaces, to test the core processing logic.
    """
    json_input = json.dumps({"text": text_content})
    try:
        result = task_func(json_input)
    except Exception:
        result = None
    assert result is not None, f"task_func raised an exception for input: {json_input}"

    expected_counts = _clean_and_count_words(text_content)
    assert sum(result.values()) == sum(expected_counts.values()), \
        f"Total word count mismatch for input: '{text_content}'. Expected sum {sum(expected_counts.values())}, got {sum(result.values())}. Result: {result}"
    assert Counter(result) == expected_counts, \
        f"Word counts mismatch for input: '{text_content}'. Expected {expected_counts}, got {result}"


@settings(max_examples=50, deadline=None)
@given(text_content=st.one_of(
    st.just(""), # Empty string
    st.text(alphabet=' ', min_size=1, max_len=12), # Only spaces
    st.text(alphabet=string.punctuation, min_size=1, max_len=12), # Only punctuation
    st.text(alphabet=' ' + string.punctuation, min_size=1, max_len=12) # Spaces and punctuation
))
def test_empty_dict_for_empty_or_only_non_word_text(text_content):
    """
    SPEC BASIS: "If the 'text' field is missing, returns an empty dictionary." (This implies that if the 'text' field is present but contains no actual words after cleaning, it should also return an empty dictionary).
    PROPERTY: If the "text" field contains an empty string, or only spaces, or only punctuation, the returned dictionary should be empty.
    STRATEGY: Generate JSON strings where the "text" field is an empty string, or contains only spaces, or only punctuation, or a mix of both.
    """
    json_input = json.dumps({"text": text_content})
    try:
        result = task_func(json_input)
    except Exception:
        result = None
    assert result == {}, f"Expected empty dict for input: '{text_content}', got {result}"


@settings(max_examples=50, deadline=None)
@given(
    words=st.lists(st.text(alphabet=string.ascii_letters + string.digits, min_size=1, max_len=5), min_size=1, max_size=5),
    punctuation_a=st.text(alphabet=string.punctuation, min_size=0, max_len=3),
    punctuation_b=st.text(alphabet=string.punctuation, min_size=0, max_len=3),
    space_a=st.text(alphabet=' ', min_size=0, max_len=3),
    space_b=st.text(alphabet=' ', min_size=0, max_len=3),
    case_choices=st.lists(st.sampled_from(['lower', 'upper', 'title', 'original']), min_size=1, max_size=5)
)
def test_case_and_punctuation_invariance_metamorphic(words, punctuation_a, punctuation_b, space_a, space_b, case_choices):
    """
    SPEC BASIS: "converting it to lowercase, removing all punctuation and non-alphanumeric characters (except spaces), and then counting the frequency of each word." and "The function is case-insensitive and treats words like 'Hello' and 'hello' as the same word."
    PROPERTY: Adding or changing punctuation, or altering the case of words, should not change the final word counts.
    STRATEGY: Generate a list of base words. Construct two different text strings by applying different casing, punctuation, and spacing variations to these same base words. The word counts from both texts should be identical.
    """
    # Ensure case_choices list matches the number of words
    case_choices = (case_choices * ((len(words) // len(case_choices)) + 1))[:len(words)]

    def apply_case(word, choice):
        if choice == 'lower': return word.lower()
        if choice == 'upper': return word.upper()
        if choice == 'title': return word.title()
        return word # 'original' or any other

    # Construct text_a with one set of variations
    text_a_parts = []
    for i, word in enumerate(words):
        text_a_parts.append(punctuation_a + apply_case(word, case_choices[i]) + punctuation_a)
        if i < len(words) - 1:
            text_a_parts.append(space_a)
    text_a = "".join(text_a_parts)

    # Construct text_b with a different set of variations (different punctuation, spaces, potentially different casing)
    text_b_parts = []
    for i, word in enumerate(words):
        # For text_b, we can use a different case choice or just ensure it's different from text_a's presentation
        # For simplicity, let's just use a different punctuation and space, and potentially a different case choice
        # The core idea is that the underlying "words" are the same.
        text_b_parts.append(punctuation_b + apply_case(word, case_choices[i]) + punctuation_b) # Re-use case_choices for simplicity, or generate new ones
        if i < len(words) - 1:
            text_b_parts.append(space_b)
    text_b = "".join(text_b_parts)

    json_a = json.dumps({"text": text_a})
    json_b = json.dumps({"text": text_b})

    try:
        result_a = task_func(json_a)
        result_b = task_func(json_b)
    except Exception:
        result_a = None
        result_b = None

    assert result_a is not None and result_b is not None, \
        f"task_func raised an exception for text_a: '{text_a}' or text_b: '{text_b}'"

    assert result_a == result_b, \
        f"Metamorphic property failed: Text A '{text_a}' resulted in {result_a}, " \
        f"but Text B '{text_b}' resulted in {result_b}. Expected them to be equal."