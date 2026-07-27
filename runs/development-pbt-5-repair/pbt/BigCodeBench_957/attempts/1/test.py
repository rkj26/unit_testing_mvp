import string
import re
from candidate import task_func
from hypothesis import given, settings, strategies as st

@given(text=st.just('Hello, world!'))
@settings(max_examples=50, deadline=None)
def test_example_one(text):
    """
    SPEC BASIS: Example: >>> task_func('Hello, world!') (2, 10, 7)
    PROPERTY: The function returns the exact expected output for the first provided example.
    """
    assert task_func(text) == (2, 10, 7)

@given(text=st.just('Python is  awesome!  '))
@settings(max_examples=50, deadline=None)
def test_example_two(text):
    """
    SPEC BASIS: Example: >>> task_func('Python is  awesome!  ') (3, 15, 12)
    PROPERTY: The function returns the exact expected output for the second provided example.
    """
    assert task_func(text) == (3, 15, 12)

@given(
    text=st.text(
        st.one_of(
            st.sampled_from(string.ascii_letters + string.digits),
            st.just(' '),
            st.sampled_from(string.punctuation)
        ),
        min_size=0, max_size=12
    )
)
@settings(max_examples=50, deadline=None)
def test_character_and_unique_character_counts_invariant(text):
    """
    SPEC BASIS: "When counting characters, this function excludes whitespace and special characters (i.e. string.punctuation)."
                "Counts the number of words, characters, and unique characters in a given text."
    PROPERTY: The number of unique characters is always less than or equal to the total number of counted characters.
              Also, the total number of counted characters matches the count of alphanumeric characters in the input.
    """
    num_words, num_chars, num_unique_chars = task_func(text)

    # Calculate expected num_chars and num_unique_chars based on definition
    expected_counted_chars = []
    for char in text:
        if char.isalnum() and char not in string.whitespace and char not in string.punctuation:
            expected_counted_chars.append(char)
    
    expected_num_chars = len(expected_counted_chars)
    expected_num_unique_chars = len(set(expected_counted_chars))

    assert num_chars == expected_num_chars
    assert num_unique_chars == expected_num_unique_chars
    assert num_unique_chars <= num_chars

@given(
    text=st.text(
        st.one_of(
            st.sampled_from(string.ascii_letters + string.digits),
            st.just(' '),
            st.sampled_from(string.punctuation)
        ),
        min_size=0, max_size=10
    )
)
@settings(max_examples=50, deadline=None)
def test_leading_trailing_whitespace_punctuation_invariance(text):
    """
    SPEC BASIS: "This function considers whitespace-separated substrings as words."
                "When counting characters, this function excludes whitespace and special characters (i.e. string.punctuation)."
    PROPERTY: Adding leading/trailing whitespace or punctuation to the text should not change the word, character,
              or unique character counts.
    """
    original_result = task_func(text)

    # Add leading/trailing whitespace
    text_with_ws = f"  \t{text}\n "
    result_with_ws = task_func(text_with_ws)
    assert result_with_ws == original_result, f"Whitespace changed result for '{text}'"

    # Add leading/trailing punctuation
    text_with_punct = f".,!{text}?!."
    result_with_punct = task_func(text_with_punct)
    assert result_with_punct == original_result, f"Punctuation changed result for '{text}'"

    # Add both
    text_with_both = f" \t.,!{text}?!.\n "
    result_with_both = task_func(text_with_both)
    assert result_with_both == original_result, f"Both changed result for '{text}'"

@given(
    text=st.text(
        st.one_of(st.just(' '), st.sampled_from(string.punctuation)),
        min_size=0, max_size=12
    )
)
@settings(max_examples=50, deadline=None)
def test_only_whitespace_or_punctuation(text):
    """
    SPEC BASIS: "This function considers whitespace-separated substrings as words."
                "When counting characters, this function excludes whitespace and special characters (i.e. string.punctuation)."
    PROPERTY: If the input text contains only whitespace and/or punctuation, all counts should be zero.
    """
    num_words, num_chars, num_unique_chars = task_func(text)
    assert num_words == 0
    assert num_chars == 0
    assert num_unique_chars == 0