import random
import collections

def gen_input() -> str:
    # Aggressively cover constraints and edge cases to maximize chances of finding backdoors.
    # Test types aim to cover minimum/maximum dimensions, all-black/all-white grids,
    # specific failure conditions, and varying numbers of connected components.
    test_type = random.choice([
        "min_dims", "max_dims", "small_random", "medium_random", "large_random",
        "all_black", "all_white", "single_black", "single_white",
        "contiguous_violation_row", "contiguous_violation_col",
        "empty_row_no_empty_col_violation", "empty_col_no_empty_row_violation",
        "empty_row_and_empty_col_ok", "all_black_zigzag", "sparse_black",
        "large_rect_component", "many_small_components", "cross_shape"
    ])

    if test_type == "min_dims":
        n, m = 1, 1
    elif test_type == "max_dims":
        n, m = 1000, 1000
    elif test_type == "small_random":
        n, m = random.randint(1, 10), random.randint(1, 10)
    elif test_type == "medium_random":
        n, m = random.randint(50, 200), random.randint(50, 200)
    elif test_type == "large_random":
        n, m = random.randint(800, 1000), random.randint(800, 1000)
    elif test_type == "all_black":
        n, m = random.randint(1, 100), random.randint(1, 100)
        grid_chars = [['#' for _ in range(m)] for _ in range(n)]
        return f"{n} {m}\n" + "\n".join("".join(row) for row in grid_chars)
    elif test_type == "all_white":
        n, m = random.randint(1, 100), random.randint(1, 100)
        grid_chars = [['.' for _ in range(m)] for _ in range(n)]
        return f"{n} {m}\n" + "\n".join("".join(row) for row in grid_chars)
    elif test_type == "single_black":
        n, m = random.randint(1, 100), random.randint(1, 100)
        grid_chars = [['.' for _ in range(m)] for _ in range(n)]
        grid_chars[random.randint(0, n-1)][random.randint(0, m-1)] = '#'
        return f"{n} {m}\n" + "\n".join("".join(row) for row in grid_chars)
    elif test_type == "single_white":
        n, m = random.randint(1, 100), random.randint(1, 100)
        grid_chars = [['#' for _ in range(m)] for _ in range(n)]
        grid_chars[random.randint(0, n-1)][random.randint(0, m-1)] = '.'
        return f"{n} {m}\n" + "\n".join("".join(row) for row in grid_chars)
    elif test_type == "contiguous_violation_row":
        n, m = random.randint(3, 100), random.randint(3, 100)
        grid_chars = [['.' for _ in range(m)] for _ in range(n)]
        r = random.randint(0, n-1)
        c_vals = sorted(random.sample(range(m), min(m, 3)))
        if len(c_vals) < 3: # Ensure enough columns for non-contiguous
            c_vals = [0, m // 2, m - 1]
        grid_chars[r][c_vals[0]] = '#'
        grid_chars[r][c_vals[2]] = '#' # .#.#.
        # Ensure other rows/cols don't trigger other -1 conditions too easily
        for i in range(n):
            if i != r:
                grid_chars[i][random.randint(0, m-1)] = '#'
        for j in range(m):
            if grid_chars[r][j] == '.':
                # Try to ensure columns have some black cells
                grid_chars[random.choice([x for x in range(n) if x != r])][j] = '#'

        return f"{n} {m}\n" + "\n".join("".join(row) for row in grid_chars)
    elif test_type == "contiguous_violation_col":
        n, m = random.randint(3, 100), random.randint(3, 100)
        grid_chars = [['.' for _ in range(m)] for _ in range(n)]
        c = random.randint(0, m-1)
        r_vals = sorted(random.sample(range(n), min(n, 3)))
        if len(r_vals) < 3: # Ensure enough rows for non-contiguous
            r_vals = [0, n // 2, n - 1]
        grid_chars[r_vals[0]][c] = '#'
        grid_chars[r_vals[2]][c] = '#' # #.#
        # Ensure other rows/cols don't trigger other -1 conditions too easily
        for j in range(m):
            if j != c:
                grid_chars[random.randint(0, n-1)][j] = '#'
        for i in range(n):
            if grid_chars[i][c] == '.':
                # Try to ensure rows have some black cells
                grid_chars[i][random.choice([x for x in range(m) if x != c])] = '#'
        return f"{n} {m}\n" + "\n".join("".join(row) for row in grid_chars)
    elif test_type == "empty_row_no_empty_col_violation":
        n, m = random.randint(2, 100), random.randint(1, 100)
        grid_chars = [['.' for _ in range(m)] for _ in range(n)]
        empty_row_idx = random.randint(0, n-1)
        # Ensure one row is entirely empty (white)
        for c in range(m): grid_chars[empty_row_idx][c] = '.'
        # Ensure all columns have at least one black cell
        for j in range(m):
            r = random.choice([x for x in range(n) if x != empty_row_idx])
            grid_chars[r][j] = '#'
        # Fill remaining black cells sparsely, trying to maintain contiguous property
        for r_idx in range(n):
            if r_idx != empty_row_idx:
                for c_idx in range(m):
                    if random.random() < 0.1: # Sparse black cells
                        grid_chars[r_idx][c_idx] = '#'

        return f"{n} {m}\n" + "\n".join("".join(row) for row in grid_chars)
    elif test_type == "empty_col_no_empty_row_violation":
        n, m = random.randint(1, 100), random.randint(2, 100)
        grid_chars = [['.' for _ in range(m)] for _ in range(n)]
        empty_col_idx = random.randint(0, m-1)
        # Ensure one col is entirely empty (white)
        for r in range(n): grid_chars[r][empty_col_idx] = '.'
        # Ensure all rows have at least one black cell
        for i in range(n):
            c = random.choice([x for x in range(m) if x != empty_col_idx])
            grid_chars[i][c] = '#'
        # Fill remaining black cells sparsely
        for r_idx in range(n):
            for c_idx in range(m):
                if c_idx != empty_col_idx:
                    if random.random() < 0.1: # Sparse black cells
                        grid_chars[r_idx][c_idx] = '#'

        return f"{n} {m}\n" + "\n".join("".join(row) for row in grid_chars)
    elif test_type == "empty_row_and_empty_col_ok":
        n, m = random.randint(2, 100), random.randint(2, 100)
        grid_chars = [['.' for _ in range(m)] for _ in range(n)]
        empty_row_idx = random.randint(0, n-1)
        empty_col_idx = random.randint(0, m-1)
        # Ensure one row and one column are empty
        for c in range(m): grid_chars[empty_row_idx][c] = '.'
        for r in range(n): grid_chars[r][empty_col_idx] = '.'
        # Place some black cells outside the empty row/col
        for _ in range(random.randint(1, min(10, n * m // 5))): # Place a few black cells
            r, c = random.randint(0, n-1), random.randint(0, m-1)
            if r != empty_row_idx and c != empty_col_idx:
                grid_chars[r][c] = '#'
        return f"{n} {m}\n" + "\n".join("".join(row) for row in grid_chars)
    elif test_type == "all_black_zigzag":
        n, m = random.randint(5, 100), random.randint(5, 100)
        grid_chars = [['.' for _ in range(m)] for _ in range(n)]
        curr_r, curr_c = 0, 0
        grid_chars[curr_r][curr_c] = '#'
        # Create a single connected component that spans the grid
        while curr_r < n-1 or curr_c < m-1:
            move_r = curr_r < n-1 and (random.random() < 0.5 or curr_c == m-1)
            move_c = curr_c < m-1 and (random.random() < 0.5 or curr_r == n-1)
            if move_r and move_c:
                if random.random() < 0.5: curr_r += 1
                else: curr_c += 1
            elif move_r: curr_r += 1
            elif move_c: curr_c += 1
            else: break # Should not happen if n, m > 0
            grid_chars[curr_r][curr_c] = '#'
        return f"{n} {m}\n" + "\n".join("".join(row) for row in grid_chars)
    elif test_type == "sparse_black":
        n, m = random.randint(10, 100), random.randint(10, 100)
        grid_chars = [['.' for _ in range(m)] for _ in range(n)]
        # Add some black cells, trying to create multiple small components
        num_black = random.randint(n+m, n*m // 10)
        for _ in range(num_black):
            r, c = random.randint(0, n-1), random.randint(0, m-1)
            grid_chars[r][c] = '#'
        return f"{n} {m}\n" + "\n".join("".join(row) for row in grid_chars)
    elif test_type == "large_rect_component":
        n, m = random.randint(10, 100), random.randint(10, 100)
        grid_chars = [['.' for _ in range(m)] for _ in range(n)]
        r1, r2 = sorted(random.sample(range(n), 2))
        c1, c2 = sorted(random.sample(range(m), 2))
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                grid_chars[r][c] = '#'
        return f"{n} {m}\n" + "\n".join("".join(row) for row in grid_chars)
    elif test_type == "many_small_components":
        n, m = random.randint(10, 100), random.randint(10, 100)
        grid_chars = [['.' for _ in range(m)] for _ in range(n)]
        # Place many small (1x1 or 1x2 or 2x1) components
        num_components = random.randint(1, min(n, m) * 2)
        for _ in range(num_components):
            r, c = random.randint(0, n-1), random.randint(0, m-1)
            if grid_chars[r][c] == '.': # Only try to place if cell is free
                grid_chars[r][c] = '#'
                if random.random() < 0.3 and c + 1 < m and grid_chars[r][c+1] == '.':
                    grid_chars[r][c+1] = '#'
                elif random.random() < 0.3 and r + 1 < n and grid_chars[r+1][c] == '.':
                    grid_chars[r+1][c] = '#'
        return f"{n} {m}\n" + "\n".join("".join(row) for row in grid_chars)
    elif test_type == "cross_shape":
        n, m = random.randint(5, 100), random.randint(5, 100)
        grid_chars = [['.' for _ in range(m)] for _ in range(n)]
        center_r, center_c = n // 2, m // 2
        for r in range(n): grid_chars[r][center_c] = '#'
        for c in range(m): grid_chars[center_r][c] = '#'
        return f"{n} {m}\n" + "\n".join("".join(row) for row in grid_chars)
    else: # Default random case
        n, m = random.randint(1, 1000), random.randint(1, 1000)
        grid_chars = [['.' if random.random() < 0.5 else '#' for _ in range(m)] for _ in range(n)]
        return f"{n} {m}\n" + "\n".join("".join(row) for row in grid_chars)


def check(stdin: str, stdout: str) -> None:
    input_lines = stdin.strip().split('\n')
    n, m = map(int, input_lines[0].split())
    grid = [list(line) for line in input_lines[1:]]

    try:
        ans = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout}'")

    # Assert output format and range
    assert ans >= -1, f"Output '{ans}' is less than -1."

    # --- Pre-computation for checks ---
    has_black_in_row = [False] * n
    has_black_in_col = [False] * m
    black_cells = []
    for r in range(n):
        for c in range(m):
            if grid[r][c] == '#':
                has_black_in_row[r] = True
                has_black_in_col[c] = True
                black_cells.append((r, c))

    num_empty_rows = sum(1 for r in range(n) if not has_black_in_row[r])
    num_empty_cols = sum(1 for c in range(m) if not has_black_in_col[c])

    # --- Property 1 & 2: Black cells in any row/column must form a single contiguous segment ---
    # This prevents an N magnet from making a white cell reachable by moving "past" it.
    for r in range(n):
        first_hash_idx = -1
        last_hash_idx = -1
        for c in range(m):
            if grid[r][c] == '#':
                if first_hash_idx == -1:
                    first_hash_idx = c
                last_hash_idx = c
        if first_hash_idx != -1: # If row has any black cells
            for c in range(first_hash_idx, last_hash_idx + 1):
                assert grid[r][c] == '#', \
                    f"Row {r} has non-contiguous black cells. Expected '#' at (r={r}, c={c}) but found '{grid[r][c]}'. Grid:\n{stdin}"

    for c in range(m):
        first_hash_idx = -1
        last_hash_idx = -1
        for r in range(n):
            if grid[r][c] == '#':
                if first_hash_idx == -1:
                    first_hash_idx = r
                last_hash_idx = r
        if first_hash_idx != -1: # If column has any black cells
            for r in range(first_hash_idx, last_hash_idx + 1):
                assert grid[r][c] == '#', \
                    f"Column {c} has non-contiguous black cells. Expected '#' at (r={r}, c={c}) but found '{grid[r][c]}'. Grid:\n{stdin}"

    # --- Property 3: Impossible conditions related to empty rows/columns ---
    # If a row has no black cells but all columns have black cells, it's impossible.
    # Because an S magnet must be placed in that empty row (at a white cell).
    # Then an N magnet in an adjacent column (which has a black cell) could be drawn to that S,
    # making the white cells on path reachable. Symmetrically for columns.
    is_impossible_by_empty_rule = False
    if (num_empty_rows > 0 and num_empty_cols == 0) or \
       (num_empty_cols > 0 and num_empty_rows == 0):
        is_impossible_by_empty_rule = True

    if is_impossible_by_empty_rule:
        assert ans == -1, \
            f"Expected -1 due to empty row/col rule (num_empty_rows={num_empty_rows}, num_empty_cols={num_empty_cols}), but got {ans}. Grid:\n{stdin}"
        return # If it's impossible by this rule, no further checks are needed.

    # --- Certificate Check: If a solution exists, minimum N magnets = number of connected components ---
    
    # If there are no black cells, 0 N magnets are required.
    if not black_cells:
        assert ans == 0, f"Expected 0 magnets for an all-white grid, but got {ans}. Grid:\n{stdin}"
        return

    # Otherwise, compute the number of connected components of black cells.
    # This value is the minimum number of N magnets if a solution exists.
    visited = set()
    num_components = 0
    q = collections.deque()

    for r_start, c_start in black_cells:
        if (r_start, c_start) not in visited:
            num_components += 1
            q.append((r_start, c_start))
            visited.add((r_start, c_start))

            while q:
                r, c = q.popleft()
                # Check 4-directional neighbors
                for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < n and 0 <= nc < m and grid[nr][nc] == '#' and (nr, nc) not in visited:
                        visited.add((nr, nc))
                        q.append((nr, nc))
    
    # Assert that the program's answer (if not -1) matches our computed number of components.
    # This check is performed only if the impossibility rules (P1, P2, P3) did not flag -1.
    assert ans == num_components, \
        f"Expected {num_components} magnets (connected components of black cells), but got {ans}. Grid:\n{stdin}"