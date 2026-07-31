import random
from collections import Counter

def gen_input() -> str:
    H = random.randint(1, 12)
    W = random.randint(1, 12)

    grid_type = random.choices([
        'random', 
        'already_symmetric', 
        'H1_not_palindromic', 
        'W1_impossible_symmetric',
        'all_same_char',
        'H1_palindromic', # Explicitly add H=1, palindromic for YES case
        'W1_possible_symmetric' # Explicitly add W=1, possible for YES case
    ], weights=[70, 5, 5, 5, 5, 5, 5], k=1)[0]
    
    initial_rows = []

    if grid_type == 'already_symmetric':
        # Generate a grid that is already symmetric
        grid_chars = [['' for _ in range(W)] for _ in range(H)]
        for r_idx in range(H):
            for c_idx in range(W):
                if grid_chars[r_idx][c_idx] == '': # If not yet filled by a symmetric copy
                    char = random.choice('abcdefghijklmnopqrstuvwxyz')
                    grid_chars[r_idx][c_idx] = char
                    grid_chars[H - 1 - r_idx][W - 1 - c_idx] = char
        initial_rows = ["".join(row) for row in grid_chars]

    elif grid_type == 'H1_not_palindromic':
        H = 1
        # Ensure W is at least 2 for non-palindromic string
        W = random.randint(2, 12)
        s = ''.join(random.choice('abcde') for _ in range(W)) # Use smaller alphabet for higher chance of non-palindrome
        # Ensure it's not palindromic
        attempts = 0
        while s == s[::-1] and attempts < 100: 
            s = ''.join(random.choice('abcde') for _ in range(W))
            attempts += 1
        if s == s[::-1]: # Fallback if too many attempts, just make first char different from last
             s_list = list(s)
             s_list[0] = random.choice('fghij')
             s = "".join(s_list)
        initial_rows = [s]
    
    elif grid_type == 'H1_palindromic':
        H = 1
        W = random.randint(1, 12)
        half_row = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range((W + 1) // 2))
        s = half_row + half_row[:W//2][::-1]
        initial_rows = [s]

    elif grid_type == 'W1_impossible_symmetric':
        W = 1
        # H must be even with > 0 odd counts OR H must be odd with > 1 odd counts
        # E.g., H even, all chars distinct
        H = random.choice([2, 4, 6, 8, 10, 12])
        if H > 26: H = 26 # Limit to alphabet size
        chars = random.sample('abcdefghijklmnopqrstuvwxyz', H) # All distinct characters
        initial_rows = [c for c in chars]
    
    elif grid_type == 'W1_possible_symmetric':
        W = 1
        # H even, all chars have even counts OR H odd, exactly one char has odd count
        H = random.randint(1, 12)
        chars_to_use = []
        if H % 2 == 1: # H is odd, need one char with odd count
            chars_to_use.append(random.choice('abcdefghijklmnopqrstuvwxyz'))
            H -= 1 # Remaining H must have even counts
        
        # Fill remaining H with pairs
        for _ in range(H // 2):
            char = random.choice('abcdefghijklmnopqrstuvwxyz')
            chars_to_use.append(char)
            chars_to_use.append(char)
        random.shuffle(chars_to_use)
        initial_rows = [c for c in chars_to_use]

    elif grid_type == 'all_same_char':
        char = random.choice('abcdefghijklmnopqrstuvwxyz')
        row_str = char * W
        initial_rows = [row_str] * H

    else: # 'random' case
        for _ in range(H):
            row = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(W))
            initial_rows.append(row)

    input_str = f"{H} {W}\n"
    input_str += '\n'.join(initial_rows) + '\n'
    return input_str

def check(stdin: str, stdout: str) -> None:
    # Helper function to reverse a string
    def rev_str_local(s):
        return s[::-1]

    # 1. Output format check
    if stdout not in ["YES\n", "NO\n"]:
        raise AssertionError(f"Output must be 'YES\\n' or 'NO\\n', got '{stdout}'")

    # Parse input
    lines = stdin.strip().split('\n')
    H, W = map(int, lines[0].split())
    initial_rows = lines[1:]

    # 2. Property: If the input grid is ALREADY symmetric, output MUST be YES.
    is_already_symmetric_input = True
    for i in range(H):
        for j in range(W):
            if initial_rows[i][j] != initial_rows[H - 1 - i][W - 1 - j]:
                is_already_symmetric_input = False
                break
        if not is_already_symmetric_input:
            break
    if is_already_symmetric_input:
        assert stdout == "YES\n", f"Input:\n{stdin}Expected: YES\\n (Input is already symmetric)\nGot: {stdout}"

    # 3. Property: If H=1:
    #    a) If the single row is NOT palindromic, output MUST be NO.
    #    b) If the single row IS palindromic, output MUST be YES.
    if H == 1:
        if initial_rows[0] != rev_str_local(initial_rows[0]):
            assert stdout == "NO\n", f"Input:\n{stdin}Expected: NO\\n (H=1 and row is not palindromic)\nGot: {stdout}"
        else:
            assert stdout == "YES\n", f"Input:\n{stdin}Expected: YES\\n (H=1 and row is palindromic)\nGot: {stdout}"

    # 4. Property: If W=1, check if the single column of characters can form a symmetric arrangement.
    # This means: if H is even, all characters in the column must have even counts.
    # If H is odd, exactly one character must have an odd count, and others even.
    if W == 1:
        col_chars = [initial_rows[i][0] for i in range(H)]
        char_counts = Counter(col_chars)
        odd_char_counts = sum(1 for count in char_counts.values() if count % 2 == 1)
        
        can_form_symmetric_col = True
        if H % 2 == 0: # H is even
            if odd_char_counts > 0: # All character counts must be even for symmetry
                can_form_symmetric_col = False
        else: # H is odd
            if odd_char_counts != 1: # Exactly one character must have an odd count for the middle element
                can_form_symmetric_col = False
        
        if can_form_symmetric_col:
            assert stdout == "YES\n", f"Input:\n{stdin}Expected: YES\\n (W=1 and column chars can form symmetric)\nGot: {stdout}"
        else:
            assert stdout == "NO\n", f"Input:\n{stdin}Expected: NO\\n (W=1 and column chars CANNOT form symmetric)\nGot: {stdout}"
    
    # 5. Property: If all input rows are identical:
    #    a) Output is YES iff the common row string is palindromic.
    #    b) Otherwise, output is NO.
    if len(set(initial_rows)) == 1: # All rows are identical
        if initial_rows[0] == rev_str_local(initial_rows[0]):
            assert stdout == "YES\n", f"Input:\n{stdin}Expected: YES\\n (All rows identical and palindromic)\nGot: {stdout}"
        else:
            assert stdout == "NO\n", f"Input:\n{stdin}Expected: NO\\n (All rows identical but not palindromic)\nGot: {stdout}"