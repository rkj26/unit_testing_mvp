from candidate import task_func
from hypothesis import given, settings, strategies as st
import string

@given(word=st.text(alphabet=string.ascii_lowercase, min_size=0, max_size=12))
@settings(max_examples=50, deadline=None)
def test_output_is_md5_hash_format(word: str):
    """
    SPEC BASIS: "encode the result as an MD5 hash."
    PROPERTY: The function always returns a string of length 32, which is the standard length for an MD5 hash.
    """
    result = task_func(word)
    assert isinstance(result, str)
    assert len(result) == 32
    # Optionally, check if it's hex, but not explicitly stated as a requirement for the test.
    # assert all(c in string.hexdigits for c in result)

@given(word=st.text(alphabet=string.ascii_lowercase, min_size=0, max_size=1))
@settings(max_examples=50, deadline=None)
def test_short_words_yield_same_hash(word: str):
    """
    SPEC BASIS: "Count the occurrence of each adjacent pair of letters from left to right in a word"
    PROPERTY: Words with fewer than two characters have no adjacent pairs. Therefore, their internal dictionary of counts should be empty.
              Assuming a consistent serialization of an empty dictionary, all such inputs should produce the same MD5 hash.
    """
    # The problem does not specify the hash of an empty dictionary.
    # However, it implies that the *internal* dictionary is empty for words with length < 2.
    # If the serialization of an empty dictionary is consistent, then the hash should be consistent.
    # We can pick a canonical short word (e.g., empty string) and assert others match its hash.
    expected_hash_for_empty_pairs = task_func('') # This will be the baseline for empty/single-char words
    result = task_func(word)
    assert result == expected_hash_for_empty_pairs

@given(word=st.just('abracadabra'))
@settings(max_examples=50, deadline=None)
def test_example_abracadabra(word: str):
    """
    SPEC BASIS: Example: `>>> task_func('abracadabra') 'bc9af285d87b312e61ab3661e66b741b'`
    PROPERTY: The function returns the specified MD5 hash for the input 'abracadabra'.
    """
    expected_hash = 'bc9af285d87b312e61ab3661e66b741b'
    result = task_func(word)
    assert result == expected_hash

@given(word=st.just('hello'))
@settings(max_examples=50, deadline=None)
def test_example_hello(word: str):
    """
    SPEC BASIS: Example: `>>> task_func('hello') 'dd5dec1a853625e2dc48f3d42665c337'`
    PROPERTY: The function returns the specified MD5 hash for the input 'hello'.
    """
    expected_hash = 'dd5dec1a853625e2dc48f3d42665c337'
    result = task_func(word)
    assert result == expected_hash