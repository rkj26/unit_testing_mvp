from candidate import task_func
from hypothesis import given, settings, strategies as st
import string

# Helper function to calculate expected values based *strictly* on the specification.
# This is not a reference implementation of task_func, but an oracle for properties.
def _calculate_expected(text: str) -> tuple:
    # "This function considers whitespace-separated substrings as words."
    # Python's str.split() without arguments handles multiple spaces and leading/trailing spaces
    # exactly as "whitespace-separated substrings".
    words = text.split()
    num_words = len(words)

    # "When counting characters, this function excludes whitespace and special
    # characters (i.e. string.punctuation)."
    # This implies counting characters that are neither whitespace nor punctuation.
    # The examples confirm case-sensitivity for characters.
    counted_chars = []
    for char in text:
        if not char.isspace() and char not in string.punctuation:
            counted_chars.append(char)
    num_chars = len(counted_chars)

    # "unique characters" - implied to be unique among the 'counted_chars'.
    # Examples confirm this interpretation.
    num_unique_chars = len(set(counted_chars))

    return num_words, num_chars, num_unique_chars

@given(text=st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=127), min_size=0, max_size=12))
@settings(max_examples=50, deadline=None)
def test_return_type_is_tuple_of_three_integers(text: str):
    """
    SPEC BASIS: "Returns: - tuple: A tuple containing three integers"
    PROPERTY: The function returns a tuple of length 3, and all elements are integers.
    """
    result = task_func(text)
    assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
    assert len(result) == 3, f"Expected tuple of length 3, got length {len(result)}"
    assert all(isinstance(x, int) for x in result), f"Expected all elements to be integers, got {result}"

@given(text=st.just('Hello, world!'))
@settings(max_examples=50, deadline=None)
def test_example_hello_world(text: str):
    """
    SPEC BASIS: Example: >>> task_func('Hello, world!') (2, 10, 7)
    PROPERTY: The function returns (2, 10, 7) for the input 'Hello, world!'.
    """
    expected_words, expected_chars, expected_unique_chars = (2, 10, 7)
    num_words, num_chars, num_unique_chars = task_func(text)
    assert num_words == expected_words, f"Expected {expected_words} words, got {num_words}"
    assert num_chars == expected_chars, f"Expected {expected_chars} characters, got {num_chars}"
    assert num_unique_chars == expected_unique_chars, f"Expected {expected_unique_chars} unique characters, got {num_unique_chars}"

@given(text=st.just('Python is  awesome!  '))
@settings(max_examples=50, deadline=None)
def test_example_python_is_awesome(text: str):
    """
    SPEC BASIS: Example: >>> task_func('Python is  awesome!  ') (3, 15, 12)
    PROPERTY: The function returns (3, 15, 12) for the input 'Python is  awesome!  '.
    """
    expected_words, expected_chars, expected_unique_chars = (3, 15, 12)
    num_words, num_chars, num_unique_chars = task_func(text)
    assert num_words == expected_words, f"Expected {expected_words} words, got {num_words}"
    assert num_chars == expected_chars, f"Expected {expected_chars} characters, got {num_chars}"
    assert num_unique_chars == expected_unique_chars, f"Expected {expected_unique_chars} unique characters, got {num_unique_chars}"

@given(text=st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=127), min_size=0, max_size=12))
@settings(max_examples=50, deadline=None)
def test_num_words_is_non_negative(text: str):
    """
    SPEC BASIS: "Counts the number of words..." (counts are non-negative)
    PROPERTY: The number of words is always non-negative.
    """
    num_words, _, _ = task_func(text)
    assert num_words >= 0, f"Expected non-negative word count, got {num_words}"

@given(text=st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=127), min_size=0, max_size=12))
@settings(max_examples=50, deadline=None)
def test_num_chars_is_non_negative(text: str):
    """
    SPEC BASIS: "Counts the number of characters..." (counts are non-negative)
    PROPERTY: The number of characters is always non-negative.
    """
    _, num_chars, _ = task_func(text)
    assert num_chars >= 0, f"Expected non-negative character count, got {num_chars}"

@given(text=st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=127), min_size=0, max_size=12))
@settings(max_examples=50, deadline=None)
def test_num_unique_chars_is_non_negative(text: str):
    """
    SPEC BASIS: "Counts the number of unique characters..." (counts are non-negative)
    PROPERTY: The number of unique characters is always non-negative.
    """
    _, _, num_unique_chars = task_func(text)
    assert num_unique_chars >= 0, f"Expected non-negative unique character count, got {num_unique_chars}"

@given(text=st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=127), min_size=0, max_size=12))
@settings(max_examples=50, deadline=None)
def test_num_unique_chars_less_than_or_equal_to_num_chars(text: str):
    """
    SPEC BASIS: "Counts the number of characters, and unique characters" (unique count cannot exceed total count)
    PROPERTY: The number of unique characters is always less than or equal to the number of characters.
    """
    _, num_chars, num_unique_chars = task_func(text)
    assert num_unique_chars <= num_chars, \
        f"Expected unique characters ({num_unique_chars}) <= total characters ({num_chars})"

@given(text=st.text(alphabet=st.just(' ') | st.sampled_from(string.punctuation), min_size=0, max_size=12))
@settings(max_examples=50, deadline=None)
def test_only_whitespace_or_punctuation_results_in_zero_chars(text: str):
    """
    SPEC BASIS: "When counting characters, this function excludes whitespace and special characters (i.e. string.punctuation)."
    PROPERTY: If the text contains only whitespace and/or punctuation, num_chars and num_unique_chars are 0.
    """
    _, num_chars, num_unique_chars = task_func(text)
    assert num_chars == 0, f"Expected 0 characters for '{text}', got {num_chars}"
    assert num_unique_chars == 0, f"Expected 0 unique characters for '{text}', got {num_unique_chars}"

@given(text=st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=127), min_size=0, max_size=12))
@settings(max_examples=50, deadline=None)
def test_num_words_matches_split_behavior(text: str):
    """
    SPEC BASIS: "This function considers whitespace-separated substrings as words."
    PROPERTY: The number of words matches the count of items from text.split().
    """
    expected_num_words = len(text.split())
    num_words, _, _ = task_func(text)
    assert num_words == expected_num_words, \
        f"Expected {expected_num_words} words for '{text}', got {num_words}"

@given(text=st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=127), min_size=0, max_size=12))
@settings(max_examples=50, deadline=None)
def test_all_counts_match_oracle(text: str):
    """
    SPEC BASIS: "Counts the number of words, characters, and unique characters in a given text."
                Combined with specific definitions for each count and examples.
    PROPERTY: All three counts match the values derived directly from the specification's rules.
    """
    expected_words, expected_chars, expected_unique_chars = _calculate_expected(text)
    num_words, num_chars, num_unique_chars = task_func(text)

    assert num_words == expected_words, \
        f"Words mismatch for '{text}': Expected {expected_words}, Got {num_words}"
    assert num_chars == expected_chars, \
        f"Characters mismatch for '{text}': Expected {expected_chars}, Got {num_chars}"
    assert num_unique_chars == expected_unique_chars, \
        f"Unique characters mismatch for '{text}': Expected {expected_unique_chars}, Got {num_unique_chars}"