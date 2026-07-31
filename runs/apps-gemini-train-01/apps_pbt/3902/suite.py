import random

def gen_input() -> str:
    # Length of string s (5 <= |s| <= 10^4)
    N = random.randint(5, 10000)

    # Scenarios to cover for aggressive exploration:
    # 1. Minimum length N=5
    # 2. Small N (e.g., 6-10)
    # 3. Medium N (e.g., 100-1000)
    # 4. Max N (10000)
    # 5. All same characters (e.g., "aaaaa...")
    # 6. Alternating characters (e.g., "ababab...")
    # 7. Random characters
    # 8. Strings designed to create specific suffix patterns at end (e.g., "ababa", "aaab", "abacabaca")
    # 9. Strings with very few possible suffixes (e.g., root takes up almost whole string)
    # 10. Strings designed to stress the "not allowed to append the same string twice in a row" rule
    # 11. String with many distinct 2-char and 3-char substrings
    # 12. String with few distinct 2-char and 3-char substrings
    
    choice = random.randint(0, 11)
    s_chars = []

    if choice == 0: # Minimum length N=5
        N = 5
        s_chars = [random.choice("abcdef") for _ in range(N)]
    elif choice == 1: # Small N (6-10)
        N = random.randint(6, 10)
        s_chars = [random.choice("abcdef") for _ in range(N)]
    elif choice == 2: # Medium N (100-1000)
        N = random.randint(100, 1000)
        s_chars = [random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(N)]
    elif choice == 3: # Max N (10000)
        N = 10000
        s_chars = [random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(N)]
    elif choice == 4: # All same characters
        N = random.randint(5, 100) # Keep N moderate for this pattern
        char = random.choice("ab")
        s_chars = [char] * N
    elif choice == 5: # Alternating characters
        N = random.randint(5, 100) # Keep N moderate
        char1 = random.choice("ab")
        char2 = random.choice("cd")
        while char1 == char2:
            char2 = random.choice("cd")
        s_chars = [char1 if i % 2 == 0 else char2 for i in range(N)]
    elif choice == 6: # General random characters
        s_chars = [random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(N)]
    elif choice == 7: # Specific suffix patterns at the end
        # Ensure minimum root length and then append specific suffix types
        root_len = random.randint(5, max(5, N - 5)) # Ensure space for at least 2 suffixes
        s_chars = [random.choice("xyz") for _ in range(root_len)]
        remaining_len = N - root_len
        
        # Possible endings: "ab", "ba", "abc", "bca", "aa", "bb", "aaa", "bbb"
        # Combine them to generate some sequences
        patterns = []
        if remaining_len >= 2: patterns.extend(["ab", "ba", "aa", "bb"])
        if remaining_len >= 3: patterns.extend(["abc", "bca", "aaa", "bbb"])
        if remaining_len >= 4: patterns.extend(["abab", "baba", "aaaa", "bbbb"]) # Stressing `mi != m(i+1)` with simple patterns
        
        if patterns:
            pattern = random.choice(patterns)
            s_chars.extend(list(pattern[:remaining_len]))
            s_chars.extend([random.choice("xyz") for _ in range(remaining_len - len(pattern))])
        else: # Fallback if remaining_len is too small for any pattern
            s_chars.extend([random.choice("xyz") for _ in range(remaining_len)])
    elif choice == 8: # Very few possible suffixes (root takes up almost whole string)
        N = random.randint(5, 100)
        # Root is N-2 or N-3 length, leaving only 1 suffix candidate
        root_len = random.randint(N - 3, N - 2) 
        if root_len < 5: root_len = 5 # Ensure root is at least 5
        s_chars = [random.choice("abc") for _ in range(root_len)]
        s_chars.extend([random.choice("de") for _ in range(N - root_len)])
    elif choice == 9: # Stressing "not allowed to append the same string twice in a row"
        N = random.randint(10, 200)
        s_chars = [random.choice("ab") for _ in range(N)] # e.g. "abababab", "aaaaaaab" etc.
        # Ensure N is large enough to potentially have repeated suffixes
        if N < 10: N = 10 
        s_chars = ['a', 'a', 'a', 'a', 'a'] # root
        current_len = 5
        while current_len < N - 3: # leave space for at least one suffix
            if random.random() < 0.5: # append length 2
                s_chars.extend(random.choice(["ab", "ba"]))
                current_len += 2
            else: # append length 3
                s_chars.extend(random.choice(["abc", "bac"]))
                current_len += 3
        s_chars = s_chars[:N] # Trim if exceeded, pad if too short
        while len(s_chars) < N:
            s_chars.append(random.choice("xy"))
    elif choice == 10: # Many distinct 2-char and 3-char substrings
        N = random.randint(500, 1000)
        s_chars = [chr(ord('a') + random.randint(0, 25)) for _ in range(N)]
    elif choice == 11: # Few distinct 2-char and 3-char substrings
        N = random.randint(500, 1000)
        s_chars = [random.choice("ab") for _ in range(N)]

    s = "".join(s_chars[:N]) # Ensure final length is N
    return s + '\n'

