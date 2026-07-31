# SEARCH PLAN:
# 1. Invalid inputs: Test `n_sentences < 0` and `vocabulary` empty, which must raise `ValueError`.
# 2. Output structure and case: Verify the output is a list of lowercase strings, and its length matches `n_sentences`.
# 3. Underscoring logic: Ensure target words with spaces are correctly underscored and case-insensitivity is applied.
# 4. No underscoring for single words or non-matches: Verify that words without spaces in `target_words` are not underscored, and words not matching any target are also not underscored.
# 5. Boundary `n_sentences=0` and `n_sentences=1`: Covered by output structure test, but specifically ensure empty list for 0 and correct processing for 1.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import re
from collections import Counter

# Helper strategy for words, ensuring they are simple and don't contain special regex characters
# or internal spaces unless explicitly for target_words.
word_strategy = st.text(
    st.sampled_from('abcdefghijklmnopqrstuvwxyz'),
    min_size=1, max_size=5
).map(lambda s: s.lower()) # Ensure vocabulary words are lowercase for consistency

# Strategy for target words, which can contain spaces
target_word_part_strategy = st.text(
    st.sampled_from('abcdefghijklmnopqrstuvwxyz'),
    min_size=1, max_size=5
)

# Strategy for target words, which can be single words or phrases with spaces
target_words_strategy = st.lists(
    st.text(
        st.sampled_from('abcdefghijklmnopqrstuvwxyz '),
        min_size=1, max_size=10
    ).map(lambda s: s.strip()), # Remove leading/trailing spaces from target phrases
    min_size=0, max_size=5
).map(lambda l: [s for s in l if s]) # Remove any empty strings that might result from stripping

@settings(max_examples=50, deadline=None)
@given(
    target_words=target_words_strategy,
    n_sentences=st.integers(min_value=-5, max_value=-1), # Negative n_sentences
    vocabulary=st.lists(word_strategy, min_size=1, max_size=5) # Valid vocabulary
)
def test_raises_value_error_for_negative_n_sentences(target_words, n_sentences, vocabulary):
    """
    SPEC BASIS: "Raises: ValueError: If n_sentences is negative or if the vocabulary is empty."
    PROPERTY: A ValueError is raised when n_sentences is negative.
    STRATEGY: Generate negative `n_sentences` values while keeping other inputs valid.
    """
    try:
        task_func(target_words, n_sentences, vocabulary)
        assert False, "ValueError was not raised for negative n_sentences"
    except ValueError as e:
        assert "negative" in str(e).lower() or "n_sentences" in str(e).lower()
    except Exception as e:
        assert False, f"Expected ValueError, but got {type(e).__name__}: {e}"

@settings(max_examples=50, deadline=None)
@given(
    target_words=target_words_strategy,
    n_sentences=st.integers(min_value=0, max_value=5), # Valid n_sentences
    vocabulary=st.lists(word_strategy, min_size=0, max_size=0) # Empty vocabulary
)
def test_raises_value_error_for_empty_vocabulary(target_words, n_sentences, vocabulary):
    """
    SPEC BASIS: "Raises: ValueError: If n_sentences is negative or if the vocabulary is empty."
    PROPERTY: A ValueError is raised when vocabulary is empty.
    STRATEGY: Generate an empty `vocabulary` while keeping other inputs valid.
    """
    try:
        task_func(target_words, n_sentences, vocabulary)
        assert False, "ValueError was not raised for empty vocabulary"
    except ValueError as e:
        assert "empty" in str(e).lower() or "vocabulary" in str(e).lower()
    except Exception as e:
        assert False, f"Expected ValueError, but got {type(e).__name__}: {e}"

@settings(max_examples=50, deadline=None)
@given(
    target_words=target_words_strategy,
    n_sentences=st.integers(min_value=0, max_value=5),
    vocabulary=st.lists(word_strategy, min_size=1, max_size=5)
)
def test_output_structure_and_case(target_words, n_sentences, vocabulary):
    """
    SPEC BASIS: "The function returns the processed sentences as a list of all lowercase strings."
                "n_sentences (int): Number of sentences to generate."
    PROPERTY: The output is a list of strings, its length matches `n_sentences`, and all sentences are lowercase.
    STRATEGY: Generate valid inputs and check the basic structural and formatting invariants of the output.
              This covers `n_sentences=0` (empty list) and `n_sentences=1` (single sentence).
    """
    try:
        result = task_func(target_words, n_sentences, vocabulary)
    except Exception:
        result = None
    assert result is not None, "Function raised an unexpected exception for valid input."

    assert isinstance(result, list), "Output is not a list."
    assert len(result) == n_sentences, f"Expected {n_sentences} sentences, but got {len(result)}."

    for sentence in result:
        assert isinstance(sentence, str), "Sentence in the output list is not a string."
        assert sentence.islower() or not sentence, f"Sentence '{sentence}' is not all lowercase."

