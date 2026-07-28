# SEARCH PLAN:
# 1. Example verification: Directly test the provided example to ensure the most basic case works.
# 2. Last word ignored: Verify that changing only the last word of a sentence does not alter the count, targeting the "without the last word" rule.
# 3. Boundary cases (empty/single/two words): Test sentences with very few words to cover edge conditions for word parsing and the "last word ignored" rule.
# 4. Output type and non-negativity: Ensure the function always returns a non-negative integer for valid inputs.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import re
import string

# Based on the example: task_func('this is an example content') returns 1.
# This implies 'this', 'is', 'an' are stopwords and 'example' is a non-stopword.
# The problem does not define a stopword list, so we must infer a minimal one from the example
# for the purpose of constructing inputs that allow for metamorphic testing.
# Any word not in this set will be considered a non-stopword for test construction.
_STOPWORDS = {'this', 'is', 'an'}

# Strategy for generating words that can be stopwords or non-stopwords
_word_strategy = st.text(string.ascii_lowercase, min_size=1, max_size=7)
_stopword_strategy = st.sampled_from(list(_STOPWORDS))
_non_stopword_strategy = _word_strategy.filter(lambda w: w not in _STOPWORDS)

# Strategy for generating a mix of words, including known stopwords and non-stopwords
_mixed_word_strategy = st.one_of(
    _stopword_strategy,
    _non_stopword_strategy,
    st.text(string.ascii_lowercase, min_size=1, max_size=7)
)

@settings(max_examples=50, deadline=None)
@given(content=st.just('this is an example content'))
def test_example_case(content):
    """
    SPEC BASIS: "Example: >>> task_func('this is an example content')\n1"
    PROPERTY: The function returns 1 for the exact example string.
    STRATEGY: Use st.just for the specific example string provided in the problem description.
    """
    try:
        result = task_func(content)
    except Exception:
        result = None
    assert result is not None, f"task_func raised an exception for input '{content}'"
    assert isinstance(result, int), f"Expected an integer, got {type(result)}"
    assert result == 1, f"Expected 1 for '{content}', got {result}"

@settings(max_examples=50, deadline=None)
@given(
    words_before_last=st.lists(_mixed_word_strategy, min_size=1, max_size=10),
    original_last_word=_mixed_word_strategy,
    new_last_word=_mixed_word_strategy.filter(lambda w: w != original_last_word)
)
def test_last_word_ignored_metamorphic(words_before_last, original_last_word, new_last_word):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
    PROPERTY: Changing only the last word of a sentence does not change the count of non-stopwords.
              This is a metamorphic property verifying the "without the last word" requirement.
    STRATEGY: Generate a sentence with at least two words. Create two versions: one with an original last word,
              and one with a different last word. The counts should be identical.
    """
    # Ensure there's at least one word before the last word to be counted
    if not words_before_last:
        words_before_last = ['dummy'] # Ensure min_size=1 for words_before_last

    content_original = ' '.join(words_before_last + [original_last_word])
    content_modified = ' '.join(words_before_last + [new_last_word])

    try:
        result_original = task_func(content_original)
        result_modified = task_func(content_modified)
    except Exception:
        result_original = None
        result_modified = None

    assert result_original is not None, f"task_func raised an exception for input '{content_original}'"
    assert result_modified is not None, f"task_func raised an exception for input '{content_modified}'"
    assert isinstance(result_original, int) and isinstance(result_modified, int)
    assert result_original == result_modified, \
        f"Changing last word from '{original_last_word}' to '{new_last_word}' changed count. " \
        f"Original: '{content_original}' -> {result_original}, Modified: '{content_modified}' -> {result_modified}"

@settings(max_examples=50, deadline=None)
@given(
    content=st.one_of(
        st.just(''),  # Empty string
        _mixed_word_strategy,  # Single word
        st.text(string.whitespace, min_size=1, max_size=5), # Only whitespace
        st.lists(_mixed_word_strategy, min_size=1, max_size=2).map(lambda x: ' '.join(x)) # One or two words
    )
)
def test_boundary_cases_empty_single_two_words(content):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
    PROPERTY: For sentences with zero or one word, the count should be 0 (as the last word is ignored, or no words exist).
              For sentences with two words, only the first word is considered.
    STRATEGY: Test empty string, string with only whitespace, single-word sentences, and two-word sentences.
    """
    try:
        result = task_func(content)
    except Exception:
        result = None

    assert result is not None, f"task_func raised an exception for input '{content}'"
    assert isinstance(result, int), f"Expected an integer, got {type(result)}"
    assert result >= 0, f"Expected non-negative count, got {result}"

    words = re.findall(r'\b\w+\b', content.lower()) # Simple word tokenization
    if len(words) <= 1:
        assert result == 0, f"Expected 0 for '{content}' (len={len(words)}), got {result}"
    elif len(words) == 2:
        # Only the first word is considered, the second is the 'last word' and ignored.
        expected_count = 1 if words[0] not in _STOPWORDS else 0
        assert result == expected_count, \
            f"Expected {expected_count} for '{content}' (first word '{words[0]}'), got {result}"

@settings(max_examples=50, deadline=None)
@given(
    words=st.lists(_mixed_word_strategy, min_size=0, max_size=12),
    leading_trailing_whitespace=st.text(string.whitespace, min_size=0, max_size=5)
)
def test_output_is_non_negative_integer(words, leading_trailing_whitespace):
    """
    SPEC BASIS: "Returns: - count (int): The count of non-stopwords."
    PROPERTY: The function always returns a non-negative integer.
    STRATEGY: Generate various sentences, including those with leading/trailing whitespace,
              and verify the type and range of the output.
    """
    content = leading_trailing_whitespace + ' '.join(words) + leading_trailing_whitespace
    try:
        result = task_func(content)
    except Exception:
        result = None

    assert result is not None, f"task_func raised an exception for input '{content}'"
    assert isinstance(result, int), f"Expected an integer, got {type(result)} for input '{content}'"
    assert result >= 0, f"Expected non-negative count, got {result} for input '{content}'"