def check(stdin: str, stdout: str) -> None:
    s = stdin.strip()
    N = len(s)

    output_lines = stdout.strip().split('\n')
    
    # Property 1: Output format - first line is k, followed by k lines of suffixes
    if not output_lines:
        raise AssertionError("Output is empty.")
    
    try:
        k = int(output_lines[0])
    except ValueError:
        raise AssertionError("First line must be an integer k.")

    # Property 2: Total number of lines must be k + 1
    if len(output_lines) != k + 1:
        raise AssertionError(f"Expected {k+1} lines (k for count + k suffixes), got {len(output_lines)}.")

    actual_suffixes = output_lines[1:]
    
    # Property 3: Number of suffixes matches k
    if len(actual_suffixes) != k:
        raise AssertionError(f"Declared k={k} but found {len(actual_suffixes)} suffixes.")

    # If k is 0, no further suffix properties apply
    if k == 0:
        return

    # Properties 4, 5, 6: Suffix format (length 2 or 3, lowercase English), distinctness, lexicographical order
    seen_suffixes = set()
    for i, suffix in enumerate(actual_suffixes):
        # Property 4: Suffix length
        if not (2 <= len(suffix) <= 3):
            raise AssertionError(f"Suffix '{suffix}' at line {i+2} has invalid length {len(suffix)} (expected 2 or 3).")
        
        # Property 5: Suffix characters
        if not all('a' <= char <= 'z' for char in suffix):
            raise AssertionError(f"Suffix '{suffix}' at line {i+2} contains non-lowercase English letters.")
        
        # Property 6: Distinctness
        if suffix in seen_suffixes:
            raise AssertionError(f"Duplicate suffix '{suffix}' found at line {i+2}.")
        seen_suffixes.add(suffix)

        # Property 7: Lexicographical order (checked against previous suffix)
        if i > 0 and suffix < actual_suffixes[i-1]:
            raise AssertionError(f"Suffix '{suffix}' at line {i+2} is not in lexicographical order (preceded by '{actual_suffixes[i-1]}').")

    # Property 8: Each output suffix must be a substring of 's' and must have at least one occurrence
    # that starts at or after index 5.
    # Reasoning: A word is constructed as `root + m1 + m2 + ... + mk`, where `len(root) >= 5`.
    # Any morpheme `mi` must therefore start at an index `j` such that `j >= len(root) >= 5`.
    # This implies that for any valid morpheme `X`, there must be an occurrence `s[j:j+len(X)] == X` where `j >= 5`.
    # This does not mean *all* occurrences of `X` must be at `j >= 5`, only that at least one such valid `j` exists.
    for suffix_str in actual_suffixes:
        found_valid_occurrence = False
        L = len(suffix_str)
        for j in range(N - L + 1):
            if s[j:j+L] == suffix_str:
                if j >= 5: # This occurrence starts after a potential root of min length 5
                    found_valid_occurrence = True
                    break
        if not found_valid_occurrence:
            raise AssertionError(f"Suffix '{suffix_str}' is claimed, but no occurrence starts at index 5 or later in the input string '{s}'.")

    # Further properties related to the "not allowed to append the same string twice in a row" rule
    # and the full decomposition validity are typically implemented using dynamic programming.
    # Such implementations would often constitute re-solving the problem, which is explicitly
    # discouraged by the problem statement for `check`.
    # The current set of checks covers format, basic string properties, ordering, uniqueness,
    # and a crucial structural constraint (minimum root length implications on suffix positions).
    # These properties are sound (i.e., every correct solution must satisfy them) and efficient
    # (running in O(N + K*L) time, where L is max suffix length, for most checks).