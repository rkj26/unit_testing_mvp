# SEARCH PLAN:
# - The explicit example provided in the problem description.
# - Boundary case: sentences with a single word, where that word is always the last and thus excluded.
# - Boundary case: sentences with two words, testing the exclusion of the last word.
# - Boundary case: empty strings or strings containing only non-word characters.
# - Metamorphic property: adding a known stop word vs. a known non-stop word (not as the last word) to a base sentence.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import string

# Based on the example: task_func('this is an example content') == 1
# 'this', 'is', 'an' appear to be stop words.
# 'example' appears to be a non-stop word.
# 'content' is the last word and excluded.
KNOWN_STOP_WORDS = st.sampled_from(['this', 'is', 'an', 'the', 'a', 'and'])
KNOWN_NON_STOP_WORDS = st.sampled_from(['example', 'apple', 'banana', 'computer', 'python'])
ALL_KNOWN_WORDS = st.one_of(KNOWN_STOP_WORDS, KNOWN_NON_STOP_WORDS)

# Strategy for generating general words (not necessarily stop/non-stop)
# Keep words short to avoid excessively long sentences.
word_strategy = st.text(
    alphabet=string.ascii_lowercase,
    min_size=1,
    max_size=8
)

# Strategy for generating sentences (lists of words)
sentence_words_strategy = st.lists(
    word_strategy,
    min_size=0,
    max_size=10
).map(lambda words: ' '.join(words))

@settings(max_examples=50, deadline=None)
@given(content=st.just('this is an example content'))
def test_example_case(content):
    """
    SPEC BASIS: "Example: >>> task_func('this is an example content')\n1"
    PROPERTY: The function returns the exact count specified in the example.
    STRATEGY: Use the exact example input to ensure the basic functionality matches the specification.
    """
    try:
        result = task_func(content)
    except Exception:
        result = None
    assert result is not None, f"task_func raised an exception for input '{content}'"
    assert result == 1, f"Expected 1 for '{content}', but got {result}"

@settings(max_examples=50, deadline=None)
@given(word=ALL_KNOWN_WORDS)
def test_single_word_sentence_returns_zero(word):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
    PROPERTY: For a sentence with only one word, that word is always the last word and thus excluded.
              Therefore, the count of non-stop words must be 0.
    STRATEGY: Generate sentences consisting of a single word, including both known stop and non-stop words.
    """
    content = word
    try:
        result = task_func(content)
    except Exception:
        result = None
    assert result is not None, f"task_func raised an exception for input '{content}'"
    assert result == 0, f"Expected 0 for single-word sentence '{content}', but got {result}"

@settings(max_examples=50, deadline=None)
@given(first_word=st.one_of(KNOWN_STOP_WORDS, KNOWN_NON_STOP_WORDS),
       second_word=ALL_KNOWN_WORDS)
def test_two_word_sentence_excludes_last(first_word, second_word):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
    PROPERTY: For a two-word sentence, only the first word is considered. The count should be 1 if the first word
              is a non-stop word, and 0 if it's a stop word.
    STRATEGY: Generate two-word sentences, varying the first word between known stop and non-stop words,
              and the second word (which is excluded) arbitrarily.
    """
    content = f"{first_word} {second_word}"
    expected_count = 1 if first_word in KNOWN_NON_STOP_WORDS.example() else 0 # Use .example() to get a representative value for comparison
    try:
        result = task_func(content)
    except Exception:
        result = None
    assert result is not None, f"task_func raised an exception for input '{content}'"
    assert result == expected_count, \
        f"Expected {expected_count} for '{content}' (first word '{first_word}'), but got {result}"

@settings(max_examples=50, deadline=None)
@given(content=st.one_of(
    st.just(''),
    st.text(alphabet=' ', min_size=1, max_size=10),
    st.text(alphabet=string.punctuation, min_size=1, max_size=10),
    st.text(alphabet=string.whitespace + string.punctuation, min_size=1, max_size=10)
))
def test_empty_or_non_word_content_returns_zero(content):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word." (Implicitly, no words means no non-stop words).
    PROPERTY: An empty string or a string containing only whitespace/punctuation should result in a count of 0,
              as there are no actual words to process.
    STRATEGY: Generate empty strings, strings with only whitespace, strings with only punctuation, or combinations.
    """
    try:
        result = task_func(content)
    except Exception:
        result = None
    assert result is not None, f"task_func raised an exception for input '{content}'"
    assert result == 0, f"Expected 0 for content '{content}', but got {result}"

@settings(max_examples=50, deadline=None)
@given(base_sentence_words=st.lists(ALL_KNOWN_WORDS, min_size=2, max_size=10),
       new_word=st.one_of(KNOWN_STOP_WORDS, KNOWN_NON_STOP_WORDS))
def test_adding_word_not_last_metamorphic(base_sentence_words, new_word):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
    PROPERTY: If a word is added to a sentence (not as the last word), the change in count should reflect
              whether the added word is a non-stop word. Adding a stop word should not change the count.
              Adding a non-stop word should increase the count by 1.
    STRATEGY: Take a base sentence, calculate its count. Then, insert a known stop word or a known non-stop word
              at a position other than the last, and check the count change.
    """
    # Ensure the base sentence has at least two words so we can insert without making the new word the last.
    # And also so the original last word is distinct from the inserted word.
    if len(base_sentence_words) < 2:
        base_sentence_words = ['first', 'second'] # Fallback to ensure min_size

    base_content = ' '.join(base_sentence_words)
    try:
        base_count = task_func(base_content)
    except Exception:
        base_count = None
    assert base_count is not None, f"task_func raised an exception for base input '{base_content}'"

    # Insert the new word at a random position, but not as the last word.
    # Since max_size is 10, len(base_sentence_words) is at most 10.
    # We can insert at index 0 up to len(base_sentence_words) - 1.
    insert_index = st.integers(min_value=0, max_value=len(base_sentence_words) - 1).example()
    
    modified_words = list(base_sentence_words)
    modified_words.insert(insert_index, new_word)
    modified_content = ' '.join(modified_words)

    try:
        modified_count = task_func(modified_content)
    except Exception:
        modified_count = None
    assert modified_count is not None, f"task_func raised an exception for modified input '{modified_content}'"

    expected_diff = 1 if new_word in KNOWN_NON_STOP_WORDS.example() else 0
    assert modified_count == base_count + expected_diff, \
        f"Metamorphic failure: Adding '{new_word}' at index {insert_index} to '{base_content}' " \
        f"changed count from {base_count} to {modified_count}. Expected change: {expected_diff}."