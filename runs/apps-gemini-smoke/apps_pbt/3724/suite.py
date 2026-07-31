import random

def gen_input() -> str:
    """
    Generates a valid input string for the problem.
    Covers minimum/boundary N, extreme values, duplicates, and various string patterns.
    """
    N_choice = random.random()
    if N_choice < 0.02: # Minimum N
        N = 1
    elif N_choice < 0.05: # Small N
        N = random.randint(2, 10)
    elif N_choice < 0.15: # Medium N
        N = random.randint(11, 100)
    elif N_choice < 0.3: # Larger N
        N = random.randint(101, 10000)
    elif N_choice < 0.4: # Max N
        N = 10**6
    elif N_choice < 0.5: # N near max
        N = random.randint(10**6 - 100, 10**6)
    else: # Wide random N
        N = random.randint(1, 10**6)

    chars = ['A', 'B', 'C']
    s_list = []

    pattern_choice = random.random()
    if pattern_choice < 0.15: # All same character
        char = random.choice(chars)
        s_list = [char] * N
    elif pattern_choice < 0.3: # Alternating two characters
        c1, c2 = random.sample(chars, 2)
        s_list = [c1 if i % 2 == 0 else c2 for i in range(N)]
    elif pattern_choice < 0.4: # Alternating three characters (ABCABC...)
        for i in range(N):
            s_list.append(chars[i % 3])
    elif pattern_choice < 0.55: # Long blocks of two characters
        # Ensure block_len is at least 1, max N
        block_len = random.randint(1, N // 2 + 1 if N > 1 else 1)
        c1, c2 = random.sample(chars, 2)
        current_char = c1
        for i in range(N):
            if block_len > 0 and i % block_len == 0:
                current_char = c1 if current_char == c2 else c2
            s_list.append(current_char)
    elif pattern_choice < 0.7: # Long blocks of three characters
        # Ensure block_len is at least 1, max N
        block_len = random.randint(1, N // 3 + 1 if N > 1 else 1)
        current_char_idx = random.randint(0, 2) # Start with a random char index
        for i in range(N):
            if block_len > 0 and i % block_len == 0:
                current_char_idx = (current_char_idx + 1) % 3
            s_list.append(chars[current_char_idx])
    else: # Completely random characters
        for _ in range(N):
            s_list.append(random.choice(chars))

    S = "".join(s_list)
    return f"{N}\n{S}\n"

def check(stdin: str, stdout: str) -> None:
    """
    Asserts properties that the CORRECT output MUST satisfy.
    """
    N_str, S = stdin.splitlines()
    N = int(N_str)

    # 1. Output format and range check
    try:
        ans = int(stdout)
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout}'")

    MOD = 10**9 + 7
    assert 0 <= ans < MOD, \
        f"Output {ans} is out of expected modulo range [0, {MOD-1}]"

    # 2. Base cases: N=1 or all characters are the same
    # If N=1, no operations are possible. Only the initial string S is reachable. Count = 1.
    # If all characters in S are the same (e.g., "AAA"), no S_i != S_{i+1} exists.
    # Thus, no operations are possible. Only the initial string S is reachable. Count = 1.
    if N == 1 or len(set(S)) == 1:
        assert ans == 1, \
            f"Input S='{S}' (N={N}): expected 1 distinct string, but got {ans}. " \
            f"(Either N=1 or all characters are identical, implying no operations possible.)"
    # 3. General case: N > 1 and S contains different characters
    # If N > 1 and S contains at least two different characters, then S is reducible.
    # - The original string S itself is always one distinct reachable string.
    # - It is always possible to reduce S to a string of length 1 (a single character)
    #   by repeatedly applying the operation until only one character remains.
    #   Since N > 1, this length-1 string is necessarily distinct from the original string S.
    #   Therefore, there must be at least 2 distinct reachable strings.
    else:
        assert ans >= 2, \
            f"Input S='{S}' (N={N}): expected at least 2 distinct strings, but got {ans}. " \
            f"(N > 1 and S contains different characters, implying S is reducible and thus " \
            f"the initial string and a length-1 string are distinct reachable options.)"