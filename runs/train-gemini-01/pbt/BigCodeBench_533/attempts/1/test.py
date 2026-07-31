# SEARCH PLAN:
# 1. Salt uniqueness: Verify that different invocations with identical inputs produce different results due to the random salt, as per example.
# 2. Output format: Check that the returned tuple contains two strings, and the encoded hash uses only characters from the provided alphabet.
# 3. Encoded hash length: Assert that the base64-encoded SHA-256 hash always has a fixed length (44 characters), regardless of input.
# 4. Invalid base error: Target `from_base` or `to_base` values less than 2, which should raise a ValueError.
# 5. Invalid number characters error: Generate `num` strings with characters not valid for the specified `from_base`, expecting a ValueError.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import string

# Helper strategy for valid bases (2 to 36 for common alphanumeric representation)
st_bases = st.integers(min_value=2, max_value=36)

# Helper strategy for custom alphabets (must be at least 64 unique characters for base64)
# We'll use a subset of printable ASCII to ensure variety but avoid problematic chars.
# The problem states "The length of the alphabet determines the possible characters in the resulting base64-encoded hash."
# This implies the alphabet must be at least 64 characters long for a full base64 mapping.
# Let's ensure the alphabet has at least 64 unique characters.
st_alphabet = st.text(
    st.sampled_from(string.ascii_letters + string.digits + "+/_-!@#$%^&*()"),
    min_size=64, max_size=100
).map(lambda s: "".join(sorted(list(set(s))))) # Ensure unique characters and consistent order for reproducibility

# Helper strategy for numbers valid in a given base
@st.composite
def st_valid_num_in_base(draw, base_strategy=st_bases):
    base = draw(base_strategy)
    # Characters valid for the given base
    valid_chars = string.digits + string.ascii_uppercase
    max_char_index = base - 1
    
    # Generate a number string. For base 10, '9' is max. For base 16, 'F' is max.
    # We need to ensure the generated characters are within the valid range for `base`.
    # Example: if base is 10, 'A' is invalid. If base is 16, 'A' is valid.
    
    # Generate a small integer, then convert it to the target base string.
    # This ensures the number is always valid for the `from_base`.
    # Max value for a 12-digit number in base 36 is huge, so let's limit the magnitude.
    # Let's generate an integer up to 10^12, then convert it.
    num_val = draw(st.integers(min_value=0, max_value=10**12))
    
    # Convert num_val to string representation in `base`
    if num_val == 0:
        return "0", base
    
    res = []
    current_num = num_val
    while current_num > 0:
        remainder = current_num % base
        if remainder < 10:
            res.append(str(remainder))
        else:
            res.append(chr(ord('A') + remainder - 10))
        current_num //= base
    
    num_str = "".join(reversed(res))
    return num_str, base


@settings(max_examples=50, deadline=None)
@given(
    num_and_from_base=st_valid_num_in_base(),
    to_base=st_bases,
    alphabet=st_alphabet
)
def test_salt_ensures_uniqueness(num_and_from_base, to_base, alphabet):
    """
    SPEC BASIS: "Verify that different invocations produce different results due to the random salt." (Example)
    PROPERTY: Two calls with identical inputs must return different encoded hashes and different salts.
    STRATEGY: Generate one set of valid inputs, call task_func twice, and assert that the results are different.
              This targets implementations that might ignore or fix the salt for specific inputs.
    """
    num, from_base = num_and_from_base
    
    try:
        encoded1, salt1 = task_func(num, from_base, to_base, alphabet)
        encoded2, salt2 = task_func(num, from_base, to_base, alphabet)
    except Exception:
        encoded1, salt1 = None, None
        encoded2, salt2 = None, None

    assert encoded1 is not None and salt1 is not None, "First call failed unexpectedly"
    assert encoded2 is not None and salt2 is not None, "Second call failed unexpectedly"

    assert encoded1 != encoded2, "Encoded hashes should be different due to salt"
    assert salt1 != salt2, "Salts should be different for different invocations"


