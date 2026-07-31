import random

def gen_input() -> str:
    # 6 <= N <= 400
    # 0 <= C_i,j <= 999

    # Predefined sample/edge cases to ensure coverage for specific scenarios
    # These will be chosen with a lower probability than random generation.
    specific_tests = [
        # Sample 1
        (6, [[0, 1, 2, 3], [0, 4, 6, 1], [1, 6, 7, 2], [2, 7, 5, 3], [6, 4, 5, 7], [4, 0, 3, 5]]),
        # Sample 2
        (8, [[0, 0, 0, 0], [0, 0, 1, 1], [0, 1, 0, 1], [0, 1, 1, 0], [1, 0, 0, 1], [1, 0, 1, 0], [1, 1, 0, 0], [1, 1, 1, 1]]),
        # Sample 3: N=6, all identical tiles (0 0 0 0) - important for exact value check
        (6, [[0, 0, 0, 0]] * 6),
        # N=7, all identical tiles (0 0 0 0) - important for exact value check
        (7, [[0, 0, 0, 0]] * 7),
        # N=400 (max N), all identical tiles (0 0 0 0) - stresses large P(N,6)
        (400, [[0, 0, 0, 0]] * 400),
        # N=6, all distinct colors (hard to match)
        (6, [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11], [12, 13, 14, 15], [16, 17, 18, 19], [20, 21, 22, 23]]),
        # N=6, all corners distinct on each tile, but using few distinct colors overall
        (6, [[0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3]]),
        # N=6, tile patterns with rotation symmetry (e.g. 0 1 0 1)
        (6, [[0, 1, 0, 1], [0, 1, 0, 1], [0, 1, 0, 1], [0, 1, 0, 1], [0, 1, 0, 1], [0, 1, 0, 1]]),
        (6, [[0, 0, 1, 1], [0, 0, 1, 1], [0, 0, 1, 1], [0, 0, 1, 1], [0, 0, 1, 1], [0, 0, 1, 1]]),
    ]

    # Approximately 15% chance to pick a specific test case
    if random.random() < 0.15:
        n_val, tiles_data = random.choice(specific_tests)
        s = f"{n_val}\n"
        for tile in tiles_data:
            s += " ".join(map(str, tile)) + "\n"
        return s

    # General random generation
    N = random.randint(6, 400)
    tiles = []

    # Randomly select a strategy for generating tile colors
    strategy_choice = random.random()

    if strategy_choice < 0.2: # 20% chance: All N tiles are identical, all 4 corners same color
        color_val = random.randint(0, 999)
        tile_pattern = [color_val] * 4
        for _ in range(N):
            tiles.append(tile_pattern)
    elif strategy_choice < 0.4: # 20% chance: All N tiles are identical, but corners might differ (e.g., 0 1 2 3)
        tile_pattern = [random.randint(0, 999) for _ in range(4)]
        for _ in range(N):
            tiles.append(tile_pattern)
    elif strategy_choice < 0.7: # 30% chance: Few unique tile patterns, repeated
        num_unique_patterns = random.randint(1, min(N, 10)) # Max 10 unique patterns
        unique_patterns = []
        for _ in range(num_unique_patterns):
            unique_patterns.append([random.randint(0, 999) for _ in range(4)])
        
        for _ in range(N):
            tiles.append(random.choice(unique_patterns))
    else: # 30% chance: Mostly distinct or fully random tiles
        for _ in range(N):
            tile_colors = [random.randint(0, 999) for _ in range(4)]
            tiles.append(tile_colors)

    # Format into STDIN string
    s = f"{N}\n"
    for tile in tiles:
        s += " ".join(map(str, tile)) + "\n"
    return s

def check(stdin: str, stdout: str) -> None:
    # 1. Output Format and Value Range
    try:
        result = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not an integer: '{stdout}'")

    if result < 0:
        raise AssertionError(f"Output must be non-negative, but got {result}")

    # 2. Specific Case Check: All N tiles are identical AND all 4 corners of each tile are the same color.
    # This scenario yields a deterministic, easily verifiable exact count.
    # Parse stdin to extract N and tile data.
    lines = stdin.strip().split('\n')
    N = int(lines[0])
    tile_data = []
    for i in range(1, N + 1):
        tile_data.append(list(map(int, lines[i].split())))

    is_all_identical_corners_same_color = True
    if N < 6: # Minimum N for cube construction is 6
        is_all_identical_corners_same_color = False
    else:
        # Check if the first tile has all 4 corners painted with the same color
        first_tile_pattern = tile_data[0]
        if not (first_tile_pattern[0] == first_tile_pattern[1] == 
                first_tile_pattern[2] == first_tile_pattern[3]):
            is_all_identical_corners_same_color = False
        else:
            # Check if all other tiles are identical to the first tile (including color pattern)
            for i in range(1, N):
                if tile_data[i] != first_tile_pattern:
                    is_all_identical_corners_same_color = False
                    break
    
    # If the specific condition is met, calculate the expected result and assert it.
    # In this scenario, any 6 distinct tiles out of N can be chosen, assigned to faces, 
    # and oriented in any way, as all corner conditions will be met due to identical colors.
    # The counting is P(N, 6) * 4^6 / 24.
    if is_all_identical_corners_same_color:
        # P(N, 6) = N * (N-1) * (N-2) * (N-3) * (N-4) * (N-5)
        P_N_6 = 1
        for i in range(6):
            P_N_6 *= (N - i)
        
        FOUR_POW_6 = 4**6 # 4^6 = 4096
        
        # The total number of fixed-orientation, fixed-face assignments is P(N,6) * 4^6.
        # We divide by 24 for the rotational symmetry of the cube.
        expected_result = (P_N_6 * FOUR_POW_6) // 24 # Use integer division
        
        if result != expected_result:
            raise AssertionError(
                f"For N={N} tiles where all tiles are identical and all corners "
                f"of each tile have the same color, expected {expected_result}, but got {result}"
            )