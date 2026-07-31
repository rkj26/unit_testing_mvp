# SEARCH PLAN:
# 1. Core functionality: Test basic word counting, lowercasing, and punctuation removal with varied text, comparing against a reference.
# 2. Punctuation/Non-alphanumeric removal: Verify all specified characters are removed using a metamorphic property, including edge cases beyond string.punctuation.
# 3. Empty/Missing/Malformed inputs: Ensure empty dict is returned for missing 'text', empty 'text', non-string 'text', or malformed JSON.
# 4. Whitespace handling: Check that various whitespace patterns (multiple spaces, tabs, newlines, leading/trailing) are normalized.
# 5. Case-insensitivity: Verify words with different casing are counted as the same word, using a custom oracle.

import re
import json
from collections import defaultdict
import string
from hypothesis import given, settings, strategies as st
from candidate import task_func

# Helper function to simulate the expected cleaning and counting for oracle/metamorphic tests
def _clean_and_count(text_content):
    # Per spec, if "text" field is missing or malformed, empty dict is returned.
    # This helper assumes text_content is the value of the "text" field.
    # If it's not a string, it's considered malformed for processing purposes.
    if not isinstance(text_content, str):
        return {}
    
    # Convert to lowercase
    text = text_content.lower()
    
    # Remove punctuation and non-alphanumeric characters (except spaces)
    # The spec says "remove all punctuation and non-alphanumeric characters (except spaces)".
    # This implies keeping only a-z, 0-9, and spaces.
    # string.punctuation covers many, but not all, non-alphanumeric characters.
    # A robust interpretation is to keep only alphanumeric ASCII and spaces.
    cleaned_text = re.sub(r'[^a-z0-9\s]', '', text)
    
    # Split into words and count frequency
    # .split() handles multiple spaces, leading/trailing spaces correctly.
    words = cleaned_text.split()
    
    word_counts = defaultdict(int)
    for word in words:
        word_counts[word] += 1
    return dict(word_counts)

@settings(max_examples=50, deadline=None)
@given(text_content=st.text(
    alphabet=st.one_of(
        st.characters(whitelist_categories=('L', 'N', 'P', 'Z')), # Letters, Numbers, Punctuation, Separators (spaces)
        st.just(' '), st.just('\t'), st.just('\n'), # Explicitly add common whitespace
        st.sampled_from(string.punctuation) # Ensure all standard punctuation is covered
    ),
    min_size=0, max_size=100 # Keep text content reasonably sized
).map(lambda s: s.strip())) # Strip leading/trailing whitespace for cleaner test cases
def test_core_functionality_and_example_like_inputs(text_content):
    """
    SPEC BASIS: "Process a JSON string containing a "text" field: convert to lowercase, remove punctuation, and count word frequency."
                "Example: {'hello': 2, 'world': 2, 'universe': 2, 'meet': 1}"
    PROPERTY: The output dictionary correctly reflects word counts after lowercasing and punctuation removal.
    STRATEGY: Generate JSON strings with varied text: mixed case, common punctuation, multiple words, some repeated,
              including digits as part of words. Compare against a simple reference implementation.
    """
    json_input = json.dumps({"text": text_content})
    
    try:
        result = task_func(json_input)
    except Exception:
        result = None
    
    assert result is not None, f"task_func raised an exception for valid input: {json_input}"
    
    expected_result = _clean_and_count(text_content)
    assert result == expected_result, f"Input: '{text_content}', Expected: {expected_result}, Got: {result}"


