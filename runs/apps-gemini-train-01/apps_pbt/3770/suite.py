import random
import itertools

# Assume _run_program_on_input is provided by the test harness.
# It takes a string representing STDIN input and returns a string representing STDOUT output.
# Example usage:
# stdout_str = _run_program_on_input(stdin_str)

def _gen_graph_edges(N, M):
    """
    Helper to generate M unique edges for N vertices.
    Ensures no self-loops and no multiple edges.
    Tries to create a connected graph if M >= N-1.
    Returns a sorted list of (u, v) tuples (u < v).
    """
    edges = set()
    if N <= 1:
        return []

    all_possible_edges = []
    for i in range(1, N + 1):
        for j in range(i + 1, N + 1):
            all_possible_edges.append((i, j))

    random.shuffle(all_possible_edges)

    # If M is large enough, try to ensure connectivity first
    if M >= N - 1:
        # Generate a spanning tree (path graph for simplicity)
        temp_edges = set()
        for i in range(1, N):
            temp_edges.add(tuple(sorted((i, i + 1))))
        
        # Add remaining edges from all_possible_edges
        remaining_edges_to_add = M - len(temp_edges)
        
        for edge in all_possible_edges:
            if edge not in temp_edges:
                temp_edges.add(edge)
                remaining_edges_to_add -= 1
            if remaining_edges_to_add <= 0:
                break
        edges = temp_edges
    else:
        # For sparse graphs or small M, just pick random edges
        for i in range(min(M, len(all_possible_edges))):
            edges.add(all_possible_edges[i])
            
    return sorted(list(edges))

def gen_input() -> str:
    N = random.randint(1, 300)
    M_max_possible = N * (N - 1) // 2
    M = random.randint(0, min(300, M_max_possible))

    A_vals = [random.randint(1, 10**6) for _ in range(N)]
    B_vals = [random.randint(-10**6, 10**6) for _ in range(N)]
    
    # --- Special N, M scenarios ---
    scenario_type = random.choices(
        ['random', 'N_1_M_0', 'small_N_M', 'large_N_M_0', 'large_N_M_tree', 'large_N_M_dense'],
        weights=[0.5, 0.1, 0.1, 0.1, 0.1, 0.1], k=1
    )[0]

    if scenario_type == 'N_1_M_0':
        N = 1
        M = 0
    elif scenario_type == 'small_N_M':
        N = random.randint(2, 5)
        M_max_possible = N * (N - 1) // 2
        M = random.randint(0, min(M_max_possible, 5))
    elif scenario_type == 'large_N_M_0': # Large N, M=0 (disconnected)
        N = random.randint(200, 300)
        M = 0
    elif scenario_type == 'large_N_M_tree' and N > 1: # Large N, M=N-1 (tree-like)
        N = random.randint(200, 300)
        M = min(N - 1, 300) # M cannot exceed 300
    elif scenario_type == 'large_N_M_dense': # Large N, M=300 (as dense as possible)
        N = random.randint(200, 300)
        M = 300

    # Regenerate A_vals and B_vals for adjusted N
    A_vals = [random.randint(1, 10**6) for _ in range(N)]
    B_vals = [random.randint(-10**6, 10**6) for _ in range(N)]

    # --- Special A_i, B_i value distributions ---
    value_dist_type = random.choices(
        ['random', 'A_same', 'A_min_max', 'B_same', 'B_min_max_zero', 'B_with_zeros'],
        weights=[0.4, 0.1, 0.1, 0.1, 0.1, 0.2], k=1
    )[0]
    
    if value_dist_type == 'A_same':
        val = random.randint(1, 10**6)
        A_vals = [val] * N
    elif value_dist_type == 'A_min_max':
        if random.random() < 0.5: A_vals = [1] * N
        else: A_vals = [10**6] * N
    elif value_dist_type == 'B_same':
        val = random.randint(-10**6, 10**6)
        B_vals = [val] * N
    elif value_dist_type == 'B_min_max_zero':
        r_val_choice = random.random()
        if r_val_choice < 0.33: B_vals = [-10**6] * N
        elif r_val_choice < 0.66: B_vals = [10**6] * N
        else: B_vals = [0] * N
    elif value_dist_type == 'B_with_zeros':
        for i in range(N):
            if random.random() < 0.3: # ~30% chance for B_i to be 0
                B_vals[i] = 0

    edges = _gen_graph_edges(N, M)

    input_str = f"{N} {M}\n"
    input_str += " ".join(map(str, A_vals)) + "\n"
    input_str += " ".join(map(str, B_vals)) + "\n"
    for u, v in edges:
        input_str += f"{u} {v}\n"

    return input_str