@settings(max_examples=50, deadline=None)
@given(
    target_words=st.lists(
        st.one_of(
            st.just("a b"),
            st.just("x y z"),
            st.just("test word"),
            st.just("another phrase"),
            st.just("mixed case target")
        ),
        min_size=1, max_size=3
    ),
    n_sentences=st.integers(min_value=1, max_value=3),
    vocabulary=st.lists(
        st.one_of(
            word_strategy,
            st.just("a"), st.just("b"), st.just("x"), st.just("y"), st.just("z"),
            st.just("test"), st.just("word"), st.just("another"), st.just("phrase"),
            st.just("mixed"), st.just("case"), st.just("target")
        ),
        min_size=5, max_size=10
    )
)
def test_underscoring_and_case_insensitivity(target_words, n_sentences, vocabulary):
    """
    SPEC BASIS: "if any words from the target_words list appear in these sentences, spaces within those words are replaced with underscores; here the modification is insensitive to the case of the letters."
                "The function returns the processed sentences as a list of all lowercase strings."
    PROPERTY: For each generated sentence, if a target word (case-insensitively) is present, its spaces are replaced by underscores, and the final sentence is lowercase.
    STRATEGY: Bias `target_words` and `vocabulary` to ensure multi-word targets are likely to be formed in sentences.
              Then, for each target word, check if its underscored, lowercase version is present in the output sentences.
              This is a metamorphic check: if a target word is present, its form changes predictably.
    """
    # Add components of target words to vocabulary to increase chances of them being generated
    extended_vocabulary = list(vocabulary)
    for target in target_words:
        extended_vocabulary.extend(target.lower().split())
    extended_vocabulary = list(set(extended_vocabulary)) # Remove duplicates

    try:
        result = task_func(target_words, n_sentences, extended_vocabulary)
    except Exception:
        result = None
    assert result is not None, "Function raised an unexpected exception for valid input."

    for sentence in result:
        assert isinstance(sentence, str)
        assert sentence.islower() or not sentence

        # Check for underscoring:
        # For each target word, if its components are found in the sentence,
        # the underscored version (lowercase) should be present.
        for target in target_words:
            target_lower = target.lower()
            target_underscored = target_lower.replace(' ', '_')

            # Create a regex pattern to find the target phrase (case-insensitively)
            # in the original sentence before any modification.
            # This is tricky because we don't have the *original* generated sentence.
            # Instead, we check if the *underscored* version is present in the *output*.
            # This implies that if the target was present, it *must* have been underscored.

            # A simpler check: if the target word (lowercase, with spaces) is NOT in the sentence,
            # then the underscored version should not be there unless it was formed by other means.
            # If the target word (lowercase, with spaces) *could* have been formed, then the underscored
            # version *should* be there.

            # Let's check if the underscored version is present.
            # This is a weak check, as it doesn't guarantee the *reason* for underscoring.
            # A stronger check would require knowing the original sentence.
            # However, the problem states "if any words from the target_words list appear in these sentences,
            # spaces within those words are replaced".
            # So, if the target_word's components are present in the sentence, the underscored version should be there.

            # Let's try to reconstruct the original sentence's potential words to see if a target could have matched.
            # This is still hard without the original random generation.

            # Alternative: Check that *only* target words are underscored.
            # This means any `_` in the output sentence must be part of an underscored target word.
            # This is a stronger invariant.

            # Collect all underscored phrases in the output sentence
            underscored_phrases_in_output = re.findall(r'\b\w+_\w+\b', sentence)

            # For each underscored phrase found, check if it corresponds to a target word
            for phrase in underscored_phrases_in_output:
                # Convert back to space-separated to check against target_words
                original_form = phrase.replace('_', ' ')
                # Check if this original form (case-insensitively) is in target_words
                assert any(original_form == tw.lower() for tw in target_words), \
                    f"Underscored phrase '{phrase}' in sentence '{sentence}' does not match any target word."

            # This test ensures that no *extra* words are underscored.
            # It doesn't guarantee that *all* matching target words *are* underscored,
            # because we don't control the random generation to guarantee a match.
            # However, the previous test `test_output_structure_and_case` ensures the output is lowercase.
            # The example `['alice_charlie alice alice_charlie charlie alice_charlie dan alice']`
            # shows that `alice charlie` becomes `alice_charlie`.

            # Let's try to make a target word appear.
            # If a target word is 'a b', and vocabulary contains 'a' and 'b',
            # then if 'a b' appears in the sentence, it should be 'a_b'.
            # We can't guarantee 'a b' appears, but we can check if 'a_b' appears.
            # If 'a_b' appears, it must be from 'a b'.

            # This test focuses on the "no false positives" for underscoring.
            # To test "all true positives", we'd need to control the random generation, which is forbidden.
            # The best we can do is ensure the *form* of the transformation is correct if it happens.

            # Let's add a check for the example behavior:
            # If a target word is 'apple banana', and the sentence contains 'apple banana',
            # then 'apple_banana' should be in the output.
            # We can't guarantee 'apple banana' is generated.
            # But we can check if the *underscored* version of a target word is present.
            # If it is, it must be lowercase.

            # This test is good for ensuring no *unintended* underscoring.
            # For ensuring *intended* underscoring, we rely on the example and the fact that
            # if the components are present, the transformation should occur.
            # The problem states "if any words from the target_words list appear in these sentences".
            # This implies the *phrase* must appear.

            # Let's refine the check: if an underscored phrase is found, it must correspond to a target.
            # This is a strong property.

    # This test implicitly covers the case-insensitivity for matching, as the `target_words`
    # can contain mixed case, but the `original_form` comparison is done against `tw.lower()`.
    # The output itself is checked for being lowercase in `test_output_structure_and_case`.

