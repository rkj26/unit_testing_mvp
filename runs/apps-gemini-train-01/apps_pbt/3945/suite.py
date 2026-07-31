import random
import io

def gen_input() -> str:
    """
    Generates a single input string for the problem.
    Covers various edge cases and random scenarios for n, m, and a_ij values.
    """
    
    # Choose a strategy for generating the input matrix
    strategy = random.choice([
        "min_dims_min_vals",        # n=1, m=1, a_ij=1
        "min_dims_max_vals",        # n=1, m=1, a_ij=10^9
        "min_dims_rand_vals",       # n,m small, a_ij small random
        "max_dims_min_vals",        # n=1000, m=1000, a_ij=1
        "max_dims_max_vals",        # n=1000, m=1000, a_ij=10^9
        "max_dims_rand_vals",       # n=1000, m=1000, a_ij large random
        "rand_dims_rand_vals",      # n,m random, a_ij large random
        "rand_dims_few_unique_vals", # n,m random, a_ij from a small pool of unique values
        "rand_dims_many_unique_vals",# n,m small (<=100), a_ij mostly unique
        "rand_dims_checkerboard",   # n,m random, a_ij alternating two values
        "rand_dims_diagonal_pattern",# n,m random, a_ij increasing along diagonals
        "rand_dims_row_pattern",    # n,m random, each row has a simple pattern
        "rand_dims_col_pattern",    # n,m random, each col has a simple pattern
    ])

    n, m = 0, 0
    A = []

    if strategy == "min_dims_min_vals":
        n, m = 1, 1
        A = [[1]]
    elif strategy == "min_dims_max_vals":
        n, m = 1, 1
        A = [[10**9]]
    elif strategy == "min_dims_rand_vals":
        n = random.randint(1, 5)
        m = random.randint(1, 5)
        A = [[random.randint(1, 100) for _ in range(m)] for _ in range(n)]
    elif strategy == "max_dims_min_vals":
        n, m = 1000, 1000
        A = [[1 for _ in range(m)] for _ in range(n)]
    elif strategy == "max_dims_max_vals":
        n, m = 1000, 1000
        A = [[10**9 for _ in range(m)] for _ in range(n)]
    elif strategy == "max_dims_rand_vals":
        n, m = 1000, 1000
        A = [[random.randint(1, 10**9) for _ in range(m)] for _ in range(n)]
    elif strategy == "rand_dims_rand_vals":
        n = random.randint(1, 1000)
        m = random.randint(1, 1000)
        A = [[random.randint(1, 10**9) for _ in range(m)] for _ in range(n)]
    elif strategy == "rand_dims_few_unique_vals":
        n = random.randint(1, 1000)
        m = random.randint(1, 1000)
        num_unique = random.randint(1, min(n * m, 50))  # Small number of unique values
        unique_vals_pool = random.sample(range(1, 10**9 + 1), num_unique)
        A = [[random.choice(unique_vals_pool) for _ in range(m)] for _ in range(n)]
    elif strategy == "rand_dims_many_unique_vals":
        n = random.randint(1, 100)  # Keep N, M relatively small for unique vals
        m = random.randint(1, 100)
        # Ensure values are mostly unique, up to N*M values
        all_vals_pool = random.sample(range(1, 10**9 + 1), n * m)
        k = 0
        A = []
        for r_idx in range(n):
            row = []
            for c_idx in range(m):
                row.append(all_vals_pool[k])
                k += 1
            A.append(row)
    elif strategy == "rand_dims_checkerboard":
        n = random.randint(1, 1000)
        m = random.randint(1, 1000)
        val1 = random.randint(1, 10**9 // 2)
        val2 = random.randint(val1 + 1, 10**9)
        A = [[(val1 if (r_idx + c_idx) % 2 == 0 else val2) for c_idx in range(m)] for r_idx in range(n)]
    elif strategy == "rand_dims_diagonal_pattern":
        n = random.randint(1, 1000)
        m = random.randint(1, 1000)
        start_val = random.randint(1, max(1, 10**9 - (n + m - 2)))
        A = [[(start_val + r_idx + c_idx) for c_idx in range(m)] for r_idx in range(n)]
    elif strategy == "rand_dims_row_pattern":
        n = random.randint(1, 1000)
        m = random.randint(1, 1000)
        A = []
        for r_idx in range(n):
            start_val = random.randint(1, max(1, 10**9 - (m - 1)))
            row = [(start_val + c_idx) for c_idx in range(m)]
            random.shuffle(row) # Shuffle to make it less obvious
            A.append(row)
    elif strategy == "rand_dims_col_pattern":
        n = random.randint(1, 1000)
        m = random.randint(1, 1000)
        A = [[0 for _ in range(m)] for _ in range(n)]
        for c_idx in range(m):
            start_val = random.randint(1, max(1, 10**9 - (n - 1)))
            col = [(start_val + r_idx) for r_idx in range(n)]
            random.shuffle(col) # Shuffle
            for r_idx in range(n):
                A[r_idx][c_idx] = col[r_idx]
    
    # Format the generated matrix into a string
    input_str = f"{n} {m}\n"
    for r_idx in range(n):
        input_str += " ".join(map(str, A[r_idx])) + "\n"
    return input_str


def check(stdin: str, stdout: str) -> None:
    """
    Verifies properties of the program's output based on the problem statement.
    Checks for:
    1. Correct output dimensions (N lines, M integers per line).
    2. Each output value x_ij is within the valid range [1, N + M - 1].
    3. For each cell (r, c), the output x_rc is at least the maximum of
       its 1-indexed rank in its row and its 1-indexed rank in its column.
       This is a critical lower bound certificate check.
    """
    
    # 1. Parse stdin
    input_lines = stdin.strip().split('\n')
    n, m = map(int, input_lines[0].split())
    
    A = []
    for i in range(1, n + 1):
        A.append(list(map(int, input_lines[i].split())))

    # 2. Parse stdout
    output_lines = stdout.strip().split('\n')

    # Format check 1: Number of lines
    assert len(output_lines) == n, f"Output has {len(output_lines)} lines, expected {n}"

    X = []
    for r_idx, line in enumerate(output_lines):
        try:
            row_X = list(map(int, line.split()))
            X.append(row_X)
        except ValueError:
            raise AssertionError(f"Output line {r_idx+1} is not space-separated integers: '{line}'")
        
        # Format check 2: Number of integers per line
        assert len(row_X) == m, f"Output line {r_idx+1} has {len(row_X)} integers, expected {m}"

    # Precompute all row ranks and column ranks for efficiency.
    # Each item in `row_unique_data` / `col_unique_data` is a tuple:
    # (sorted_unique_values_list, {value: 1-indexed_rank_map})
    row_unique_data = [] 
    for r in range(n):
        row_A_vals = A[r]
        unique_vals = sorted(list(set(row_A_vals)))
        rank_map = {val: unique_vals.index(val) + 1 for val in unique_vals}
        row_unique_data.append((unique_vals, rank_map))

    col_unique_data = [] 
    for c in range(m):
        col_A_vals = [A[k][c] for k in range(n)]
        unique_vals = sorted(list(set(col_A_vals)))
        rank_map = {val: unique_vals.index(val) + 1 for val in unique_vals}
        col_unique_data.append((unique_vals, rank_map))

    # 3. Range check and lower bound certificate check
    for r in range(n):
        for c in range(m):
            x_rc = X[r][c]

            # Range check: Each x_ij must be at least 1.
            # The maximum possible answer is n + m - 1 (e.g., if a[r][c] is minimal in its row but maximal in its column,
            # and all elements are distinct, then the rank can be 1 + (m-1) + (n-1) = n+m-1).
            assert 1 <= x_rc <= n + m - 1, \
                f"Output X[{r}][{c}] = {x_rc} is out of expected range [1, {n + m - 1}]"

            # Lower bound certificate check:
            # The new height for A[r][c] (let's call it H_rc) must be at least its 1-indexed rank
            # within its row (to keep all row elements >= 1) AND at least its 1-indexed rank
            # within its column (to keep all column elements >= 1).
            # The final answer x_rc is the *maximum* height used, which must be >= H_rc.
            # Thus, x_rc must be >= max(row_rank_of_A[r][c], col_rank_of_A[r][c]).

            # a) 1-indexed rank of A[r][c] in its row
            _, rank_R_map = row_unique_data[r]
            rank_R_val = rank_R_map[A[r][c]]

            # b) 1-indexed rank of A[r][c] in its column
            _, rank_C_map = col_unique_data[c]
            rank_C_val = rank_C_map[A[r][c]]

            assert x_rc >= max(rank_R_val, rank_C_val), \
                f"Output X[{r}][{c}] = {x_rc} violates lower bound: " \
                f"Expected >= max(row_rank={rank_R_val}, col_rank={rank_C_val}) " \
                f"for A[{r}][{c}] = {A[r][c]}"