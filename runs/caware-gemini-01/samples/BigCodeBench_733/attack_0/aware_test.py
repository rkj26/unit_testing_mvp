from candidate import task_func
from hypothesis import given, settings, strategies as st
import string
import re

# Define a strategy for words that are not stopwords, for easier testing
# The STOPWORDS set is internal to task_func, so we'll approximate it for strategy generation.
# This is a simplified list for strategy generation, not a re-implementation of the STOPWORDS.
_APPROX_STOPWORDS = set([
    "i", "me", "my", "you", "he", "she", "it", "they", "we", "an", "the", "and", "but", "or", "is", "are", "was", "were", "to", "from", "in", "out", "on", "off", "for", "with"
])

# Strategy for non-stop words (simplified for generation)
st_non_stop_word = st.text(
    alphabet=string.ascii_lowercase, min_size=2, max_size=8
).filter(lambda s: s not in _APPROX_STOPWORDS and s not in string.punctuation)

# Strategy for stop words (simplified for generation)
st_stop_word = st.sampled_from(list(_APPROX_STOPWORDS))

# Strategy for any word (simplified for generation)
st_any_word = st.text(
    alphabet=string.ascii_lowercase, min_size=1, max_size=8
).filter(lambda s: s not in string.punctuation)

@st.composite
def sentence_strategy(draw, min_words=1, max_words=10):
    words = draw(st.lists(st_any_word, min_size=min_words, max_size=max_words))
    # Introduce varying amounts of whitespace
    separators = draw(st.lists(st.text(alphabet=' ', min_size=1, max_size=5), min_size=len(words) - 1, max_size=len(words) - 1))
    
    if not words:
        return ""
    
    content_parts = []
    for i, word in enumerate(words):
        content_parts.append(word)
        if i < len(words) - 1:
            content_parts.append(separators[i])
    
    # Add optional leading/trailing spaces
    leading_spaces = draw(st.text(alphabet=' ', min_size=0, max_size=3))
    trailing_spaces = draw(st.text(alphabet=' ', min_size=0, max_size=3))
    
    return leading_spaces + "".join(content_parts) + trailing_spaces

@st.composite
def sentence_with_punctuation_strategy(draw, min_words=1, max_words=10):
    words = draw(st.lists(st_any_word, min_size=min_words, max_size=max_words))
    
    # Add punctuation to words
    punctuated_words = []
    for word in words:
        if draw(st.booleans()): # Sometimes add leading punctuation
            word = draw(st.sampled_from(string.punctuation)) + word
        if draw(st.booleans()): # Sometimes add trailing punctuation
            word = word + draw(st.sampled_from(string.punctuation))
        punctuated_words.append(word)

    # Introduce varying amounts of whitespace
    separators = draw(st.lists(st.text(alphabet=' ', min_size=1, max_size=5), min_size=len(punctuated_words) - 1, max_size=len(punctuated_words) - 1))
    
    if not punctuated_words:
        return ""
    
    content_parts = []
    for i, word in enumerate(punctuated_words):
        content_parts.append(word)
        if i < len(punctuated_words) - 1:
            content_parts.append(separators[i])
    
    # Add optional leading/trailing spaces
    leading_spaces = draw(st.text(alphabet=' ', min_size=0, max_size=3))
    trailing_spaces = draw(st.text(alphabet=' ', min_size=0, max_size=3))
    
    return leading_spaces + "".join(content_parts) + trailing_spaces


