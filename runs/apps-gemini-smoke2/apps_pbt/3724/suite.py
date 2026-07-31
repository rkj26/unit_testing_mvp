import random
from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str  (the harness provides this)

@st.composite
def make_input(draw):
    """
    Generates valid input strings for the problem.
    N ranges from 1 to 10^6. S consists of A, B, C.
    The strategy focuses on generating a diverse set of N values, including small edge cases,
    sample values, and larger values, and then generating a diverse string S for that N.
    """
    # Define a strategy for N that prioritizes small values, common sample values,
    # and occasionally hits large values to test scalability.
    n = draw(st.one_of(
        st.just(1),           # Smallest N
        st.just(2),           # Small N, allows one operation
        st.just(5),           # Sample N
        st.just(50),          # Sample N
        st.integers(min_value=3, max_value=100), # Other small N values
        st.integers(min_value=101, max_value=10**6) # Larger N values
    ))

    # Generate the string S of length N using characters 'A', 'B', 'C'.
    # st.text is good at generating diverse strings, including all-same, alternating, etc.
    s = draw(st.text('ABC', min_size=n, max_size=n))
    
    return f"{n}\n{s}"

# Helper function to permute characters in a string
def _permute_string(s, char_permutation_map):
    return ''.join(char_permutation_map[c] for c in s)

@given(make_input())
@settings(max_examples=50, deadline=None)
def test_char_permutation_invariance(stdin):
    """
    Metamorphic test: Permuting the characters (A, B, C) in the input string S
    should not change the *number* of distinct reachable strings.
    The operation rule ("replace with the character different from both") is
    symmetric with respect to any permutation of {A, B, C}.
    """
    n_str, s_orig = stdin.split('\n')
    n = int(n_str)
    
    stdout_orig = run_candidate(stdin)
    count_orig = int(stdout_orig)

    # Generate a random permutation of characters A, B, C
    chars = ['A', 'B', 'C']
    shuffled_chars = random.sample(chars, len(chars)) # Ensure a true permutation
    char_map = {old: new for old, new in zip(chars, shuffled_chars)}

    # Apply the permutation to the original string
    s_permuted = _permute_string(s_orig, char_map)
    stdin_permuted = f"{n}\n{s_permuted}"
    
    stdout_permuted = run_candidate(stdin_permuted)
    count_permuted = int(stdout_permuted)

    assert count_orig == count_permuted, \
        f"Permutation invariance failed for S='{s_orig}' (N={n}) and S'='{s_permuted}' (map: {char_map}). " \
        f"Original count: {count_orig}, Permuted count: {count_permuted}. Input: {stdin_orig_first_line} {stdin_orig_last_line}"


@given(make_input())
@settings(max_examples=50, deadline=None)
def test_all_same_chars_and_non_trivial_count(stdin):
    """
    Edge case and sanity check:
    1. If the input string `S` consists of `N` identical characters (e.g., "AAAAA"),
       no operation can be performed (since `S_i == S_{i+1}` always).
       Therefore, the only distinct string is `S` itself, and the count must be 1.
    2. If the input string `S` contains at least one pair of distinct adjacent characters,
       at least one operation is possible, leading to at least one new (shorter) string.
       Thus, the count must be strictly greater than 1.
    """
    n_str, s_orig = stdin.split('\n')
    n = int(n_str)
    
    stdout = run_candidate(stdin)
    count = int(stdout)

    is_all_same = (len(set(s_orig)) == 1)

    if is_all_same:
        assert count == 1, \
            f"Expected count 1 for all identical characters (S='{s_orig}', N={n}), got {count}."
    else:
        # For N=1, s_orig is always all_same. So this branch implies N > 1.
        # If N > 1 and not all chars are same, operations are possible.
        # Example: "AB" -> "C". So "AB", "C" are 2 distinct strings. Count is 2.
        assert count > 1, \
            f"Expected count > 1 for string with mixed characters (S='{s_orig}', N={n}), got {count}."


@given(make_input())
@settings(max_examples=50, deadline=None)
def test_output_format_and_range(stdin):
    """
    Checks if the output is a valid integer string and falls within the expected range.
    The problem asks for the count modulo (10^9+7), so the output should be in [0, 10^9+6].
    Since a string always counts as 1 (at least itself), the minimum is 1.
    """
    n_str, s_orig = stdin.split('\n')
    n = int(n_str)
    
    stdout = run_candidate(stdin)
    
    # Check if output is a valid non-negative integer string
    assert stdout.strip().isdigit(), f"Output '{stdout}' is not a valid non-negative integer string."
    
    count = int(stdout)
    
    MOD = 10**9 + 7
    
    # The count must be at least 1 (the original string is always reachable).
    assert count >= 1, f"Count {count} is less than 1 for input S='{s_orig}' (N={n})."
    
    # The count must be within the modulo range [1, MOD-1].
    assert count < MOD, \
        f"Count {count} is not less than MOD ({MOD}) for input S='{s_orig}' (N={n})."


@given(make_input())
@settings(max_examples=50, deadline=None)
def test_string_reversal_invariance(stdin):
    """
    Metamorphic test: The number of distinct strings should be invariant under
    reversing the input string `S`.
    The operation (`S_i \to Z, remove S_{i+1}`) applied to `S` and `reversed(S)`
    generates symmetric sets of reachable strings, thus the count should be identical.
    For example, `AB -> C` and `BA -> C`.
    """
    n_str, s_orig = stdin.split('\n')
    n = int(n_str)
    
    stdout_orig = run_candidate(stdin)
    count_orig = int(stdout_orig)

    s_reversed = s_orig[::-1] # Reverse the string
    stdin_reversed = f"{n}\n{s_reversed}"
    
    stdout_reversed = run_candidate(stdin_reversed)
    count_reversed = int(stdout_reversed)

    assert count_orig == count_reversed, \
        f"Reversal invariance failed for S='{s_orig}' (N={n}) and S_reversed='{s_reversed}'. " \
        f"Original count: {count_orig}, Reversed count: {count_reversed}."