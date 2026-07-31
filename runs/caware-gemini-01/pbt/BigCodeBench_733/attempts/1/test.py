# SEARCH PLAN:
# 1. Empty/Single-word sentence boundary: Test inputs with zero or one word, where the "last word" rule implies a count of zero.
# 2. Metamorphic relation for adding a word: Verify how the count changes when a new word is appended, shifting which word is "last".
# 3. Metamorphic relation for removing the last word: Check that removing the last word from a sentence (which was previously excluded) results in the same count as the original sentence.
# 4. Punctuation and case handling: Ensure the function correctly processes sentences with punctuation and mixed case, assuming standard word tokenization and case-insensitivity for stop words.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import re
import string

# A common set of English stop words. The problem does not provide one,
# so this is used for generating inputs that are *likely* to be stop words
# or non-stop words, but the tests themselves do not rely on this specific list
# for their assertions (they use metamorphic properties or simple counts).
_STOP_WORDS = {
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'this', 'that', 'these', 'those',
    'and', 'but', 'or', 'for', 'nor', 'on', 'at', 'to', 'from', 'of', 'in', 'with',
    'by', 'as', 'it', 'its', 'he', 'she', 'they', 'them', 'him', 'her', 'his', 'hers',
    'what', 'which', 'who', 'whom', 'where', 'when', 'why', 'how', 'all', 'any',
    'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'not',
    'only', 'own', 'same', 'so', 'than', 'too', 'very', 'can', 'will', 'just',
    'don', 'should', 'now', 'i', 'me', 'my', 'you', 'your', 'yours', 'we', 'us',
    'our', 'ours', 's', 't', 'm', 'll', 'd', 're', 've'
}

# Strategy for generating words: either common stop words or simple non-stop words.
# This helps ensure a mix of word types without relying on the specific stop word list
# for the assertion logic.
_WORD_STRATEGY = st.one_of(
    st.sampled_from(list(_STOP_WORDS)),
    st.text(string.ascii_lowercase, min_size=2, max_size=8).filter(lambda w: w not in _STOP_WORDS)
)

# Strategy for generating sentences: lists of words joined by spaces, with optional punctuation.
@st.composite
def sentence_strategy(draw, min_words, max_words):
    words = draw(st.lists(_WORD_STRATEGY, min_size=min_words, max_size=max_words))
    if not words:
        return ""
    
    # Add some punctuation randomly
    punctuations = draw(st.lists(st.sampled_from(['.', ',', '!', '?']), min_size=0, max_size=2))
    
    sentence = " ".join(words)
    if punctuations:
        sentence += draw(st.sampled_from(punctuations))
    
    # Randomly capitalize first letter
    if draw(st.booleans()):
        sentence = sentence[0].upper() + sentence[1:]
        
    return sentence

@settings(max_examples=50, deadline=None)
@given(content=st.one_of(
    st.just(''),
    sentence_strategy(min_words=1, max_words=1)
))
def test_empty_or_single_word_sentence_returns_zero(content):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
    PROPERTY: For an empty sentence or a sentence with only one word, the count of non-stop words must be 0.
              If the sentence is empty, there are no words. If there's one word, it's the "last word" and excluded.
    STRATEGY: Generate empty strings and strings containing exactly one word (which will be excluded by the rule).
    """
    try:
        result = task_func(content)
    except Exception:
        result = None
    assert result is not None, f"task_func raised an exception for content: '{content}'"
    assert result == 0, f"Expected 0 for content '{content}', got {result}"

@settings(max_examples=50, deadline=None)
@given(
    first_part=sentence_strategy(min_words=1, max_words=5),
    last_word=_WORD_STRATEGY,
    new_last_word=_WORD_STRATEGY
)
def test_metamorphic_adding_word_changes_last_word_exclusion(first_part, last_word, new_last_word):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
    PROPERTY: When a new word is appended to a sentence, the *original* last word is now included in the count,
              while the *new* last word is excluded. This should result in a count that is either the same,
              one greater, or one less than the original count, depending on whether the original last word
              was a non-stop word and whether the new last word is a non-stop word.
              Specifically, if we have `S = P + W1` and `S' = P + W1 + W2`, then `count(S')` should be
              `count(P)` + (1 if W1 is non-stop else 0).
    STRATEGY: Generate a sentence, then append a new word. Compare the result of `task_func` on the original
              sentence with the result on the modified sentence. This tests the "without the last word" rule.
    """
    # Clean up punctuation and ensure consistent word separation for comparison
    def get_words(text):
        return [word.lower() for word in re.findall(r'\b\w+\b', text)]

    words_first_part = get_words(first_part)
    
    # Ensure first_part has at least one word to make 'last_word' meaningful
    if not words_first_part:
        first_part = "dummy"
        words_first_part = ["dummy"]

    original_content = f"{first_part} {last_word}"
    extended_content = f"{original_content} {new_last_word}"

    try:
        original_result = task_func(original_content)
        extended_result = task_func(extended_content)
    except Exception as e:
        assert False, f"task_func raised an exception for content '{original_content}' or '{extended_content}': {e}"

    # The words considered for original_content are `words_first_part`.
    # The words considered for extended_content are `words_first_part` + `last_word`.
    # So, extended_result should be original_result + (1 if last_word is non-stop else 0).
    # Since we don't know the stop word list, we can't predict the exact value,
    # but we can check if the difference is 0 or 1.
    
    # This test is tricky because we don't know the stop word list.
    # A more robust metamorphic property:
    # If we have a sentence `S = W1 W2 ... Wn-1 Wn`.
    # `task_func(S)` considers `W1 ... Wn-1`.
    # If we form `S' = W1 W2 ... Wn-1`.
    # `task_func(S')` considers `W1 ... Wn-2`.
    # This is `test_metamorphic_removing_last_word_from_consideration`.

    # Let's re-evaluate this metamorphic test.
    # S1 = P + W1 (last word W1) -> considers P
    # S2 = P + W1 + W2 (last word W2) -> considers P + W1
    # The difference `task_func(S2) - task_func(S1)` should be 1 if W1 is a non-stop word, and 0 if W1 is a stop word.
    # Since we don't know the stop word list, we can only assert that the difference is 0 or 1.
    
    diff = extended_result - original_result
    assert diff in {0, 1}, \
        f"Metamorphic property failed: Adding '{new_last_word}' to '{original_content}' " \
        f"changed count from {original_result} to {extended_result}. Expected difference 0 or 1, got {diff}."

