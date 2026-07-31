from candidate import task_func
from hypothesis import given, settings, strategies as st
import string
import re

@given(content=st.text(alphabet=string.ascii_letters + ' ', min_size=0, max_size=10))
@settings(max_examples=50, deadline=None)
def test_single_or_no_word_input_results_in_zero_count(content):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
                Example: task_func('this is an example content') -> 1
                The example implies that if the last word is removed, the remaining words are counted.
                If only one word exists, removing it means no words remain.
    PROPERTY: If the input string, when split by a single space, yields a list with 0 or 1 elements,
              the function should return 0, as there are no words left to count after removing the "last word".
    STRATEGY: Target inputs with 0 or 1 "words" (as defined by `str.split(' ')`) to test the `len(content) > 1` branch.
    """
    try:
        # Simulate the initial split to determine if it's a single-word or empty case
        initial_split = content.split(' ')
        
        # Filter out empty strings from the initial split to count actual "words"
        # This is to align with the spirit of "words" in a sentence, even if the code's
        # internal `split(' ')` might produce `['']` for an empty string.
        # The code's `if len(content) > 1` check operates on the raw `split(' ')` output.
        
        # The candidate code's logic:
        # content = content.split(' ')
        # if len(content) > 1: content = content[:-1] else: content = []
        # This means if len(content) is 0 or 1, it becomes [].
        
        if len(initial_split) <= 1:
            result = task_func(content)
            assert result == 0
        else:
            # For multi-word inputs, we don't assert 0, as it's not the target of this test.
            # We just ensure it doesn't raise an exception.
            task_func(content)
            pass # No specific assertion for multi-word inputs in this test
    except Exception:
        assert False, f"task_func raised an exception for input: '{content}'"


@given(content=st.text(alphabet=string.ascii_letters + ' ', min_size=0, max_size=10))
@settings(max_examples=50, deadline=None)
def test_output_is_non_negative(content):
    """
    SPEC BASIS: Returns: - count (int): The count of non-stopwords.
    PROPERTY: The count of non-stopwords must always be a non-negative integer.
    STRATEGY: General property for all valid string inputs.
    """
    try:
        count = task_func(content)
        assert isinstance(count, int)
        assert count >= 0
    except Exception:
        assert False, f"task_func raised an exception for input: '{content}'"


@given(
    words=st.lists(
        st.text(alphabet=string.ascii_letters, min_size=1, max_size=5),
        min_size=2, max_size=5
    )
)
@settings(max_examples=50, deadline=None)
def test_last_word_is_always_ignored(words):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
    PROPERTY: The last word of the original sentence should never contribute to the final count.
    STRATEGY: Construct sentences where the last word is a known non-stopword, and verify it's not counted.
              Also, ensure that if the last word is a stopword, its removal doesn't affect the count of other words.
    """
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

    # Ensure the last word is a non-stopword for a clear test case
    last_word_candidate = words[-1].lower()
    if last_word_candidate in STOPWORDS:
        # If it's a stopword, replace it with a known non-stopword
        # This is a bit of a hack to ensure the last word is a non-stopword for the test
        # A better strategy might be to generate non-stopwords directly.
        # For simplicity, we'll just use a fixed non-stopword.
        words[-1] = "example" # 'example' is not in the provided STOPWORDS list

    content = ' '.join(words)
    
    try:
        count_with_last_word_removed = task_func(content)

        # Manually calculate the expected count for all words *except* the last one
        # This re-implements the core logic for the "without the last word" part
        # but only for the words that *should* be considered.
        
        # Get all words except the last one
        words_to_consider = words[:-1]
        
        # Join them back and re-split robustly, then clean and filter stopwords
        processed_content = ' '.join(words_to_consider)
        tokens = re.split(r'\s+', processed_content)
        cleaned_words = [word.strip(string.punctuation).lower() for word in tokens if word]
        expected_non_stopwords = [word for word in cleaned_words if word not in STOPWORDS]
        expected_count = len(expected_non_stopwords)

        assert count_with_last_word_removed == expected_count, \
            f"Input: '{content}', Expected count: {expected_count}, Actual count: {count_with_last_word_removed}"

    except Exception:
        assert False, f"task_func raised an exception for input: '{content}'"