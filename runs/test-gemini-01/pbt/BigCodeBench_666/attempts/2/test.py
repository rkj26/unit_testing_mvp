# SEARCH PLAN:
# 1. Boundary: Empty string, single character string, all positive/negative weights.
# 2. Subsequence Validity: Ensure the output is always a valid subsequence of the input.
# 3. Maximality (Metamorphic): Check that removing a negative-weight character from the result does not increase its weight (unless it's the only char).
# 4. Maximality (Metamorphic): Check that the result's weight is at least zero if any positive-weight character exists in the input.
# 5. Maximality (Reference): Compare against a simple, known-correct brute-force for small inputs to ensure global optimality.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import math
from collections import Counter
from itertools import combinations # Required by problem statement, though not used in tests directly.

# Helper to calculate the weight of a subsequence
def calculate_weight(subsequence, letter_weight_dict):
    return sum(letter_weight_dict.get(char, 0) for char in subsequence)

# Helper to find all subsequences (for reference implementation)
def get_all_subsequences(seq):
    subsequences = set()
    for i in range(1 << len(seq)): # Iterate through all possible combinations
        sub = ""
        for j in range(len(seq)):
            if (i >> j) & 1:
                sub += seq[j]
        subsequences.add(sub)
    return sorted(list(subsequences)) # Sort for deterministic order in testing, though not strictly needed for max weight

# Strategy for characters and weights, ensuring all chars in seq are in dict
@st.composite
def sequences_and_weights(draw, min_seq_len=0, max_seq_len=12):
    alphabet = draw(st.text(st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=5, unique=True))
    
    # Draw a specific length for the sequence within the allowed range
    seq_len = draw(st.integers(min_value=min_seq_len, max_value=max_seq_len))
    seq = draw(st.text(st.sampled_from(alphabet), min_size=seq_len, max_size=seq_len))
    
    # Ensure weights are diverse, including negative, zero, and positive
    weights = draw(st.dictionaries(
        st.sampled_from(alphabet),
        st.integers(min_value=-10, max_value=10),
        min_size=len(alphabet),
        max_size=len(alphabet)
    ))
    return seq, weights

# Strategy for sequences with only positive weights
@st.composite
def sequences_and_positive_weights(draw, min_seq_len=0, max_seq_len=12):
    alphabet = draw(st.text(st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=5, unique=True))
    
    seq_len = draw(st.integers(min_value=min_seq_len, max_value=max_seq_len))
    seq = draw(st.text(st.sampled_from(alphabet), min_size=seq_len, max_size=seq_len))
    
    weights = draw(st.dictionaries(
        st.sampled_from(alphabet),
        st.integers(min_value=1, max_value=10), # All positive weights
        min_size=len(alphabet),
        max_size=len(alphabet)
    ))
    return seq, weights

# Strategy for sequences with only negative weights (or zero for empty string case)
@st.composite
def sequences_and_negative_weights(draw, min_seq_len=0, max_seq_len=12):
    alphabet = draw(st.text(st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=5, unique=True))
    
    seq_len = draw(st.integers(min_value=min_seq_len, max_value=max_seq_len))
    seq = draw(st.text(st.sampled_from(alphabet), min_size=seq_len, max_size=seq_len))
    
    weights = draw(st.dictionaries(
        st.sampled_from(alphabet),
        st.integers(min_value=-10, max_value=-1), # All negative weights
        min_size=len(alphabet),
        max_size=len(alphabet)
    ))
    return seq, weights


@settings(max_examples=50, deadline=None)
@given(seq_and_weights=st.one_of(
    st.just(('', {})), # Empty string
    st.builds(lambda c: (c, {c: 1}), st.characters(min_codepoint=97, max_codepoint=122)), # Single char
    sequences_and_positive_weights(min_seq_len=2, max_seq_len=12) # Longer sequences with positive weights
))
def test_empty_and_all_positive_weights(seq_and_weights):
    """
    SPEC BASIS: "Find the subsequence in a string that has the maximum total weight."
                Example 1: `task_func('abc', {'a': 1, 'b': 2, 'c': 3})` -> `'abc'`
    PROPERTY: If the input sequence is empty, the output is an empty string.
              If all characters in `seq` have positive weights, the returned subsequence must be `seq` itself.
    STRATEGY: Target empty string, single-character string, and sequences where all character weights are positive.
              An empty string is a boundary case; all positive weights test the simplest "include everything" logic.
    """
    seq, letter_weight_dict = seq_and_weights
    try:
        result = task_func(seq, letter_weight_dict)
    except Exception:
        result = None
    
    assert result is not None, f"Function raised an exception for input seq='{seq}', weights={letter_weight_dict}"

    if not seq:
        assert result == '', f"Expected empty string for empty input, got '{result}'"
    else:
        # If all weights are positive, the entire sequence should be the max weight subsequence
        assert result == seq, f"For seq='{seq}' with positive weights, expected '{seq}', got '{result}'"
        # Also check that the weight is indeed the sum of all characters
        expected_weight = calculate_weight(seq, letter_weight_dict)
        actual_weight = calculate_weight(result, letter_weight_dict)
        assert actual_weight == expected_weight, \
            f"Weight mismatch for seq='{seq}': expected {expected_weight}, got {actual_weight} for '{result}'"


