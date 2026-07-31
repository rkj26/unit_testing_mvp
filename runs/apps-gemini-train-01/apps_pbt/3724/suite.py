import random

def gen_input() -> str:
    # N must be between 1 and 10^6
    N_choices = [1, 2, 3, 4, 5, 10, 50, 100, 1000, 10000, 100000, 1000000]
    # Small N are important for known patterns, large N for performance/overflow.
    # N is chosen from a list to ensure boundary and medium values are well-represented.
    N = random.choice(N_choices)
    
    chars = ['A', 'B', 'C']
    S_list = []

    # Generate S by choosing a pattern type, then filling characters.
    # This aggressive exploration aims to hit rare divergent cases.
    pattern_type = random.random()
    
    # 1. Monochromatic strings (e.g., "AAA...")
    if pattern_type < 0.15: # 15% chance
        S_list = [random.choice(chars)] * N
    # 2. Alternating two characters (e.g., "ABAB...")
    elif pattern_type < 0.30: # 15% chance
        char1 = random.choice(chars)
        char2 = random.choice([c for c in chars if c != char1])
        S_list = [char1 if i % 2 == 0 else char2 for i in range(N)]
    # 3. Alternating three characters (e.g., "ABCABC...")
    elif pattern_type < 0.45: # 15% chance
        c_perm = random.sample(chars, 3) # Random permutation of A,B,C
        S_list = [c_perm[i % 3] for i in range(N)]
    # 4. Strings with distinct long runs of characters (e.g., "AAAABBBCC")
    elif pattern_type < 0.60: # 15% chance
        num_blocks = random.randint(1, min(N, 3)) # 1 to 3 distinct blocks
        block_chars = random.sample(chars, num_blocks) # Choose unique characters for blocks
        
        block_lengths = [0] * num_blocks
        remaining_N = N
        # Assign lengths such that each block has at least 1 character
        for i in range(num_blocks - 1):
            block_lengths[i] = random.randint(1, remaining_N - (num_blocks - i - 1))
            remaining_N -= block_lengths[i]
        block_lengths[num_blocks - 1] = remaining_N # Last block gets remaining length
        
        random.shuffle(block_chars) # Randomize order of blocks' characters
        
        for i in range(num_blocks):
            S_list.extend([block_chars[i]] * block_lengths[i])
        
    # 5. Short random string (up to N=100)
    elif pattern_type < 0.75 and N <= 100: # 15% chance if N is small
        S_list = [random.choice(chars) for _ in range(N)]
    # 6. General random string (default for remaining cases and larger N)
    else:
        S_list = [random.choice(chars) for _ in range(N)]
            
    S = "".join(S_list)
    return f"{N}\n{S}\n"

def check(stdin: str, stdout: str) -> None:
    # Parse input
    parts = stdin.strip().split('\n')
    N = int(parts[0])
    S = parts[1]

    # Property 1: Output format and range
    try:
        count = int(stdout)
    except ValueError:
        raise AssertionError(f"Output is not an integer: '{stdout}'")

    modulo = 10**9 + 7
    # The count should be between 0 and modulo-1 (inclusive) as it's a modulo result.
    # A true count of `modulo` would result in `0`.
    assert 0 <= count < modulo, f"Output {count} is not within [0, {modulo-1}]"

    # For small N (1, 2, 3), the actual count is always less than `modulo`.
    # Therefore, the output count must be positive for these cases.
    if N <= 3:
         assert count > 0, f"For N={N}, actual count is small and positive, so modulo result {count} must also be positive."

    # Property 2: Monochromatic strings (e.g., "AAA...") always yield 1 distinct string.
    # No operations are possible if all characters are the same.
    if all(c == S[0] for c in S):
        assert count == 1, f"Monochromatic string '{S}' should yield 1 distinct string, but got {count}"
        return # No further specific N-checks needed for this type

    # Property 3: Specific checks for N=2, non-monochromatic strings.
    # Example: S = "AB". Possible strings: {"AB", "C"}. Count = 2.
    if N == 2:
        # Since monochromatic strings are handled above, this only applies to non-monochromatic.
        assert count == 2, f"For non-monochromatic string '{S}' of N=2, expected 2 distinct strings, but got {count}"
        return

    # Property 4: Specific checks for N=3, various patterns.
    if N == 3:
        # Case 4.1: S[0] == S[2] and S[0] != S[1] (e.g., "ABA", "BCB", "CAC")
        # Example "ABA":
        #   - Operation (S_0, S_1) on A,B -> C. String becomes "CA".
        #     - Operation (S_0, S_1) on C,A -> B. String becomes "B".
        #   - Operation (S_1, S_2) on B,A -> C. String becomes "AC".
        #     - Operation (S_0, S_1) on A,C -> B. String becomes "B".
        # Reachable distinct strings: {"ABA", "CA", "AC", "B"}. Count = 4.
        if S[0] == S[2] and S[0] != S[1]:
            assert count == 4, f"For '{S}' (type ABA, N=3), expected 4, got {count}"
            return
        
        # Case 4.2: S[0] == S[1] and S[1] != S[2] (e.g., "AAB", "BBC", "CCA")
        # Example "AAB":
        #   - Operation (S_1, S_2) on A,B -> C. String becomes "AC".
        #     - Operation (S_0, S_1) on A,C -> B. String becomes "B".
        # Reachable distinct strings: {"AAB", "AC", "B"}. Count = 3.
        # (S_0, S_1) cannot operate as S_0 == S_1.
        elif S[0] == S[1] and S[1] != S[2]:
            assert count == 3, f"For '{S}' (type AAB, N=3), expected 3, got {count}"
            return
        
        # Case 4.3: S[1] == S[2] and S[0] != S[1] (e.g., "ABB", "BCC", "CAA") - mirror of AAB
        # Example "ABB":
        #   - Operation (S_0, S_1) on A,B -> C. String becomes "CB".
        #     - Operation (S_0, S_1) on C,B -> A. String becomes "A".
        # Reachable distinct strings: {"ABB", "CB", "A"}. Count = 3.
        # (S_1, S_2) cannot operate as S_1 == S_2.
        elif S[1] == S[2] and S[0] != S[1]:
            assert count == 3, f"For '{S}' (type ABB, N=3), expected 3, got {count}"
            return

        # Case 4.4: S[0], S[1], S[2] are all distinct (e.g., "ABC", "BCA", "CAB")
        # Example "ABC":
        #   - Operation (S_0, S_1) on A,B -> C. String becomes "CC".
        #   - Operation (S_1, S_2) on B,C -> A. String becomes "AA".
        # Reachable distinct strings: {"ABC", "CC", "AA"}. Count = 3.
        elif S[0] != S[1] and S[1] != S[2] and S[0] != S[2]:
            assert count == 3, f"For '{S}' (type ABC, N=3), expected 3, got {count}"
            return
    
    # Property 5: Sample case check.
    # While generally not a property, confirming sample behavior helps validate the test setup.
    if N == 5 and S == "ABAAC":
        assert count == 11, f"Sample case '{S}', N=5, expected 11, got {count}"
        return

    # No further general, sound properties are obvious without re-solving the problem
    # or relying on metamorphic relations that require running the program multiple times
    # with transformed inputs, which is outside the scope of this `check` function.
    # The extensive `gen_input` combined with these small N checks should cover many common backdoors.