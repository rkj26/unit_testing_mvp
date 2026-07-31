# SEARCH PLAN:
# 1. Example Replication: Directly test the provided example to ensure the core logic works as specified.
# 2. Missing/Malformed JSON: Target inputs where the "text" field is absent or the JSON is invalid, expecting an empty dictionary.
# 3. Punctuation and Case Handling: Generate text with mixed case, various punctuation, and special characters, ensuring they are correctly removed/normalized and word counts are accurate.
# 4. Empty/Whitespace-only Text: Focus on inputs where the "text" field is present but contains no actual words (empty string, only spaces, only punctuation), expecting an empty dictionary.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import string
import json
from collections import Counter

@settings(max_examples=50, deadline=None)
@given(
    json_input=st.just('{"text": "Hello world! Hello universe. World, meet universe."}')
)
def test_example_case(json_input):
    """
    SPEC BASIS: "Example: >>> json_input = '{"text": "Hello world! Hello universe. World, meet universe."}' >>> task_func(json_input) {'hello': 2, 'world': 2, 'universe': 2, 'meet': 1}"
    PROPERTY: The function output exactly matches the provided example's expected output.
    STRATEGY: Use st.just to provide the exact example input string.
    """
    try:
        result = task_func(json_input)
    except Exception:
        result = None
    
    assert result is not None
    expected_output = {'hello': 2, 'world': 2, 'universe': 2, 'meet': 1}
    assert result == expected_output

@settings(max_examples=50, deadline=None)
@given(
    json_string=st.one_of(
        st.just('{}'),  # Empty JSON object
        st.just('{"other_field": "some value"}'),  # JSON without "text" field
        st.builds(
            lambda s: json.dumps({"other_field": s}),
            st.text(min_size=0, max_size=10, alphabet=string.ascii_letters + string.digits)
        ), # JSON with other fields, but no "text"
        st.text(min_size=1, max_size=12, alphabet=string.printable).filter(
            lambda s: not s.strip().startswith('{') or not s.strip().endswith('}')
        ) # Malformed JSON (not starting/ending with braces)
    )
)
def test_missing_text_field_or_malformed_json(json_string):
    """
    SPEC BASIS: "If the 'text' field is missing, returns an empty dictionary."
                "If the JSON string is malformed or the 'text' field is missing, an empty dictionary is returned."
    PROPERTY: For inputs where the "text" field is absent or the JSON is malformed, an empty dictionary is returned.
    STRATEGY: Generate JSON strings that are either empty, contain other fields but no "text", or are syntactically malformed.
    """
    try:
        result = task_func(json_string)
    except Exception:
        result = None
    
    assert result is not None
    assert result == {}

@settings(max_examples=50, deadline=None)
@given(
    words=st.lists(
        st.text(
            min_size=1,
            max_size=5,
            alphabet=string.ascii_letters
        ),
        min_size=0,
        max_size=5
    ),
    punctuation_chars=st.lists(
        st.sampled_from(string.punctuation + string.whitespace + string.digits + '!@#$%^&*()'),
        min_size=0,
        max_size=5
    )
)
def test_case_insensitivity_and_punctuation_removal(words, punctuation_chars):
    """
    SPEC BASIS: "The function is case-insensitive and treats words like "Hello" and "hello" as the same word."
                "Punctuation is removed using the `string.punctuation` constant."
                "remove punctuation, and count word frequency."
    PROPERTY: Words are counted case-insensitively, and punctuation/non-alphanumeric characters (except spaces) are ignored.
    STRATEGY: Construct text by interspersing words (with random casing) and various punctuation/special characters.
              Verify that the resulting counts only contain lowercase words and match the expected frequencies.
    """
    # Create a text string with mixed case words and various punctuation
    text_parts = []
    expected_counts = Counter()
    for i, word in enumerate(words):
        # Randomly change case of the word
        cased_word = "".join(c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(word))
        text_parts.append(cased_word)
        expected_counts[word.lower()] += 1
        
        # Add some punctuation or spaces between words
        if i < len(words) - 1:
            text_parts.append("".join(punctuation_chars))
            text_parts.append(" ") # Ensure spaces are present for word separation

    # Add leading/trailing punctuation/spaces
    full_text = "".join(punctuation_chars) + " ".join(text_parts) + "".join(punctuation_chars)
    
    json_string = json.dumps({"text": full_text})

    try:
        result = task_func(json_string)
    except Exception:
        result = None
    
    assert result is not None
    assert result == expected_counts

@settings(max_examples=50, deadline=None)
@given(
    text_content=st.one_of(
        st.just(""),  # Empty string
        st.text(min_size=1, max_size=12, alphabet=string.whitespace), # Only whitespace
        st.text(min_size=1, max_size=12, alphabet=string.punctuation), # Only punctuation
        st.text(min_size=1, max_size=12, alphabet=string.whitespace + string.punctuation) # Mix of whitespace and punctuation
    )
)
def test_empty_or_non_word_text_content(text_content):
    """
    SPEC BASIS: "remove punctuation and non-alphanumeric characters (except spaces), and then counting the frequency of each word."
                (Implicitly, if no words remain after processing, the count should be empty.)
    PROPERTY: If the "text" field contains only whitespace, punctuation, or is empty, the function returns an empty dictionary.
    STRATEGY: Generate JSON strings where the "text" field is present but contains no actual alphanumeric words.
    """
    json_string = json.dumps({"text": text_content})
    
    try:
        result = task_func(json_string)
    except Exception:
        result = None
    
    assert result is not None
    assert result == {}