from candidate import task_func
from hypothesis import given, settings, strategies as st
import string
import re

# Define the STOPWORDS set as it is in the candidate code for reference in tests
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

# Helper to determine if a word is a stopword
def is_stopword(word):
    return word.lower() in STOPWORDS

# Strategy for generating non-stop words
non_stop_word_strategy = st.text(
    alphabet=string.ascii_lowercase, min_size=1, max_size=5
).filter(lambda s: s not in STOPWORDS)

# Strategy for generating stop words
stop_word_strategy = st.sampled_from(list(STOPWORDS))

# Strategy for generating punctuation
punctuation_strategy = st.text(
    alphabet=string.punctuation, min_size=1, max_size=3
)

@given(
    words_before_last=st.lists(non_stop_word_strategy | stop_word_strategy, min_size=0, max_size=5),
    last_word_core=st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=5),
    trailing_punct=punctuation_strategy | st.just(''),
    trailing_spaces=st.text(alphabet=' ', min_size=0, max_size=3),
    separator=st.text(alphabet=' ', min_size=1, max_size=3)
)
@settings(max_examples=50, deadline=None)
def test_last_semantic_word_removal_with_varied_endings(words_before_last, last_word_core, trailing_punct, trailing_spaces, separator):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
    PROPERTY: The count should reflect the non-stopwords *before* the last semantic word,
              regardless of trailing punctuation or spaces which might confuse simple `split(' ')` logic.
    STRATEGY: Targets the `content.split(' ')` and `content = content[:-1]` logic,
              especially when the "last word" is followed by punctuation or multiple spaces.
    """
    last_word_full = f"{last_word_core}{trailing_punct}"
    
    if not words_before_last:
        # If only one semantic word, it should be removed, resulting in 0.
        content = f"{last_word_full}{trailing_spaces}"
        expected_count = 0
    else:
        content = separator.join(words_before_last + [last_word_full]) + trailing_spaces
        
        # Calculate expected count based on words_before_last
        expected_count = sum(1 for word in words_before_last if word not in STOPWORDS)

    try:
        result = task_func(content)
    except Exception:
        result = None

    assert result == expected_count, f"Input: '{content}', Expected: {expected_count}, Got: {result}"


@given(
    words=st.lists(non_stop_word_strategy | stop_word_strategy, min_size=2, max_size=5),
    spaces_between=st.lists(st.text(alphabet=' ', min_size=1, max_size=3), min_size=1, max_size=4),
    leading_punct=punctuation_strategy | st.just(''),
    trailing_punct=punctuation_strategy | st.just('')
)
@settings(max_examples=50, deadline=None)
def test_multiple_words_with_varied_whitespace_and_punctuation(words, spaces_between, leading_punct, trailing_punct):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
    PROPERTY: The count of non-stopwords should be consistent with the number of non-stop words
              in the sentence *before* the last word, regardless of varied whitespace or punctuation.
    STRATEGY: Targets the interaction between `content.split(' ')`, `[:-1]`, and `re.split(r'\W+', ...)`
              with sentences having multiple words and varied spacing/punctuation.
    """
    # Ensure spaces_between has one less element than words for joining
    if len(spaces_between) >= len(words):
        spaces_between = spaces_between[:len(words) - 1]
    else:
        spaces_between.extend([st.just(' ').example() for _ in range(len(words) - 1 - len(spaces_between))])

    # Construct the content string with varied spaces and punctuation
    content_parts = []
    for i, word in enumerate(words):
        content_parts.append(word)
        if i < len(words) - 1:
            content_parts.append(spaces_between[i])
    
    content = f"{leading_punct}{''.join(content_parts)}{trailing_punct}"

    try:
        result = task_func(content)
    except Exception:
        result = None

    # Manually determine the expected count
    # First, tokenize the *original* content to find the semantic words
    original_semantic_words = [
        w.strip(string.punctuation).lower() 
        for w in re.split(r'\W+', content) if w
    ]

    # If there are no semantic words or only one, the count should be 0.
    if len(original_semantic_words) <= 1:
        expected_count = 0
    else:
        # Remove the last semantic word
        words_to_count = original_semantic_words[:-1]
        expected_count = sum(1 for word in words_to_count if word not in STOPWORDS)

    assert result == expected_count, f"Input: '{content}', Expected: {expected_count}, Got: {result}"


@given(
    word=st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=5),
    leading_punct=punctuation_strategy | st.just(''),
    trailing_punct=punctuation_strategy | st.just('')
)
@settings(max_examples=50, deadline=None)
def test_single_word_input(word, leading_punct, trailing_punct):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
    PROPERTY: If the input sentence contains only one semantic word (even with punctuation),
              the count of non-stopwords should be 0, as that single word is the "last word" and is removed.
    STRATEGY: Targets the `if len(content) > 1: ... else: content = []` branch for single-word inputs.
    """
    content = f"{leading_punct}{word}{trailing_punct}"
    
    try:
        result = task_func(content)
    except Exception:
        result = None

    assert result == 0, f"Input: '{content}', Expected: 0, Got: {result}"


@given(
    content=st.text(
        alphabet=string.ascii_letters + string.punctuation + ' ',
        min_size=0, max_size=12
    )
)
@settings(max_examples=50, deadline=None)
def test_empty_or_only_punctuation_input(content):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
    PROPERTY: For inputs that are empty or contain only whitespace/punctuation, the count should be 0.
    STRATEGY: General property for edge cases of input content.
    """
    # Filter to ensure content is effectively empty or only non-word characters
    semantic_words = [w.strip(string.punctuation).lower() for w in re.split(r'\W+', content) if w]
    if semantic_words:
        st.assume(False) # Skip if there are actual words

    try:
        result = task_func(content)
    except Exception:
        result = None

    assert result == 0, f"Input: '{content}', Expected: 0, Got: {result}"


@given(
    words_list=st.lists(non_stop_word_strategy | stop_word_strategy, min_size=1, max_size=5),
    separator=st.text(alphabet=' ', min_size=1, max_size=3)
)
@settings(max_examples=50, deadline=None)
def test_no_trailing_punctuation_or_spaces(words_list, separator):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
    PROPERTY: When the input is a simple sentence with words separated by single spaces and no trailing punctuation/spaces,
              the count should be correct after removing the last word.
    STRATEGY: Tests the core logic under ideal conditions for the `split(' ')` and `[:-1]` operations.
    """
    content = separator.join(words_list)

    try:
        result = task_func(content)
    except Exception:
        result = None

    # Calculate expected count
    if len(words_list) <= 1:
        expected_count = 0
    else:
        words_to_count = words_list[:-1]
        expected_count = sum(1 for word in words_to_count if word not in STOPWORDS)

    assert result == expected_count, f"Input: '{content}', Expected: {expected_count}, Got: {result}"