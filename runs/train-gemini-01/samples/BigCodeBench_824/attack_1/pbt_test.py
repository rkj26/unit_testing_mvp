# SEARCH PLAN:
# 1. Boundary Cases: Test with empty strings, strings of only spaces, or only punctuation to catch off-by-one errors.
# 2. Punctuation Count Invariant: Verify the punctuation count is exact, regardless of surrounding words or spaces.
# 3. Word Count Invariant: Verify word count handles various separators (multiple spaces, leading/trailing spaces, numbers as words).
# 4. Metamorphic Relation: Adding non-punctuation characters should not change the punctuation count.

import re
import string
from hypothesis import given, settings, strategies as st
from candidate import task_func

# Constants from the problem description
PUNCTUATION = string.punctuation

@settings(max_examples=50, deadline=None)
@given(text=st.one_of(
    st.just(""),
    st.text(st.just(" "), min_size=1, max_size=12),
    st.text(st.sampled_from(PUNCTUATION), min_size=1, max_size=12)
))
def test_boundary_cases(text):
    """
    SPEC BASIS: "Count the number of words and punctuation marks in a string."
    PROPERTY: For empty strings, strings of only spaces, or strings of only punctuation,
              the counts should be predictable (0 words for all, N punctuation for only punctuation).
    STRATEGY: Target empty string, strings with only spaces, and strings with only punctuation.
              These are common sources of off-by-one errors or incorrect initializations.
    """
    try:
        words, punc = task_func(text)
    except Exception:
        words, punc = None, None

    assert words is not None and punc is not None, f"task_func crashed for input: '{text}'"

    if text == "":
        assert words == 0
        assert punc == 0
    elif all(c == ' ' for c in text):
        assert words == 0
        assert punc == 0
    elif all(c in PUNCTUATION for c in text):
        assert words == 0
        assert punc == len(text)
    else:
        # This branch should not be hit by the current strategy, but as a fallback
        # it ensures no unexpected behavior if strategy changes.
        pass


@settings(max_examples=50, deadline=None)
@given(text=st.text(st.characters(min_codepoint=1, max_codepoint=127), min_size=0, max_size=12))
def test_punctuation_count_accuracy(text):
    """
    SPEC BASIS: "Count the number of words and punctuation marks in a string."
    PROPERTY: The second element of the returned tuple (punctuation count) must exactly
              match the number of characters from `string.punctuation` present in the input string.
    STRATEGY: Generate arbitrary strings of varying content. The punctuation count is a direct
              summation, making it a robust oracle for this part of the output.
    """
    try:
        _, punc_count = task_func(text)
    except Exception:
        punc_count = None

    assert punc_count is not None, f"task_func crashed for input: '{text}'"

    expected_punc_count = sum(1 for char in text if char in PUNCTUATION)
    assert punc_count == expected_punc_count, \
        f"Punctuation count mismatch for '{text}': Expected {expected_punc_count}, Got {punc_count}"


@settings(max_examples=50, deadline=None)
@given(text=st.text(
    st.one_of(
        st.sampled_from(string.ascii_letters + string.digits),
        st.just(" "),
        st.sampled_from(PUNCTUATION)
    ),
    min_size=0, max_size=12
))
def test_word_count_accuracy_with_varied_separators(text):
    """
    SPEC BASIS: "Count the number of words and punctuation marks in a string."
    PROPERTY: The first element of the returned tuple (word count) must be correct,
              handling multiple spaces, leading/trailing spaces, and numbers as words.
              The example `(6, 3)` for `"Hello, world! This is a test."` implies
              words are sequences of alphanumeric characters.
    STRATEGY: Generate strings with a mix of letters, digits, spaces, and punctuation.
              Use `re.findall(r'\b\w+\b', text)` as a robust oracle for word counting,
              which aligns with the example's interpretation of "word".
    """
    try:
        word_count, _ = task_func(text)
    except Exception:
        word_count = None

    assert word_count is not None, f"task_func crashed for input: '{text}'"

    # The problem's example "Hello, world! This is a test." -> (6, 3)
    # implies that "Hello", "world", "This", "is", "a", "test" are words.
    # This matches `re.findall(r'\b\w+\b', text)` behavior.
    expected_words = re.findall(r'\b\w+\b', text)
    expected_word_count = len(expected_words)

    assert word_count == expected_word_count, \
        f"Word count mismatch for '{text}': Expected {expected_word_count} (from {expected_words}), Got {word_count}"


@settings(max_examples=50, deadline=None)
@given(
    base_text=st.text(st.characters(min_codepoint=1, max_codepoint=127), min_size=0, max_size=6),
    insert_text=st.text(
        st.characters(blacklist_characters=PUNCTUATION),
        min_size=0, max_size=6
    ),
    insert_pos=st.integers(min_value=0, max_value=6) # Max position for base_text of size 6
)
def test_metamorphic_punctuation_invariance(base_text, insert_text, insert_pos):
    """
    SPEC BASIS: "Count the number of words and punctuation marks in a string."
    PROPERTY: Inserting non-punctuation characters into a string should not change
              the total count of punctuation marks.
    STRATEGY: Generate a base string and a second string containing only non-punctuation
              characters (letters, digits, spaces, etc.). Insert the second string into
              the first. The punctuation count of the modified string should be identical
              to the original string's punctuation count. This tests for unintended side
              effects or incorrect character classification.
    """
    # Ensure insert_pos is valid for base_text length
    insert_pos = min(insert_pos, len(base_text))

    original_text = base_text
    modified_text = original_text[:insert_pos] + insert_text + original_text[insert_pos:]

    try:
        _, original_punc_count = task_func(original_text)
        _, modified_punc_count = task_func(modified_text)
    except Exception:
        original_punc_count, modified_punc_count = None, None

    assert original_punc_count is not None and modified_punc_count is not None, \
        f"task_func crashed for original: '{original_text}' or modified: '{modified_text}'"

    assert original_punc_count == modified_punc_count, \
        f"Punctuation count changed after inserting non-punctuation characters. " \
        f"Original: '{original_text}' (Punc: {original_punc_count}), " \
        f"Inserted: '{insert_text}', Modified: '{modified_text}' (Punc: {modified_punc_count})"