@settings(max_examples=50, deadline=None)
@given(
    base_words=st.lists(st.text(string.ascii_lowercase + string.digits, min_size=1, max_size=5), min_size=0, max_size=5),
    punctuation_chars=st.lists(st.sampled_from(string.punctuation + '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~' + '©™®€£¥'), min_size=0, max_size=10),
    whitespace_chars=st.lists(st.sampled_from([' ', '\t', '\n']), min_size=0, max_size=5)
)
def test_punctuation_and_non_alphanumeric_removal(base_words, punctuation_chars, whitespace_chars):
    """
    SPEC BASIS: "removing all punctuation and non-alphanumeric characters (except spaces)"
                "Punctuation is removed using the `string.punctuation` constant."
    PROPERTY: Adding punctuation or non-alphanumeric characters (that are not spaces) to a word,
              or between words, does not change the word counts of the actual alphanumeric words.
    STRATEGY: Construct a base text from alphanumeric words. Then, create a "noisy" version by
              interspersing various punctuation and non-alphanumeric symbols (including those
              beyond `string.punctuation` like copyright symbols) and extra whitespace.
              The word counts of the noisy version should match the clean version.
    """
    # Create a clean base text
    clean_text = " ".join(base_words)
    
    # Create a noisy text by inserting punctuation and other non-alphanumeric chars
    noisy_text_parts = []
    for i, word in enumerate(base_words):
        noisy_text_parts.append(word)
        if i < len(base_words) - 1:
            # Insert random punctuation and whitespace between words
            noisy_text_parts.append("".join(punctuation_chars[:len(punctuation_chars)//2]))
            noisy_text_parts.append("".join(whitespace_chars))
    
    # Add more noise at the beginning and end, and within words
    final_noisy_text = "".join(punctuation_chars[len(punctuation_chars)//2:]) + \
                       "".join(noisy_text_parts) + \
                       "".join(punctuation_chars[:len(punctuation_chars)//2])
    
    # Insert some punctuation/non-alphanumeric characters inside words
    if base_words:
        idx = len(final_noisy_text) // 2
        final_noisy_text = final_noisy_text[:idx] + "".join(punctuation_chars) + final_noisy_text[idx:]

    json_clean = json.dumps({"text": clean_text})
    json_noisy = json.dumps({"text": final_noisy_text})

    try:
        result_clean = task_func(json_clean)
        result_noisy = task_func(json_noisy)
    except Exception:
        result_clean = None
        result_noisy = None
    
    assert result_clean is not None, f"task_func raised for clean input: {clean_text}"
    assert result_noisy is not None, f"task_func raised for noisy input: {final_noisy_text}"
    
    assert result_noisy == result_clean, \
        f"Punctuation/non-alphanumeric removal failed.\n" \
        f"Clean text: '{clean_text}' -> {result_clean}\n" \
        f"Noisy text: '{final_noisy_text}' -> {result_noisy}"


@settings(max_examples=50, deadline=None)
@given(
    json_data=st.one_of(
        st.just({}), # Empty JSON object
        st.dictionaries(st.text(min_size=1, max_size=5), st.text(min_size=1, max_size=5), min_size=1, max_size=3)
          .filter(lambda d: "text" not in d), # JSON without "text" field
        st.builds(lambda x: {"text": x}, st.just("")), # JSON with empty "text" field
        st.builds(lambda x: {"text": x}, st.none()), # JSON with "text": null
        st.builds(lambda x: {"text": x}, st.integers()), # JSON with "text": 123 (non-string)
        st.builds(lambda x: {"text": x}, st.lists(st.text(min_size=1, max_size=5), min_size=0, max_size=12)), # JSON with "text": ["word"] (non-string)
        st.just("not a json string"), # Malformed JSON string
        st.just(""), # Empty string (malformed JSON)
        st.just("{"), # Incomplete JSON string
    ).map(lambda d: json.dumps(d) if isinstance(d, dict) else d)
)
def test_empty_missing_malformed_inputs(json_data):
    """
    SPEC BASIS: "If the "text" field is missing, returns an empty dictionary."
                "If the JSON string is malformed or the "text" field is missing, an empty dictionary is returned."
    PROPERTY: Returns `{}` for these specific invalid/edge-case inputs.
    STRATEGY: Generate JSON strings that are malformed, or valid JSON but with a missing "text" field,
              an empty "text" field, or a "text" field that is not a string.
    """
    try:
        result = task_func(json_data)
    except Exception:
        result = {} # Per spec, malformed JSON should return empty dict, so catch and normalize
    
    assert result == {}, f"Input: '{json_data}', Expected: {{}}, Got: {result}"


@settings(max_examples=50, deadline=None)
@given(
    words=st.lists(st.text(string.ascii_letters + string.digits, min_size=1, max_size=5), min_size=0, max_size=5),
    whitespace_strategy=st.lists(st.sampled_from([' ', '\t', '\n']), min_size=1, max_size=3)
)
def test_whitespace_handling_and_word_splitting(words, whitespace_strategy):
    """
    SPEC BASIS: "counting the frequency of each word." (implies words are split by whitespace).
                "remove all punctuation and non-alphanumeric characters (except spaces)".
    PROPERTY: Multiple spaces, leading/trailing spaces, and different whitespace characters (tabs, newlines)
              are correctly normalized to single word separators, and do not create empty word keys.
    STRATEGY: Generate text with various whitespace patterns (multiple spaces, tabs, newlines, leading/trailing spaces)
              between alphanumeric words. The word counts should match those from a simply space-separated version.
    """
    # Create a base text with words separated by single spaces
    clean_text = " ".join(words)
    
    # Create a text with varied whitespace
    whitespace_separator = "".join(whitespace_strategy)
    noisy_text = whitespace_separator.join(words)
    
    # Add leading/trailing whitespace
    noisy_text = whitespace_separator + noisy_text + whitespace_separator

    json_clean = json.dumps({"text": clean_text})
    json_noisy = json.dumps({"text": noisy_text})

    try:
        result_clean = task_func(json_clean)
        result_noisy = task_func(json_noisy)
    except Exception:
        result_clean = None
        result_noisy = None
    
    assert result_clean is not None, f"task_func raised for clean input: {clean_text}"
    assert result_noisy is not None, f"task_func raised for noisy input: {noisy_text}"
    
    assert result_noisy == result_clean, \
        f"Whitespace handling failed.\n" \
        f"Clean text: '{clean_text}' -> {result_clean}\n" \
        f"Noisy text: '{noisy_text}' -> {result_noisy}"


@settings(max_examples=50, deadline=None)
@given(
    words_and_cases=st.lists(
        st.text(string.ascii_letters, min_size=1, max_size=5).map(
            lambda s: st.sampled_from([s.lower(), s.upper(), s.capitalize()]).example()
        ),
        min_size=0, max_size=5
    )
)
def test_case_insensitivity(words_and_cases):
    """
    SPEC BASIS: "The function is case-insensitive and treats words like "Hello" and "hello" as the same word."
    PROPERTY: Words with different casing are counted as the same word (lowercase).
    STRATEGY: Generate text containing the same base words but with varying casing (e.g., "word", "Word", "WORD").
              The final counts for the lowercase versions should be the sum of all their case variations.
    """
    text_content = " ".join(words_and_cases)
    json_input = json.dumps({"text": text_content})

    try:
        result = task_func(json_input)
    except Exception:
        result = None
    
    assert result is not None, f"task_func raised an exception for valid input: {json_input}"

    # Manually calculate expected result to verify case-insensitivity
    expected_counts = defaultdict(int)
    for word in words_and_cases:
        # Simulate cleaning for individual words to match _clean_and_count's behavior
        cleaned_word = re.sub(r'[^a-z0-9]', '', word.lower())
        if cleaned_word: # Only count if it's not empty after cleaning
            expected_counts[cleaned_word] += 1
    
    assert result == dict(expected_counts), \
        f"Case-insensitivity failed.\n" \
        f"Input text: '{text_content}'\n" \
        f"Expected: {dict(expected_counts)}\n" \
        f"Got: {result}"