import random
import collections

def gen_input() -> str:
    # Determine n: covers small, medium, and large values.
    # Constraints: 2 <= n <= 200,000
    r_n = random.random()
    if r_n < 0.1:  # 10% chance for small n
        n = random.randint(2, min(50, 200000))
    elif r_n < 0.4:  # 30% chance for medium n
        n = random.randint(51, min(5000, 200000))
    else:  # 60% chance for large n
        n = random.randint(5001, 200000)

    # Determine k: covers minimum, maximum, and random values.
    # Constraints: 1 <= k <= n / 2
    r_k = random.random()
    if r_k < 0.1:  # 10% chance for k=1 (minimum)
        k = 1
    elif r_k < 0.2:  # 10% chance for k=n/2 (maximum)
        k = n // 2
    else:  # 80% chance for k random in between
        k = random.randint(1, n // 2)

    # Generate 2k distinct university towns.
    # Towns are 1-indexed.
    university_towns = sorted(random.sample(range(1, n + 1), 2 * k))

    # Generate tree edges.
    edges = []
    r_tree_type = random.random()
    if r_tree_type < 0.1:  # 10% chance for a path graph (high diameter)
        for i in range(1, n):
            edges.append((i, i + 1))
    elif r_tree_type < 0.2:  # 10% chance for a star graph (low diameter)
        if n > 1:
            center = random.randint(1, n)
            for i in range(1, n + 1):
                if i != center:
                    edges.append((center, i))
    else:  # 80% chance for a general random tree
        # Connect each new node `i` to a randomly chosen existing node `parent` (1 to i-1).
        for i in range(2, n + 1):
            parent = random.randint(1, i - 1)
            edges.append((parent, i))
        random.shuffle(edges) # Shuffle to randomize edge order

    # Format the input string.
    input_str = f"{n} {k}\n"
    input_str += " ".join(map(str, university_towns)) + "\n"
    for u, v in edges:
        input_str += f"{u} {v}\n"

    return input_str

def check(stdin: str, stdout: str) -> None:
    lines = stdin.strip().split('\n')
    
    # Parse n and k
    n, k = map(int, lines[0].split())
    
    # Parse university towns
    university_towns_list = list(map(int, lines[1].split()))
    university_set = set(university_towns_list)

    # Build adjacency list for the tree
    adj = collections.defaultdict(list)
    # Edges start from the third line (index 2) of the input.
    for i in range(2, len(lines)):
        u, v = map(int, lines[i].split())
        adj[u].append(v)
        adj[v].append(u)

    # --- Recompute the correct answer based on a known property ---
    # The maximum total distance is the sum, over all edges, of the minimum
    # number of university towns in the two components formed by removing that edge.
    # More formally, for an edge (u, v), let `count_v_subtree` be the number of
    # university towns in the subtree rooted at `v` (when `u` is its parent).
    # Then `min(count_v_subtree, 2*k - count_v_subtree)` is the contribution
    # of this edge to the total maximum distance.

    total_max_dist_recomputed = 0
    
    # DFS function to calculate subtree university counts and accumulate total distance.
    # `u`: current node
    # `parent`: parent of `u` in the DFS tree, to avoid going back up.
    # Returns the count of universities in the subtree rooted at `u`.
    def dfs(u: int, parent: int) -> int:
        nonlocal total_max_dist_recomputed # Allow modifying outer variable

        current_subtree_uni_count = 0
        if u in university_set:
            current_subtree_uni_count += 1
            
        for v in adj[u]:
            if v == parent:
                continue
            
            # Recurse for child v
            child_subtree_uni_count = dfs(v, u)
            
            # Calculate contribution of the edge (u, v)
            # This edge separates `child_subtree_uni_count` universities from
            # `2*k - child_subtree_uni_count` universities.
            total_max_dist_recomputed += min(child_subtree_uni_count, 2 * k - child_subtree_uni_count)
            
            current_subtree_uni_count += child_subtree_uni_count
            
        return current_subtree_uni_count

    # Start DFS from an arbitrary root, e.g., node 1.
    # The parent of the root (1) can be a non-existent node like 0.
    # The return value of the initial DFS call is the total number of universities (2k),
    # which is not directly used for the final answer, but `total_max_dist_recomputed`
    # is populated during the traversal.
    if n > 0: # Problem constraints say n >= 2, so this check is mostly for robustness.
        dfs(1, 0)
    
    # --- Check the program's output ---
    try:
        program_output = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Program output '{stdout.strip()}' is not a valid integer.")
    
    # The program's output must match the recomputed maximum total distance.
    assert program_output == total_max_dist_recomputed, \
        f"Mismatch: Expected {total_max_dist_recomputed}, but program outputted {program_output}.\nInput:\n{stdin}\nOutput:\n{stdout}"