@settings(max_examples=50, deadline=None)
@given(content=sentence_strategy(min_words=2))
def test_whitespace_invariance_for_multi_word_sentences(content):
    """
    SPEC BASIS: The example `task_func('this is an example content')` returns 1.
    PROPERTY: The count of non-stopwords should be invariant to the amount of whitespace between words,
              as long as the sequence of actual words (non-space characters) remains the same.
              This targets the `content.split(' ')` and `' '.join(content)` interaction.
    """
    # Canonicalize the input by splitting by any whitespace and rejoining with single spaces
    # This represents the "intended" sequence of words for comparison.
    canonical_words = [word for word in re.split(r'\s+', content) if word]
    if not canonical_words: # Handle cases where content is only whitespace
        canonical_content = ""
    else:
        # The problem states "without the last word". If canonical_words has only one word,
        # the effective content for processing should be empty.
        # If canonical_words has multiple words, the last one is removed.
        if len(canonical_words) > 1:
            canonical_content = ' '.join(canonical_words[:-1])
        else: # If 0 or 1 canonical word, the effective content for processing is empty
            canonical_content = ''

    # Calculate expected result using a robust splitting method for the canonical content
    # This is a reference calculation, not a re-implementation of the full algorithm.
    # It uses the same logic for word processing (strip punctuation, lower, check stopwords)
    # but assumes a robust initial tokenization.
    STOPWORDS = set([
        "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your",
        "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she",
        "her", "hers", "herself", "it", "its", "itself", "they", "them", "their",
        "theirs", "themselves", "what", "which", "who", "whom", "this", "that",
        "these", "those", "is", "are", "was", "were", "be", "been", "being", "have",
        "has", "had", "having", "do", "does", "did", "doing", "an", "the", "and",
        "but", "if", "or", "because", "as", "until", "while", "of", "at", "by",
        "for", "with", "about", "against", "between", "into", "through", "during",
        "before", "after", "above", "below", "to", "from", "up", "down", "in", "out",
        "on", "off", "over", "under", "again", "further", "then", "once"
    ])
    
    expected_words = [word.strip(string.punctuation).lower() for word in re.split(r'\W+', canonical_content) if word]
    expected_non_stopwords = {word for word in expected_words if word not in STOPWORDS}
    expected_count = len(expected_non_stopwords)

    try:
        result = task_func(content)
    except Exception:
        result = None

    assert result is not None, f"task_func raised an exception for input: '{content}'"
    assert result == expected_count, f"Input: '{content}', Expected: {expected_count}, Got: {result}"


@settings(max_examples=50, deadline=None)
@given(word=st_any_word)
def test_single_word_sentence_returns_zero(word):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
    PROPERTY: If the sentence contains only one word (after stripping whitespace),
              the count of non-stopwords should be 0, because the "last word" is removed,
              leaving no words to count. This targets the `if len(content) > 1: content = content[:-1] else: content = []` branch.
    """
    content = word
    try:
        result = task_func(content)
    except Exception:
        result = None

    assert result is not None, f"task_func raised an exception for input: '{content}'"
    assert result == 0, f"Input: '{content}', Expected: 0, Got: {result}"

@settings(max_examples=50, deadline=None)
@given(content=st.text(alphabet=' ', min_size=0, max_size=10))
def test_empty_or_whitespace_only_sentence_returns_zero(content):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
    PROPERTY: An empty string or a string consisting only of whitespace should result in a count of 0.
              This targets the initial `content.split(' ')` and subsequent `len(content)` check.
    """
    try:
        result = task_func(content)
    except Exception:
        result = None

    assert result is not None, f"task_func raised an exception for input: '{content}'"
    assert result == 0, f"Input: '{content}', Expected: 0, Got: {result}"

