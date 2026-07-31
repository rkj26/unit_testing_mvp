import random
import collections

def gen_input() -> str:
    parts = []

    # Choose strategy for N, M (dimensions of the labyrinth)
    strategy_nm = random.choice([
        "min", "max", "small_square", "medium_rect", "large_rect", "random_medium", "random_large",
        "thin_tall", "thin_wide", "small_for_bfs_check" # Specific strategy to target small grid BFS check
    ])

    if strategy_nm == "min":
        n, m = 1, 1
    elif strategy_nm == "max":
        n, m = 2000, 2000
    elif strategy_nm == "small_square":
        size = random.randint(1, 20)
        n, m = size, size
    elif strategy_nm == "medium_rect":
        n = random.randint(50, 500)
        m = random.randint(50, 500)
    elif strategy_nm == "large_rect":
        n = random.randint(1000, 2000)
        m = random.randint(1000, 2000)
    elif strategy_nm == "random_medium":
        n = random.randint(1, 100)
        m = random.randint(1, 100)
    elif strategy_nm == "random_large":
        n = random.randint(100, 2000)
        m = random.randint(100, 2000)
    elif strategy_nm == "thin_tall":
        n = random.randint(100, 2000)
        m = random.randint(1, 5)
    elif strategy_nm == "thin_wide":
        n = random.randint(1, 5)
        m = random.randint(100, 2000)
    elif strategy_nm == "small_for_bfs_check":
        # Target N*M up to 4000 for _check_small_grid_bfs to run
        max_dim = int(random.sqrt(4000)) # Approx 63
        n = random.randint(1, max_dim)
        m = random.randint(1, 4000 // n) if 4000 // n >= 1 else 1 # Ensure m is at least 1
    else: # Fallback (should be covered by random_large)
        n = random.randint(1, 2000)
        m = random.randint(1, 2000)
    
    parts.append(f"{n} {m}")

    # Choose r, c (starting row and column, 1-indexed)
    strategy_rc = random.choice(["corner", "center", "edge", "random"])
    if strategy_rc == "corner":
        r = random.choice([1, n])
        c = random.choice([1, m])
    elif strategy_rc == "center":
        r = n // 2 if n > 1 else 1
        c = m // 2 if m > 1 else 1
    elif strategy_rc == "edge":
        if random.random() < 0.5: # Top/Bottom edge
            r = random.choice([1, n])
            c = random.randint(1, m)
        else: # Left/Right edge
            r = random.randint(1, n)
            c = random.choice([1, m])
    else:
        r = random.randint(1, n)
        c = random.randint(1, m)
    parts.append(f"{r} {c}")

    # Choose x, y (max left/right moves)
    strategy_xy = random.choice([
        "min_zero", "max_unlimited", "small_tight", "medium_random", "just_enough_m", "unlimited_for_bfs_check", "one_zero_one_large"
    ])
    max_xy_val = 10**9 # Problem statement max x, y

    if strategy_xy == "min_zero":
        x, y = 0, 0
    elif strategy_xy == "max_unlimited":
        x, y = max_xy_val, max_xy_val 
    elif strategy_xy == "small_tight":
        x = random.randint(0, min(m * 2, 20)) # Cap at 20 to keep it really tight
        y = random.randint(0, min(m * 2, 20))
    elif strategy_xy == "medium_random":
        # Random up to a reasonable cap for typical movement patterns in a 2000x2000 grid
        x = random.randint(0, min(m * 2 + n * 2, 10000))
        y = random.randint(0, min(m * 2 + n * 2, 10000))
    elif strategy_xy == "just_enough_m":
        x_base = m - 1 if m > 0 else 0
        y_base = m - 1 if m > 0 else 0
        x = x_base + random.randint(0, min(max_xy_val - x_base, 5)) # Add small buffer
        y = y_base + random.randint(0, min(max_xy_val - y_base, 5))
    elif strategy_xy == "unlimited_for_bfs_check": # For the _check_unrestricted_bfs property
        # x, y should be large enough to cover any path in the grid. Max N*M is a safe bound.
        min_unlimited_val = n * m 
        x = random.randint(min_unlimited_val, max_xy_val) if min_unlimited_val < max_xy_val else max_xy_val
        y = random.randint(min_unlimited_val, max_xy_val) if min_unlimited_val < max_xy_val else max_xy_val
    elif strategy_xy == "one_zero_one_large":
        if random.random() < 0.5:
            x, y = 0, max_xy_val
        else:
            x, y = max_xy_val, 0
    else: # Fallback (should be covered by medium_random or max_unlimited)
        x = random.randint(0, max_xy_val)
        y = random.randint(0, max_xy_val)
    parts.append(f"{x} {y}")

    # Grid generation
    grid_rows = []
    start_r_idx, start_c_idx = r - 1, c - 1 # 0-indexed for internal use
    
    strategy_grid = random.choice([
        "all_free", "all_obstacles_except_start", "sparse_random", "dense_random",
        "checkerboard", "single_wall_h", "single_wall_v", "frame_obstacles", "random_paths_sparse"
    ])

    if strategy_grid == "all_free":
        for _ in range(n):
            grid_rows.append('.' * m)
    elif strategy_grid == "all_obstacles_except_start":
        for _ in range(n):
            grid_rows.append('*' * m)
        # Ensure start cell is free, even in 1x1 case
        grid_list = list(grid_rows[start_r_idx])
        grid_list[start_c_idx] = '.'
        grid_rows[start_r_idx] = "".join(grid_list)
    elif strategy_grid == "sparse_random":
        for i in range(n):
            row_chars = []
            for j in range(m):
                if i == start_r_idx and j == start_c_idx:
                    row_chars.append('.')
                else:
                    row_chars.append(random.choice(['.', '.', '.', '.', '.', '*', '*'])) # ~30% obstacles
            grid_rows.append("".join(row_chars))
    elif strategy_grid == "dense_random":
        for i in range(n):
            row_chars = []
            for j in range(m):
                if i == start_r_idx and j == start_c_idx:
                    row_chars.append('.')
                else:
                    row_chars.append(random.choice(['.', '*', '*', '*', '*', '*', '*'])) # ~85% obstacles
            grid_rows.append("".join(row_chars))
    elif strategy_grid == "checkerboard":
        for i in range(n):
            row_chars = []
            for j in range(m):
                if i == start_r_idx and j == start_c_idx:
                    row_chars.append('.')
                elif (i + j) % 2 == 0:
                    row_chars.append('.')
                else:
                    row_chars.append('*')
            grid_rows.append("".join(row_chars))
    elif strategy_grid == "single_wall_h": # Horizontal wall
        if n > 1: # Only place a horizontal wall if there's at least 2 rows
            wall_row = random.randint(0, n-1)
            # Try to place wall away from start if possible
            if n > 1 and wall_row == start_r_idx: 
                wall_row = (start_r_idx + 1) % n # Move to adjacent row
            
            for i in range(n):
                if i == wall_row:
                    grid_rows.append('*' * m)
                else:
                    grid_rows.append('.' * m)
        else: # Fallback for N=1 (no meaningful horizontal wall)
            for _ in range(n): grid_rows.append('.' * m)
    elif strategy_grid == "single_wall_v": # Vertical wall
        if m > 1: # Only place a vertical wall if there's at least 2 columns
            wall_col = random.randint(0, m-1)
            # Try to place wall away from start if possible
            if m > 1 and wall_col == start_c_idx:
                wall_col = (start_c_idx + 1) % m # Move to adjacent column
            
            for i in range(n):
                row_chars = []
                for j in range(m):
                    if j == wall_col:
                        row_chars.append('*')
                    else:
                        row_chars.append('.')
                grid_rows.append("".join(row_chars))
        else: # Fallback for M=1 (no meaningful vertical wall)
            for _ in range(n): grid_rows.append('.' * m)
    elif strategy_grid == "frame_obstacles":
        if n > 2 and m > 2: # Frame requires at least 3x3 to make sense
            for i in range(n):
                if i == 0 or i == n - 1:
                    grid_rows.append('*' * m)
                else:
                    grid_rows.append('*' + '.' * (m - 2) + '*')
        else: # Fallback for small N or M
            for _ in range(n): grid_rows.append('.' * m)
    elif strategy_grid == "random_paths_sparse": # Create a path from start, mostly blocked otherwise
        temp_grid = [['*' for _ in range(m)] for _ in range(n)]
        
        temp_grid[start_r_idx][start_c_idx] = '.'
        
        current_path_r, current_path_c = start_r_idx, start_c_idx
        # Max path length 1000 cells to keep generation time reasonable for large grids
        num_path_steps = random.randint(min(n*m // 4, 10), min(n*m, 1000)) 
        
        for _ in range(num_path_steps):
            dr, dc = random.choice([(-1,0), (1,0), (0,-1), (0,1)])
            next_r, next_c = current_path_r + dr, current_path_c + dc
            
            if 0 <= next_r < n and 0 <= next_c < m:
                temp_grid[next_r][next_c] = '.'
                current_path_r, current_path_c = next_r, next_c
        
        # Add some very sparse random free cells to allow for alternative paths/connectivity
        for i in range(n):
            for j in range(m):
                if temp_grid[i][j] == '*' and random.random() < 0.02: # 2% chance to be free
                    temp_grid[i][j] = '.'

        for r_str_list in temp_grid:
            grid_rows.append("".join(r_str_list))
    else: # Fallback to sparse random for any unhandled grid strategy
        for i in range(n):
            row_chars = []
            for j in range(m):
                if i == start_r_idx and j == start_c_idx:
                    row_chars.append('.')
                else:
                    row_chars.append(random.choice(['.', '.', '.', '*', '*'])) # ~40% obstacles
            grid_rows.append("".join(row_chars))

    # Ensure start cell is free (redundant with current logic but good defensive programming)
    grid_list = list(grid_rows[start_r_idx])
    grid_list[start_c_idx] = '.'
    grid_rows[start_r_idx] = "".join(grid_list)

    parts.extend(grid_rows)
    return "\n".join(parts) + "\n"

# Helper function to parse input for check
def _parse_input_for_check(stdin_str):
    lines = stdin_str.strip().split('\n')
    n, m = map(int, lines[0].split())
    r, c = map(int, lines[1].split())
    x, y = map(int, lines[2].split())
    grid = [list(line) for line in lines[3:]]
    return n, m, r, c, x, y, grid

# Helper function for small grid verification (two 0-1 BFS implementations)
def _check_small_grid_bfs(n, m, r, c, x, y, grid) -> int:
    start_r, start_c = r - 1, c - 1 # Convert to 0-indexed

    # BFS for min_left_moves_used
    min_left_moves = [[float('inf')] * m for _ in range(n)]
    q_left = collections.deque()

    min_left_moves[start_r][start_c] = 0
    q_left.append((start_r, start_c))

    while q_left:
        curr_r, curr_c = q_left.popleft()
        l_cost = min_left_moves[curr_r][curr_c]

        # Define movement directions and their associated left_move cost
        # (dr, dc, l_cost_increase, push_to_front_of_deque)
        moves = [
            (-1, 0, 0, True), # Up: 0 cost, high priority
            ( 1, 0, 0, True), # Down: 0 cost, high priority
            ( 0, -1, 1, False), # Left: 1 cost, low priority
            ( 0,  1, 0, True)  # Right: 0 cost, high priority
        ]

        for dr, dc, l_inc, push_front in moves:
            nr, nc = curr_r + dr, curr_c + dc
            new_l_cost = l_cost + l_inc

            if (0 <= nr < n and 0 <= nc < m and grid[nr][nc] == '.' and 
                new_l_cost < min_left_moves[nr][nc]):
                min_left_moves[nr][nc] = new_l_cost
                if push_front:
                    q_left.appendleft((nr, nc))
                else:
                    q_left.append((nr, nc))

    # BFS for min_right_moves_used
    min_right_moves = [[float('inf')] * m for _ in range(n)]
    q_right = collections.deque()

    min_right_moves[start_r][start_c] = 0
    q_right.append((start_r, start_c))

    while q_right:
        curr_r, curr_c = q_right.popleft()
        r_cost = min_right_moves[curr_r][curr_c]

        # Define movement directions and their associated right_move cost
        # (dr, dc, r_cost_increase, push_to_front_of_deque)
        moves = [
            (-1, 0, 0, True), # Up: 0 cost, high priority
            ( 1, 0, 0, True), # Down: 0 cost, high priority
            ( 0, -1, 0, True), # Left: 0 cost, high priority
            ( 0,  1, 1, False)  # Right: 1 cost, low priority
        ]

        for dr, dc, r_inc, push_front in moves:
            nr, nc = curr_r + dr, curr_c + dc
            new_r_cost = r_cost + r_inc

            if (0 <= nr < n and 0 <= nc < m and grid[nr][nc] == '.' and 
                new_r_cost < min_right_moves[nr][nc]):
                min_right_moves[nr][nc] = new_r_cost
                if push_front:
                    q_right.appendleft((nr, nc))
                else:
                    q_right.append((nr, nc))

    # Count reachable cells that satisfy both budget constraints
    reachable_count = 0
    for i in range(n):
        for j in range(m):
            if min_left_moves[i][j] <= x and min_right_moves[i][j] <= y:
                reachable_count += 1
    
    return reachable_count

# Helper function for unrestricted BFS (standard BFS ignoring x, y budget limits)
def _check_unrestricted_bfs(n, m, r, c, grid) -> int:
    start_r, start_c = r - 1, c - 1 # Convert to 0-indexed
    
    q = collections.deque()
    visited = [[False] * m for _ in range(n)]
    
    # Problem guarantees start cell is free
    q.append((start_r, start_c))
    visited[start_r][start_c] = True
    count = 1

    while q:
        curr_r, curr_c = q.popleft()

        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]: # Up, Down, Left, Right
            nr, nc = curr_r + dr, curr_c + dc
            if (0 <= nr < n and 0 <= nc < m and grid[nr][nc] == '.' and 
                not visited[nr][nc]):
                visited[nr][nc] = True
                q.append((nr, nc))
                count += 1
    return count


def check(stdin: str, stdout: str) -> None:
    # 1. Parse input from stdin
    n, m, r, c, x, y, grid = _parse_input_for_check(stdin)

    # 2. Parse output from stdout and perform basic sanity checks
    try:
        actual_count = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout}'")

    assert actual_count >= 1, f"Expected at least 1 reachable cell (start cell is always reachable and free), but got {actual_count}"
    assert actual_count <= n * m, f"Reachable cells count {actual_count} exceeds total cells {n*m}"

    # 3. Property 1: Small Grid Verification
    # For small grids (N*M up to 4000), we can run a full, correct 0-1 BFS solver
    # and compare its result with the program's output.
    if n * m <= 4000:
        expected_count = _check_small_grid_bfs(n, m, r, c, x, y, grid)
        assert actual_count == expected_count, \
            f"Small grid (N={n}, M={m}, N*M={n*m}): Expected {expected_count} reachable cells, but program output {actual_count}"

    # 4. Property 2: Unrestricted BFS for Large Budgets
    # If the allowed left and right moves (x, y) are sufficiently large (e.g., >= total cells N*M),
    # the budget constraints should not limit reachability. In this case, the problem reduces
    # to a standard BFS on the grid.
    # The max value for N*M is 2000*2000 = 4,000,000. If x, y are >= this, they are effectively unlimited.
    if x >= n * m and y >= n * m:
        unrestricted_count = _check_unrestricted_bfs(n, m, r, c, grid)
        assert actual_count == unrestricted_count, \
            f"Large budgets (x={x}, y={y} >= N*M={n*m}): Expected {unrestricted_count} reachable cells (via unrestricted BFS), but program output {actual_count}"