@settings(max_examples=50, deadline=None)
@given(seq_and_weights=sequences_and_negative_weights(min_seq_len=1, max_seq_len=12))
def test_all_negative_weights(seq_and_weights):
    """
    SPEC BASIS: "Find the subsequence in a string that has the maximum total weight."
    PROPERTY: If all characters in `seq` have negative weights, the returned subsequence must be the single
              character from `seq` that has the highest (least negative) weight.
              Any combination of two or more negative weights will result in a sum that is more negative (smaller)
              than any single negative weight.
    STRATEGY: Generate sequences where all character weights are negative. This tests the logic for finding
              the "least bad" option when all choices are detrimental.
    """
    seq, letter_weight_dict = seq_and_weights
    try:
        result = task_func(seq, letter_weight_dict)
    except Exception:
        result = None
    
    assert result is not None, f"Function raised an exception for input seq='{seq}', weights={letter_weight_dict}"
    assert len(result) > 0, f"Result should not be empty for non-empty input with negative weights: '{seq}'"

    # Find the character with the highest (least negative) weight
    max_char = ''
    max_weight = -math.inf
    for char in seq:
        weight = letter_weight_dict.get(char, 0)
        if weight > max_weight:
            max_weight = weight
            max_char = char
    
    # The result should be a single character, and its weight should be the max_weight found
    assert len(result) == 1, f"Expected single character result for all negative weights, got '{result}' for seq='{seq}'"
    assert result in seq, f"Result character '{result}' not found in original sequence '{seq}'"
    assert calculate_weight(result, letter_weight_dict) == max_weight, \
        f"Weight mismatch for seq='{seq}': expected {max_weight} for '{max_char}', got {calculate_weight(result, letter_weight_dict)} for '{result}'"


@settings(max_examples=50, deadline=None)
@given(seq_and_weights=sequences_and_weights(min_seq_len=0, max_seq_len=12))
def test_output_is_valid_subsequence_and_non_decreasing_weight_on_negative_removal(seq_and_weights):
    """
    SPEC BASIS: "Find the subsequence in a string that has the maximum total weight."
                "a subsequence is a sequence that can be derived from another sequence by deleting some elements
                without changing the order of the remaining elements."
    PROPERTY: The returned string must be a valid subsequence of the input `seq`.
              If the returned subsequence `R` contains a character `c` with a negative weight,
              then removing `c` from `R` (to get `R'`) should result in `R'` having a weight
              less than or equal to `R`, UNLESS `c` is the only character in `R` and `R` is the best possible subsequence.
              This implies that a negative-weight character should only be included if it enables a larger sum later.
    STRATEGY: Generate diverse sequences with mixed positive, negative, and zero weights.
              This tests the core logic of selecting characters to maximize weight and ensures local optimality.
    """
    seq, letter_weight_dict = seq_and_weights
    try:
        result = task_func(seq, letter_weight_dict)
    except Exception:
        result = None
    
    assert result is not None, f"Function raised an exception for input seq='{seq}', weights={letter_weight_dict}"
    
    # Property 1: `result` must be a subsequence of `seq`
    i = 0
    j = 0
    while i < len(seq) and j < len(result):
        if seq[i] == result[j]:
            j += 1
        i += 1
    assert j == len(result), f"'{result}' is not a subsequence of '{seq}'"

    # Property 2: Metamorphic check for negative weight characters
    original_result_weight = calculate_weight(result, letter_weight_dict)

    if not result: # If result is empty, no characters to remove
        return

    for i in range(len(result)):
        char_to_remove = result[i]
        char_weight = letter_weight_dict.get(char_to_remove, 0)

        if char_weight < 0:
            subsequence_without_char = result[:i] + result[i+1:]
            weight_without_char = calculate_weight(subsequence_without_char, letter_weight_dict)

            # If removing a negative-weight character leads to a higher weight,
            # and the original result was not just that single character,
            # then the original result was suboptimal.
            # Exception: if `result` was just `char_to_remove` (e.g., 'a' with weight -1, and it's the best option).
            if len(result) > 1 and weight_without_char > original_result_weight:
                assert False, (
                    f"Suboptimal result for seq='{seq}', weights={letter_weight_dict}. "
                    f"Returned '{result}' (weight {original_result_weight}). "
                    f"Removing '{char_to_remove}' (weight {char_weight}) yields '{subsequence_without_char}' (weight {weight_without_char}), "
                    f"which is higher. This implies '{result}' was not the maximum weight subsequence."
                )
            elif len(result) == 1 and weight_without_char > original_result_weight:
                # If the result was a single negative character, and removing it (resulting in empty string, weight 0)
                # gives a higher weight, it means the empty string would have been better.
                # However, the problem implies finding a subsequence, and for non-empty input, an empty string
                # might not be considered a valid return if there are other options.
                # If all characters are negative, the single least negative char is the correct answer.
                # If there are positive chars, and the result is a single negative char, it's wrong.
                # This case is covered by the brute-force test.
                pass # This specific case is acceptable if the single negative char is the best non-empty option.