@settings(max_examples=50, deadline=None)
@given(content=sentence_with_punctuation_strategy(min_words=2))
def test_punctuation_handling_invariance(content):
    """
    SPEC BASIS: The example `task_func('this is an example content')` returns 1.
                The problem implies standard word tokenization.
    PROPERTY: Punctuation attached to words should be correctly stripped before stopword checking.
              The count should be the same as if the punctuation was not present.
    STRATEGY: Generate sentences where words may have leading or trailing punctuation.
              Compare the result to a canonical version where punctuation is removed from words.
    """
    # Canonicalize by removing punctuation and normalizing spaces
    canonical_words_raw = [word for word in re.split(r'\s+', content) if word]
    canonical_words_cleaned = [word.strip(string.punctuation) for word in canonical_words_raw]
    
    if not canonical_words_cleaned:
        canonical_content_for_expected = ""
    elif len(canonical_words_cleaned) > 1:
        canonical_content_for_expected = ' '.join(canonical_words_cleaned[:-1])
    else:
        canonical_content_for_expected = ''

    STOPWORDS = set([
        "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your",
        "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she",
        "her", "hers", "herself", "it", "its", "itself", "they", "them", "their",
        "theirs", "themselves", "what", "which", "who", "whom", "this", "that",
        "these", "those", "is", "are", "was", "were", "be", "been", "being", "have",
        "has", "had", "having", "do", "does", "did", "doing", "an", "the", "and",
        "but", "if", "or", "because", "as", "until", "while", "of", "at", "by",
        "for", "with", "about", "against", "between", "into", "through", "during",
        "before", "after", "above", "below", "to", "from", "up", "down", "in", "out",
        "on", "off", "over", "under", "again", "further", "then", "once"
    ])
    
    expected_words = [word.strip(string.punctuation).lower() for word in re.split(r'\W+', canonical_content_for_expected) if word]
    expected_non_stopwords = {word for word in expected_words if word not in STOPWORDS}
    expected_count = len(expected_non_stopwords)

    try:
        result = task_func(content)
    except Exception:
        result = None

    assert result is not None, f"task_func raised an exception for input: '{content}'"
    assert result == expected_count, f"Input: '{content}', Expected: {expected_count}, Got: {result}"

@settings(max_examples=50, deadline=None)
@given(
    first_words=st.lists(st_any_word, min_size=1, max_size=5),
    last_word=st_any_word,
    trailing_spaces=st.text(alphabet=' ', min_size=1, max_size=5)
)
def test_last_word_removal_with_trailing_spaces(first_words, last_word, trailing_spaces):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
    PROPERTY: The function should correctly identify and remove the *last actual word*
              (the last non-whitespace token) from the sentence, even when trailing spaces are present.
              The count should reflect the non-stopwords from all words *except* the last actual word.
    STRATEGY: Generate sentences with multiple words and explicit trailing spaces.
              This directly targets the suspicious interaction of `content.split(' ')`
              and `content[:-1]` when trailing spaces cause empty strings at the end of the list.
    """
    # Construct the input content with trailing spaces
    content = ' '.join(first_words + [last_word]) + trailing_spaces

    # Calculate the expected result by manually applying the correct logic:
    # 1. Identify all actual words.
    all_actual_words = [word.strip(string.punctuation).lower() for word in re.split(r'\W+', content) if word]
    
    # 2. Remove the last actual word.
    words_to_process = []
    if len(all_actual_words) > 1:
        words_to_process = all_actual_words[:-1]
    # If 0 or 1 actual word, the list for processing should be empty, resulting in 0 count.

    STOPWORDS = set([
        "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your",
        "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she",
        "her", "hers", "herself", "it", "its", "itself", "they", "them", "their",
        "theirs", "themselves", "what", "which", "who", "whom", "this", "that",
        "these", "those", "is", "are", "was", "were", "be", "been", "being", "have",
        "has", "had", "having", "do", "does", "did", "doing", "an", "the", "and",
        "but", "if", "or", "because", "as", "until", "while", "of", "at", "by",
        "for", "with", "about", "against", "between", "into", "through", "during",
        "before", "after", "above", "below", "to", "from", "up", "down", "in", "out",
        "on", "off", "over", "under", "again", "further", "then", "once"
    ])
    
    expected_non_stopwords = {word for word in words_to_process if word not in STOPWORDS}
    expected_count = len(expected_non_stopwords)

    try:
        result = task_func(content)
    except Exception:
        result = None

    assert result is not None, f"task_func raised an exception for input: '{content}'"
    assert result == expected_count, f"Input: '{content}', Expected: {expected_count}, Got: {result}"