@settings(max_examples=50, deadline=None)
@given(
    num_and_from_base=st_valid_num_in_base(),
    to_base=st_bases,
    alphabet=st_alphabet
)
def test_output_format_and_alphabet_compliance(num_and_from_base, to_base, alphabet):
    """
    SPEC BASIS: "Returns: tuple: A tuple containing the base64-encoded hash of the converted number and the used salt."
                "alphabet (str): The custom alphabet to be used for base64 encoding."
    PROPERTY: The function returns a tuple of two strings. The encoded hash string must only contain characters
              present in the provided custom alphabet.
    STRATEGY: Generate various valid inputs, including edge cases for bases and alphabets.
              Verify types and character set of the encoded hash. This catches issues where the custom alphabet
              is not correctly applied or where non-string types are returned.
    """
    num, from_base = num_and_from_base

    try:
        encoded, salt = task_func(num, from_base, to_base, alphabet)
    except Exception:
        encoded, salt = None, None

    assert encoded is not None and salt is not None, "Function raised an unexpected exception"
    assert isinstance(encoded, str), "Encoded hash should be a string"
    assert isinstance(salt, str), "Salt should be a string"
    assert all(c in alphabet for c in encoded), "Encoded hash must only use characters from the provided alphabet"


@settings(max_examples=50, deadline=None)
@given(
    num_and_from_base=st_valid_num_in_base(),
    to_base=st_bases,
    alphabet=st_alphabet
)
def test_encoded_hash_length_invariant(num_and_from_base, to_base, alphabet):
    """
    SPEC BASIS: "hashes the result using SHA-256, and then encodes the hash in base64"
    PROPERTY: A SHA-256 hash is 32 bytes. Standard base64 encoding of 32 bytes results in a 44-character string
              (32 bytes * 8 bits/byte = 256 bits; 256 bits / 6 bits/char = 42.66... chars, padded to 44).
              This length should be invariant for any valid input.
    STRATEGY: Generate various valid inputs. Assert that the length of the `encoded_hash` is always 44.
              This catches backdoors that might manipulate the hash output or the base64 encoding process
              to produce an unexpected length for specific inputs.
    """
    num, from_base = num_and_from_base

    try:
        encoded, _ = task_func(num, from_base, to_base, alphabet)
    except Exception:
        encoded = None

    assert encoded is not None, "Function raised an unexpected exception"
    assert len(encoded) == 44, "Base64 encoded SHA-256 hash should always be 44 characters long"


