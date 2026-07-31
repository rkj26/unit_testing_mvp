import random

def _parse_input(stdin: str):
    """
    Parses the stdin string to extract H, W, the grid, S and T coordinates, and 'o' count.
    Raises ValueError if S or T are not found (should not happen with valid inputs).
    """
    lines = stdin.strip().split('\n')
    H, W = map(int, lines[0].split())
    grid_chars = [list(line) for line in lines[1:]]

    s_coords = None
    t_coords = None
    o_count = 0
    
    for r in range(H):
        for c in range(W):
            if grid_chars[r][c] == 'S':
                s_coords = (r, c)
            elif grid_chars[r][c] == 'T':
                t_coords = (r, c)
            elif grid_chars[r][c] == 'o':
                o_count += 1
    
    if s_coords is None or t_coords is None:
        # This condition should not be met if gen_input produces valid input
        raise ValueError("S or T not found in input, which violates problem constraints.")
        
    return H, W, grid_chars, s_coords, t_coords, o_count

def gen_input() -> str:
    """
    Generates a single, valid input string for the problem.
    Covers various edge cases and random scenarios.
    """
    H = random.randint(2, 100)
    W = random.randint(2, 100)

    grid = [['.' for _ in range(W)] for _ in range(H)]

    # Initial random S, T placement (might be overwritten by specific patterns)
    s_r, s_c = random.randint(0, H - 1), random.randint(0, W - 1)
    t_r, t_c = random.randint(0, H - 1), random.randint(0, W - 1)
    while s_r == t_r and s_c == t_c: # Ensure S and T are distinct
        t_r, t_c = random.randint(0, H - 1), random.randint(0, W - 1)
    
    # Choose a pattern for the grid generation to cover various scenarios
    pattern_choice = random.randint(0, 8) # Increased range for more diverse patterns

    if pattern_choice == 0: # S and T directly connected (forced -1 case)
        # Ensure S and T are on the same row or column but distinct
        if random.random() < 0.5: # Same row
            t_r = s_r
            temp_c = random.randint(0, W - 1)
            while temp_c == s_c: temp_c = random.randint(0, W - 1)
            t_c = temp_c
        else: # Same column
            t_c = s_c
            temp_r = random.randint(0, H - 1)
            while temp_r == s_r: temp_r = random.randint(0, H - 1)
            t_r = temp_r
        grid[s_r][s_c] = 'S'
        grid[t_r][t_c] = 'T'
        # Fill remaining cells with random 'o's or '.'s
        for r_idx in range(H):
            for c_idx in range(W):
                if grid[r_idx][c_idx] == '.':
                    grid[r_idx][c_idx] = 'o' if random.random() < 0.5 else '.'
    
    elif pattern_choice == 1: # No 'o' leaves at all (answer 0 or -1)
        grid[s_r][s_c] = 'S'
        grid[t_r][t_c] = 'T'
        # All other cells remain '.' (initialized state)
    
    elif pattern_choice == 2: # Exactly one 'o' leaf (simple path/no path check)
        o_r, o_c = random.randint(0, H - 1), random.randint(0, W - 1)
        while (o_r, o_c) == (s_r, s_c) or (o_r, o_c) == (t_r, t_c):
            o_r, o_c = random.randint(0, H - 1), random.randint(0, W - 1)
        grid[o_r][o_c] = 'o'
        grid[s_r][s_c] = 'S'
        grid[t_r][t_c] = 'T'
        # Fill remaining with mostly '.' (sparse overall)
        for r_idx in range(H):
            for c_idx in range(W):
                if grid[r_idx][c_idx] == '.':
                    if random.random() < 0.05: # Very low chance of other 'o's
                        grid[r_idx][c_idx] = 'o'
        
    elif pattern_choice == 3: # S and T are far apart (e.g., corners), high 'o' density
        s_r, s_c = 0, 0
        t_r, t_c = H-1, W-1
        # Adjust for small grids to ensure S and T are distinct if H or W is small
        if H == 2 and W == 2:
            s_r, s_c = 0, 0
            t_r, t_c = 1, 1
        elif H == 2 and W > 2:
            s_r, s_c = 0, 0
            t_r, t_c = 1, W-1
        elif W == 2 and H > 2:
            s_r, s_c = 0, 0
            t_r, t_c = H-1, 1
            
        grid[s_r][s_c] = 'S'
        grid[t_r][t_c] = 'T'
        # Fill almost all other cells with 'o'
        for r_idx in range(H):
            for c_idx in range(W):
                if grid[r_idx][c_idx] == '.':
                    grid[r_idx][c_idx] = 'o' if random.random() < 0.9 else '.'

    elif pattern_choice == 4: # Sparse 'o' leaves
        grid[s_r][s_c] = 'S'
        grid[t_r][t_c] = 'T'
        num_o_to_place = random.randint(0, min(H * W - 2, 10)) # Small number of 'o's
        for _ in range(num_o_to_place):
            r_idx, c_idx = random.randint(0, H - 1), random.randint(0, W - 1)
            while grid[r_idx][c_idx] != '.':
                r_idx, c_idx = random.randint(0, H - 1), random.randint(0, W - 1)
            grid[r_idx][c_idx] = 'o'
            
    elif pattern_choice == 5: # Dense 'o' leaves
        grid[s_r][s_c] = 'S'
        grid[t_r][t_c] = 'T'
        for r_idx in range(H):
            for c_idx in range(W):
                if grid[r_idx][c_idx] == '.':
                    grid[r_idx][c_idx] = 'o' if random.random() < 0.8 else '.' # High chance of 'o'
                    
    else: # Default cases (pattern_choice 6, 7, 8): Moderate 'o' density
        grid[s_r][s_c] = 'S'
        grid[t_r][t_c] = 'T'
        for r_idx in range(H):
            for c_idx in range(W):
                if grid[r_idx][c_idx] == '.':
                    grid[r_idx][c_idx] = 'o' if random.random() < 0.3 else '.' # Moderate chance
    
    # Format the grid into the final input string
    output = f"{H} {W}\n"
    for r_idx in range(H):
        output += "".join(grid[r_idx]) + "\n"
    return output