@settings(max_examples=50, deadline=None)
@given(content=sentence_strategy(min_words=2, max_words=10))
def test_metamorphic_removing_last_word_from_consideration(content):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
    PROPERTY: If a sentence `S` has words `W1 W2 ... Wn-1 Wn`, `task_func(S)` considers `W1 ... Wn-1`.
              If we create `S_prime = W1 W2 ... Wn-1`, then `task_func(S_prime)` considers `W1 ... Wn-2`.
              This means `task_func(S)` should be equal to `task_func(S_prime)` plus 1 if `Wn-1` is a non-stop word,
              or `task_func(S_prime)` if `Wn-1` is a stop word.
              The difference `task_func(S) - task_func(S_prime)` must be 0 or 1.
    STRATEGY: Generate a sentence with at least two words. Create a `S_prime` by removing the last word.
              Compare the results. This directly tests the "without the last word" rule's effect on the count.
    """
    words = [word.lower() for word in re.findall(r'\b\w+\b', content)]
    
    if len(words) < 2: # Ensure there are at least two words to remove one
        # This case should be handled by min_words=2 in sentence_strategy, but as a safeguard
        return

    # S = W1 ... Wn-1 Wn
    # S_prime = W1 ... Wn-1
    
    # Reconstruct S_prime without the last word, preserving original spacing/punctuation style if possible
    # This is tricky with arbitrary punctuation. Let's simplify to just words.
    s_prime_words = words[:-1]
    s_prime_content = " ".join(s_prime_words)
    
    try:
        result_s = task_func(content)
        result_s_prime = task_func(s_prime_content)
    except Exception as e:
        assert False, f"task_func raised an exception for content '{content}' or '{s_prime_content}': {e}"

    diff = result_s - result_s_prime
    assert diff in {0, 1}, \
        f"Metamorphic property failed: For content '{content}' (words: {words}) and '{s_prime_content}' (words: {s_prime_words}), " \
        f"expected difference in counts to be 0 or 1. Got {result_s} - {result_s_prime} = {diff}."

@settings(max_examples=50, deadline=None)
@given(
    words=st.lists(_WORD_STRATEGY, min_size=2, max_size=10),
    punctuation=st.text(st.sampled_from(string.punctuation + ' '), min_size=0, max_size=3),
    case_change=st.booleans()
)
def test_punctuation_and_case_invariance_on_word_extraction(words, punctuation, case_change):
    """
    SPEC BASIS: "Count the non-stop words in a sentence without the last word."
                Example: `task_func('this is an example content')` returns `1`.
                This implies words are extracted and case-normalized for stop word comparison.
    PROPERTY: Adding punctuation or changing case (without altering the actual words) should not change
              the count of non-stop words, assuming standard word tokenization and case-insensitivity.
    STRATEGY: Generate a base sentence. Create a modified version with added punctuation and/or changed case.
              The count should remain the same.
    """
    base_content = " ".join(words)
    
    modified_content = base_content
    if case_change:
        modified_content = modified_content.upper() if words[0][0].islower() else modified_content.lower()
    
    # Insert punctuation randomly
    if punctuation:
        # Insert punctuation at the end or in the middle
        if len(words) > 1:
            insert_idx = st.integers(min_value=0, max_value=len(words) - 2).example() # Not last word
            modified_content_list = list(modified_content)
            # Find a space to insert punctuation
            space_indices = [i for i, char in enumerate(modified_content_list) if char == ' ']
            if space_indices:
                insert_pos = space_indices[insert_idx % len(space_indices)]
                modified_content_list.insert(insert_pos + 1, punctuation)
                modified_content = "".join(modified_content_list)
            else: # No spaces, just append
                modified_content += punctuation
        else: # Single word, just append
            modified_content += punctuation

    try:
        base_result = task_func(base_content)
        modified_result = task_func(modified_content)
    except Exception as e:
        assert False, f"task_func raised an exception for content '{base_content}' or '{modified_content}': {e}"

    assert base_result == modified_result, \
        f"Punctuation/case invariance failed: Base '{base_content}' -> {base_result}, " \
        f"Modified '{modified_content}' -> {modified_result}. Expected same count."

@settings(max_examples=50, deadline=None)
@given(content=st.just('this is an example content'))
def test_example_case(content):
    """
    SPEC BASIS: Example: `task_func('this is an example content')` returns `1`.
    PROPERTY: The function must return the exact value specified in the example.
    STRATEGY: Use the exact example string as input.
    """
    try:
        result = task_func(content)
    except Exception:
        result = None
    assert result is not None, f"task_func raised an exception for content: '{content}'"
    assert result == 1, f"Expected 1 for example '{content}', got {result}"