@settings(max_examples=50, deadline=None)
@given(seq_and_weights=sequences_and_weights(min_seq_len=0, max_seq_len=12))
def test_result_weight_is_at_least_zero_if_possible(seq_and_weights):
    """
    SPEC BASIS: "Find the subsequence in a string that has the maximum total weight."
    PROPERTY: If the input sequence `seq` contains at least one character with a positive weight,
              then the returned subsequence's total weight must be greater than or equal to zero.
              If all characters in `seq` have zero or negative weights, this property does not apply.
    STRATEGY: Generate diverse sequences with mixed weights. This catches implementations that
              incorrectly return a negative total weight when a non-negative one is achievable
              (e.g., by simply returning an empty string or a single positive-weight character).
    """
    seq, letter_weight_dict = seq_and_weights
    try:
        result = task_func(seq, letter_weight_dict)
    except Exception:
        result = None
    
    assert result is not None, f"Function raised an exception for input seq='{seq}', weights={letter_weight_dict}"

    original_result_weight = calculate_weight(result, letter_weight_dict)

    # Check if any character in the original sequence has a positive weight
    has_positive_char = any(letter_weight_dict.get(c, 0) > 0 for c in seq)

    if has_positive_char:
        # If there's a positive character, it's always possible to form a subsequence with non-negative weight
        # (e.g., by taking just that positive character, or the empty string if all are negative but empty is allowed).
        # The problem implies finding the maximum, so if positive weights exist, the max should be >= 0.
        assert original_result_weight >= 0, \
            f"For seq='{seq}' with positive weight chars, expected result weight >= 0, got {original_result_weight} for '{result}'"


@settings(max_examples=50, deadline=None)
@given(seq_and_weights=sequences_and_weights(min_seq_len=0, max_seq_len=8)) # Keep seq_len small for brute force
def test_global_optimality_against_brute_force(seq_and_weights):
    """
    SPEC BASIS: "Find the subsequence in a string that has the maximum total weight."
                Example: `task_func('aabc', {'a': 10, 'b': -5, 'c': 3})` -> `'aac'`
    PROPERTY: The returned subsequence must have the absolute maximum total weight among all possible subsequences.
    STRATEGY: For small input sequences, generate all possible subsequences and calculate their weights
              to find the true maximum. Compare the function's result against this brute-force oracle.
              This is a strong check for global optimality.
    """
    seq, letter_weight_dict = seq_and_weights
    try:
        result = task_func(seq, letter_weight_dict)
    except Exception:
        result = None
    
    assert result is not None, f"Function raised an exception for input seq='{seq}', weights={letter_weight_dict}"

    # Brute-force calculation of the maximum weight
    all_subsequences = get_all_subsequences(seq)
    
    max_brute_force_weight = -math.inf
    best_brute_force_subsequence = ''

    # Handle empty string case explicitly for max_brute_force_weight
    if not seq:
        max_brute_force_weight = 0
        best_brute_force_subsequence = ''
    else:
        # If seq is not empty, consider all subsequences, including empty string (weight 0)
        # The problem implies returning a subsequence from the string, not necessarily non-empty.
        # However, the examples show non-empty results for non-empty inputs.
        # Let's assume the empty string is a valid subsequence with weight 0.
        # If all characters have negative weights, the empty string might be the max.
        # But the example `task_func('aabc', {'a': 10, 'b': -5, 'c': 3})` -> 'aac' (weight 13)
        # The problem statement implies finding *the* subsequence, not necessarily non-empty.
        # Let's consider the empty string as a candidate for max weight.
        max_brute_force_weight = 0 # Empty string has weight 0
        best_brute_force_subsequence = ''

        for sub in all_subsequences:
            current_weight = calculate_weight(sub, letter_weight_dict)
            if current_weight > max_brute_force_weight:
                max_brute_force_weight = current_weight
                best_brute_force_subsequence = sub
            # If weights are equal, the problem does not specify tie-breaking.
            # So we only care about the maximum weight.

    actual_result_weight = calculate_weight(result, letter_weight_dict)

    assert actual_result_weight == max_brute_force_weight, \
        f"Weight mismatch for seq='{seq}', weights={letter_weight_dict}. " \
        f"Expected max weight {max_brute_force_weight} (e.g., from '{best_brute_force_subsequence}'), " \
        f"got {actual_result_weight} for '{result}'."

    # Additionally, ensure the result itself is a valid subsequence.
    # This is already covered by test_output_is_valid_subsequence_and_non_decreasing_weight_on_negative_removal,
    # but a quick check here doesn't hurt.
    i = 0
    j = 0
    while i < len(seq) and j < len(result):
        if seq[i] == result[j]:
            j += 1
        i += 1
    assert j == len(result), f"'{result}' is not a subsequence of '{seq}'"