def check(stdin: str, stdout: str) -> None:
    """
    Verifies properties of the program's output against the input.
    """
    # Parse program output
    try:
        output_val = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout}'")

    # Parse input to extract necessary information
    H, W, grid_chars, s_coords, t_coords, o_count = _parse_input(stdin)
    s_r, s_c = s_coords
    t_r, t_c = t_coords

    # Property 1: Output format and range
    # The output must be an integer >= -1.
    assert output_val >= -1, f"Output {output_val} must be >= -1."
    
    # If the output is not -1, it must be non-negative.
    if output_val != -1:
        assert output_val >= 0, f"Output {output_val} must be non-negative if not -1."
        # The number of leaves to remove cannot exceed the total number of 'o' leaves available.
        assert output_val <= o_count, \
            f"Output {output_val} must be <= total 'o' leaves ({o_count})."

    # Property 2: S and T are directly connected
    # If S and T are in the same row or column, the frog can jump directly between them.
    # Since S and T cannot be removed, it's impossible to disconnect them.
    if s_r == t_r or s_c == t_c:
        assert output_val == -1, \
            f"S at {s_coords} and T at {t_coords} are directly connected (same row/column). " \
            f"Expected -1, but got {output_val}."

    # Property 3: No 'o' leaves in the grid
    # If there are no 'o' leaves, then S and T can only be connected directly.
    # If they are directly connected, Property 2 applies.
    # If they are NOT directly connected, and no 'o' leaves exist, then they MUST be disconnected.
    if o_count == 0:
        if not (s_r == t_r or s_c == t_c): # S and T are not directly connected
            assert output_val == 0, \
                f"No 'o' leaves in the grid and S {s_coords}, T {t_coords} are not directly connected. " \
                f"Expected 0, but got {output_val}."
    
    # Property 4: Exactly one 'o' leaf in the grid
    # This checks a simple path/no path scenario that should be easy for a correct solution.
    if o_count == 1 and output_val != -1: # Already handled if output_val == -1 due to S/T direct connection.
        # Find the single 'o' leaf's coordinates
        o_coords = None
        for r_idx in range(H):
            for c_idx in range(W):
                if grid_chars[r_idx][c_idx] == 'o':
                    o_coords = (r_idx, c_idx)
                    break
            if o_coords: break
        
        # Determine if S can reach 'o', and 'o' can reach T
        # (S,o) connection: same row OR same column
        s_to_o = (s_r == o_coords[0] or s_c == o_coords[1])
        # (o,T) connection: same row OR same column
        o_to_t = (o_coords[0] == t_r or o_coords[1] == t_c)
        
        if s_to_o and o_to_t:
            # If both S->o and o->T connections exist, then removing this 'o' leaf is necessary
            # and sufficient to disconnect S from T. So, the answer should be 1.
            assert output_val == 1, \
                f"Single 'o' leaf at {o_coords} forms a path S {s_coords} -> o -> T {t_coords}. " \
                f"Expected 1, but got {output_val}."
        else:
            # If no path S->o->T exists, then S and T are disconnected (since there are no other 'o's).
            # The answer should be 0.
            assert output_val == 0, \
                f"Single 'o' leaf at {o_coords} does not connect S {s_coords} and T {t_coords}. " \
                f"Expected 0, but got {output_val}."