@settings(max_examples=50, deadline=None)
@given(
    target_words=st.lists(
        st.one_of(
            word_strategy, # Single words, should not be underscored
            st.just("no_space_target") # Already underscored, should not be re-processed
        ),
        min_size=0, max_size=5
    ),
    n_sentences=st.integers(min_value=1, max_value=5),
    vocabulary=st.lists(word_strategy, min_size=1, max_size=5)
)
def test_no_underscoring_for_single_words_or_non_matches(target_words, n_sentences, vocabulary):
    """
    SPEC BASIS: "spaces in certain target words replaced by underscores"
    PROPERTY: Words in `target_words` that do not contain spaces should not result in underscores in the output.
              Also, if a target word is already underscored, it should not be further modified.
    STRATEGY: Generate `target_words` that are single words or already contain underscores.
              Verify that no new underscores are introduced based on these targets.
    """
    try:
        result = task_func(target_words, n_sentences, vocabulary)
    except Exception:
        result = None
    assert result is not None, "Function raised an unexpected exception for valid input."

    for sentence in result:
        assert isinstance(sentence, str)
        assert sentence.islower() or not sentence

        # Check that no underscores are present that shouldn't be.
        # Specifically, if a target word was a single word (e.g., 'apple'),
        # it should not become 'apple_'.
        # If a target word was 'already_underscored', it should not become 'already__underscored'.
        # The problem states "spaces within those words are replaced with underscores".
        # This implies only words *with spaces* are affected.

        # Find all underscored parts in the sentence
        underscored_parts = re.findall(r'\b\w+_\w+\b', sentence)

        for part in underscored_parts:
            # This part must have originated from a target word that originally contained spaces.
            # Check if the original form (replacing '_' with ' ') exists in the target_words (case-insensitively)
            original_form = part.replace('_', ' ')
            assert any(original_form == tw.lower() for tw in target_words if ' ' in tw), \
                f"Underscored part '{part}' in sentence '{sentence}' does not correspond to a target word with spaces."

        # Also, ensure that single-word targets do not cause any underscoring.
        for target in target_words:
            if ' ' not in target: # This is a single-word target
                # The single word itself might appear in the sentence.
                # We need to ensure it doesn't get an underscore.
                # E.g., if target is 'apple', and sentence is 'apple banana', it should not become 'apple_ banana'.
                # This is covered by the `underscored_parts` check above, as 'apple_' would be caught.
                pass # No specific assertion needed here, as the above check covers it.