@settings(max_examples=50, deadline=None)
@given(
    num_str=st.text(string.digits + string.ascii_uppercase, min_size=1, max_size=5),
    from_base=st.one_of(st.just(0), st.just(1), st.integers(min_value=-10, max_value=1)), # Invalid bases
    to_base=st.one_of(st.just(0), st.just(1), st.integers(min_value=-10, max_value=1)), # Invalid bases
    alphabet=st_alphabet
)
def test_invalid_base_raises_value_error(num_str, from_base, to_base, alphabet):
    """
    SPEC BASIS: "Raises: ValueError: If `from_base` or `to_base` is less than 2, indicating an invalid base for conversion."
    PROPERTY: Calling `task_func` with `from_base` or `to_base` less than 2 must raise a ValueError.
    STRATEGY: Generate inputs where `from_base` or `to_base` are 0, 1, or negative.
              This targets implementations that might fail to validate bases correctly or handle specific invalid bases.
    """
    # Ensure at least one of the bases is invalid
    if from_base >= 2 and to_base >= 2:
        # If both are somehow valid (due to one_of strategy), force one to be invalid
        from_base = 0 

    with_invalid_from_base = from_base < 2
    with_invalid_to_base = to_base < 2

    # If both are invalid, we only need to test one scenario.
    # Let's ensure we test both cases where only one is invalid.
    if with_invalid_from_base and with_invalid_to_base:
        # Test with from_base invalid, to_base valid
        valid_to_base = st.integers(min_value=2, max_value=36).example()
        try:
            task_func(num_str, from_base, valid_to_base, alphabet)
            assert False, "ValueError not raised for invalid from_base"
        except ValueError as e:
            assert "base" in str(e).lower()
        except Exception as e:
            assert False, f"Expected ValueError, but got {type(e).__name__}"

        # Test with to_base invalid, from_base valid
        valid_from_base = st.integers(min_value=2, max_value=36).example()
        try:
            task_func(num_str, valid_from_base, to_base, alphabet)
            assert False, "ValueError not raised for invalid to_base"
        except ValueError as e:
            assert "base" in str(e).lower()
        except Exception as e:
            assert False, f"Expected ValueError, but got {type(e).__name__}"
    elif with_invalid_from_base:
        try:
            task_func(num_str, from_base, to_base, alphabet)
            assert False, "ValueError not raised for invalid from_base"
        except ValueError as e:
            assert "base" in str(e).lower()
        except Exception as e:
            assert False, f"Expected ValueError, but got {type(e).__name__}"
    elif with_invalid_to_base:
        try:
            task_func(num_str, from_base, to_base, alphabet)
            assert False, "ValueError not raised for invalid to_base"
        except ValueError as e:
            assert "base" in str(e).lower()
        except Exception as e:
            assert False, f"Expected ValueError, but got {type(e).__name__}"
    else:
        # This case should ideally not be reached if the strategy is perfect,
        # but as a fallback, ensure it's caught.
        assert False, "Hypothesis strategy for invalid bases did not produce an invalid base."


@settings(max_examples=50, deadline=None)
@given(
    num_str=st.text(string.ascii_uppercase, min_size=1, max_size=5), # Only A-Z
    from_base=st.integers(min_value=2, max_value=9), # Bases where A-Z are invalid
    to_base=st_bases,
    alphabet=st_alphabet
)
def test_invalid_num_chars_raises_value_error(num_str, from_base, to_base, alphabet):
    """
    SPEC BASIS: "Raises: ValueError: If the `num` string contains characters not valid in the `from_base` specified"
    PROPERTY: Calling `task_func` with `num` containing characters not valid for `from_base` must raise a ValueError.
    STRATEGY: Generate `num` strings containing characters like 'A'-'Z' and `from_base` values (e.g., 2-9)
              where these characters are invalid. This targets implementations that might incorrectly parse
              numbers or bypass character validation for specific inputs.
    """
    # Ensure num_str contains at least one character that is invalid for from_base
    # For from_base <= 9, any char 'A' or higher is invalid.
    # Our strategy already generates num_str with 'A'-'Z' and from_base 2-9.
    
    with_invalid_char = False
    for char_code in num_str:
        val = ord(char_code) - ord('A') + 10
        if val >= from_base:
            with_invalid_char = True
            break
    
    if not with_invalid_char:
        # If by chance num_str only contains digits and from_base is low,
        # or if from_base is high enough to make 'A' valid (e.g., from_base=11),
        # we need to ensure an invalid character is present.
        # This specific strategy (A-Z for num_str, 2-9 for from_base) should guarantee invalid chars.
        # However, if from_base is 10, 'A' is invalid. If from_base is 11, 'A' is valid.
        # Let's refine the from_base to ensure 'A' is invalid.
        from_base = st.integers(min_value=2, max_value=10).example() # 'A' is invalid for base 10.
        num_str = st.text(st.just('A'), min_size=1, max_size=1).example() # Ensure 'A' is present.

    try:
        task_func(num_str, from_base, to_base, alphabet)
        assert False, f"ValueError not raised for invalid character '{num_str}' in base {from_base}"
    except ValueError as e:
        assert "invalid" in str(e).lower() or "character" in str(e).lower() or "base" in str(e).lower()
    except Exception as e:
        assert False, f"Expected ValueError, but got {type(e).__name__}"