def parse_input(stdin_str):
    """Helper to parse stdin string into N, M, A, B, edges."""
    lines = stdin_str.strip().split('\n')
    N, M = map(int, lines[0].split())
    A = list(map(int, lines[1].split()))
    B = list(map(int, lines[2].split()))
    edges = []
    for i in range(M):
        u, v = map(int, lines[3 + i].split())
        edges.append((u, v))
    return N, M, A, B, edges

def check(stdin: str, stdout: str) -> None:
    """
    Verifies properties of the program's output.
    """
    # --- 1. Output Format and Type Check ---
    try:
        profit = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Program output '{stdout.strip()}' is not a single integer.")

    N, M, A, B, edges = parse_input(stdin)

    # --- 2. Metamorphic Property: Flipping B_i signs ---
    # The score of a component is `abs(sum(B_i))`. If all B_i are replaced by -B_i,
    # the sum becomes `sum(-B_i) = -sum(B_i)`. The absolute value `abs(-sum(B_i))`
    # is the same as `abs(sum(B_i))`. Deletion costs A_i are unaffected.
    # Therefore, the maximum profit should remain unchanged.
    
    B_flipped = [-b for b in B]
    stdin_flipped_B = f"{N} {M}\n" \
                      f"{' '.join(map(str, A))}\n" \
                      f"{' '.join(map(str, B_flipped))}\n"
    for u, v in edges:
        stdin_flipped_B += f"{u} {v}\n"

    try:
        stdout_flipped_B = _run_program_on_input(stdin_flipped_B)
        profit_flipped_B = int(stdout_flipped_B.strip())
    except Exception as e:
        raise AssertionError(f"Program failed or produced malformed output on B_i flipped input. Error: {e}, Output: '{stdout_flipped_B.strip()}'")

    assert profit == profit_flipped_B, \
        f"Metamorphic (B_i sign flip) check failed: Profit changed from {profit} to {profit_flipped_B}."

    # --- 3. Lower Bound Property: Baseline Strategies ---
    # The optimal profit must be at least as good as easily calculable baseline strategies.

    # Strategy 1: Keep all vertices. Cost = 0. Score = |sum(B_i for all vertices)|.
    profit_if_keep_all = abs(sum(B))
    assert profit >= profit_if_keep_all, \
        f"Lower Bound (Keep All) check failed: Output profit {profit} is less than {profit_if_keep_all} (profit if no vertices are deleted)."

    # Strategy 2: Delete all vertices. Cost = sum(A_i for all vertices). Score = 0 (no components).
    profit_if_delete_all = -sum(A)
    assert profit >= profit_if_delete_all, \
        f"Lower Bound (Delete All) check failed: Output profit {profit} is less than {profit_if_delete_all} (profit if all vertices are deleted)."

    # --- 4. Metamorphic Property: Adding an isolated vertex with A=0, B=0 ---
    # If a new vertex (N+1) is added with A_{N+1}=0 and B_{N+1}=0, and it has no edges,
    # it can either be kept or deleted.
    # - If kept: It forms an isolated component. Score = |0| = 0. Cost = 0 (A_i is paid on deletion). Profit contribution = 0.
    # - If deleted: Cost = A_{N+1} = 0. Profit contribution = 0.
    # In either case, it contributes 0 to the total profit and does not interact with the rest of the graph.
    # Thus, the optimal profit for the new graph should be the same as the original graph.
    # This test is only applicable if N < 300, as N+1 must not exceed the constraint.

    if N < 300:
        A_plus_iso = A + [0]
        B_plus_iso = B + [0]
        N_plus_iso = N + 1
        M_plus_iso = M # No new edges

        stdin_plus_iso = f"{N_plus_iso} {M_plus_iso}\n" \
                         f"{' '.join(map(str, A_plus_iso))}\n" \
                         f"{' '.join(map(str, B_plus_iso))}\n"
        for u, v in edges:
            stdin_plus_iso += f"{u} {v}\n"

        try:
            stdout_plus_iso = _run_program_on_input(stdin_plus_iso)
            profit_plus_iso = int(stdout_plus_iso.strip())
        except Exception as e:
            raise AssertionError(f"Program failed or produced malformed output on A=0, B=0 isolated vertex input. Error: {e}, Output: '{stdout_plus_iso.strip()}'")
        
        assert profit == profit_plus_iso, \
            f"Metamorphic (Isolated A=0, B=0 vertex) check failed: Profit changed from {profit} to {profit_plus_iso}."