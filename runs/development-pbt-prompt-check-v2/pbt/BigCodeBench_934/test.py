from candidate import task_func
from hypothesis import given, settings, strategies as st
import hashlib

# Helper to calculate the expected dictionary of counts, as described in the specification.
# This helper does NOT perform the MD5 hashing, as the serialization to string before hashing
# is not specified. It only calculates the intermediate dictionary.
def _calculate_pair_counts(word: str) -> dict:
    """Calculates the dictionary of adjacent pair counts."""
    if len(word) < 2:
        return {}
    counts = {}
    for i in range(len(word) - 1):
        pair = word[i:i+2]
        counts[pair] = counts.get(pair, 0) + 1
    return counts

# Strategy for valid words: strings of letters, max length 12.
# The problem does not specify character set, but examples use lowercase English letters.
# To be conservative, we stick to lowercase ASCII letters.
# Max length 12 to keep generated inputs small as per instructions.
valid_words = st.text(st.ascii_lowercase, min_size=0, max_size=12)

@given(word=st.just('abracadabra'))
@settings(max_examples=50, deadline=None)
def test_example_abracadabra(word: str):
    """
    SPEC BASIS: >>> task_func('abracadabra')\n    'bc9af285d87b312e61ab3661e66b741b'
    PROPERTY: The function returns the exact MD5 hash for the example input 'abracadabra'.
    """
    expected_hash = 'bc9af285d87b312e61ab3661e66b741b'
    assert task_func(word) == expected_hash

@given(word=st.just('hello'))
@settings(max_examples=50, deadline=None)
def test_example_hello(word: str):
    """
    SPEC BASIS: >>> task_func('hello')\n    'dd5dec1a853625e2dc48f3d42665c337'
    PROPERTY: The function returns the exact MD5 hash for the example input 'hello'.
    """
    expected_hash = 'dd5dec1a853625e2dc48f3d42665c337'
    assert task_func(word) == expected_hash

@given(word=valid_words)
@settings(max_examples=50, deadline=None)
def test_return_type_is_string(word: str):
    """
    SPEC BASIS: "encode the result as an MD5 hash." and examples show string outputs.
    PROPERTY: The function returns a string.
    """
    result = task_func(word)
    assert isinstance(result, str)

@given(word=valid_words)
@settings(max_examples=50, deadline=None)
def test_return_length_is_32(word: str):
    """
    SPEC BASIS: "encode the result as an MD5 hash." and examples show 32-character strings.
    PROPERTY: The returned string has a length of 32 characters (standard MD5 hash length).
    """
    result = task_func(word)
    assert len(result) == 32

@given(word=valid_words)
@settings(max_examples=50, deadline=None)
def test_return_is_hexadecimal(word: str):
    """
    SPEC BASIS: "encode the result as an MD5 hash." and examples show hexadecimal strings.
    PROPERTY: The returned string consists only of hexadecimal characters (0-9, a-f).
    """
    result = task_func(word)
    assert all(c in '0123456789abcdef' for c in result)

@given(word=valid_words)
@settings(max_examples=50, deadline=None)
def test_determinism(word: str):
    """
    SPEC BASIS: Implied by "Count the occurrence... and encode the result as an MD5 hash."
    PROPERTY: Calling the function with the same input multiple times yields the same output.
    """
    result1 = task_func(word)
    result2 = task_func(word)
    assert result1 == result2

@given(word=st.just(''))
@settings(max_examples=50, deadline=None)
def test_empty_string_input(word: str):
    """
    SPEC BASIS: "Count the occurrence of each adjacent pair of letters from left to right in a word" implies no pairs for empty string.
    PROPERTY: An empty string input results in a consistent, deterministic MD5 hash (likely of an empty or specific representation).
    """
    # Cannot predict the exact hash without knowing the serialization of an empty dict.
    # But it must be a valid hash string and deterministic.
    result = task_func(word)
    assert isinstance(result, str)
    assert len(result) == 32
    assert all(c in '0123456789abcdef' for c in result)
    assert result == task_func(word) # Determinism for this specific input

@given(word=st.just('a'))
@settings(max_examples=50, deadline=None)
def test_single_character_string_input(word: str):
    """
    SPEC BASIS: "Count the occurrence of each adjacent pair of letters from left to right in a word" implies no pairs for single char string.
    PROPERTY: A single-character string input results in a consistent, deterministic MD5 hash.
    """
    # Cannot predict the exact hash without knowing the serialization of an empty dict.
    # But it must be a valid hash string and deterministic.
    result = task_func(word)
    assert isinstance(result, str)
    assert len(result) == 32
    assert all(c in '0123456789abcdef' for c in result)
    assert result == task_func(word) # Determinism for this specific input

@given(word=st.text(st.ascii_lowercase, min_size=2, max_size=12))
@settings(max_examples=50, deadline=None)
def test_output_changes_with_input(word: str):
    """
    SPEC BASIS: "Count the occurrence of each adjacent pair of letters from left to right in a word and encode the result as an MD5 hash."
    PROPERTY: Different inputs that should produce different pair counts result in different MD5 hashes.
    """
    # This is a weak property, but it checks for trivial constant return values.
    # We can't guarantee *all* different inputs produce different hashes due to collisions,
    # but for simple cases, it should.
    # We compare against a known different input, e.g., 'zz'
    if word != 'zz':
        result_word = task_func(word)
        result_zz = task_func('zz')
        # It's possible for a collision, but highly unlikely for simple inputs.
        # This checks against a trivial implementation that always returns the same hash.
        assert result_word != result_zz or _calculate_pair_counts(word) == _calculate_pair_counts('zz')

@given(word=st.text(st.ascii_lowercase, min_size=2, max_size=12))
@settings(max_examples=50, deadline=None)
def test_case_sensitivity_implied_by_examples(word: str):
    """
    SPEC BASIS: Examples 'abracadabra' and 'hello' use lowercase letters, implying case sensitivity.
    PROPERTY: Changing the case of letters in the input word should result in a different hash (unless the pair counts are identical).
    """
    # This tests that 'aa' is different from 'aA' or 'Aa' or 'AA' if the implementation is case-sensitive.
    # The problem does not explicitly state case sensitivity, but examples use only lowercase.
    # A conservative interpretation is that 'a' and 'A' are distinct characters.
    upper_word = word.upper()
    if word != upper_word: # Only test if there's an actual case difference
        hash_lower = task_func(word)
        hash_upper = task_func(upper_word)
        # If the pair counts are different, the hashes must be different.
        # If the pair counts are identical (e.g., if the function internally normalizes case),
        # then the hashes *could* be the same.
        # We assert they are different unless the underlying pair counts are identical.
        # This is a weak check, but avoids false positives if the implementation normalizes case.
        assert hash_lower != hash_upper or _calculate_pair_counts(word) == _calculate_pair_counts(upper_word)