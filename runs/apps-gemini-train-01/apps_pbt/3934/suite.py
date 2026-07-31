import random
import sys

def gen_input() -> str:
    # --- Helper functions for generating specific tree types ---
    def _generate_path_graph(n_nodes):
        # Creates a simple path graph: 1-2-3-...-n_nodes
        edges = []
        if n_nodes >= 2:
            for i in range(1, n_nodes):
                edges.append((i, i + 1))
        return edges

    def _generate_star_graph(n_nodes):
        # Creates a star graph with node 1 as the center, connected to all other nodes.
        edges = []
        if n_nodes >= 2:
            # Node 1 is the center, connects to all other nodes
            for i in range(2, n_nodes + 1):
                edges.append((1, i))
        return edges

    def _generate_random_tree(n_nodes):
        # Generates a random tree using the "parent list" method.
        # For each node i (from 2 to n_nodes), a random parent is chosen from 1 to i-1.
        edges = []
        if n_nodes >= 2:
            for i in range(2, n_nodes + 1):
                parent = random.randint(1, i - 1)
                edges.append((parent, i))
        return edges

    def _generate_specific_tree_example3_like(n_nodes):
        # Mimics Example 3: n=5, 1-2, 1-3, 1-4, 2-5. Node 2 has degree 2. (Expected "NO")
        # For n_nodes > 5, additional nodes are attached as leaves to nodes 1 or 2.
        edges = []
        if n_nodes >= 5:
            edges.append((1, 2))
            edges.append((1, 3))
            edges.append((1, 4))
            edges.append((2, 5))
            # Add remaining nodes as leaves to existing nodes (1 or 2)
            for i in range(6, n_nodes + 1):
                edges.append((random.choice([1, 2]), i))
        else: # Fallback to a random tree for smaller n_nodes
            edges = _generate_random_tree(n_nodes)
        return edges

    def _generate_specific_tree_example4_like(n_nodes):
        # Mimics Example 4: n=6, 1-2, 1-3, 1-4, 2-5, 2-6. No degree 2 nodes. (Expected "YES")
        # For n_nodes > 6, additional nodes are attached as leaves to nodes 1 or 2.
        edges = []
        if n_nodes >= 6:
            edges.append((1, 2))
            edges.append((1, 3))
            edges.append((1, 4))
            edges.append((2, 5))
            edges.append((2, 6))
            # Add remaining nodes as leaves to existing nodes (1 or 2)
            for i in range(7, n_nodes + 1):
                edges.append((random.choice([1, 2]), i))
        else: # Fallback to a random tree for smaller n_nodes
            edges = _generate_random_tree(n_nodes)
        return edges

    # --- Main gen_input logic ---
    # Choose 'n' (number of nodes)
    # Prioritize small 'n' values for specific structures, and also include medium and max 'n'
    n_options = [random.randint(2, 10) for _ in range(20)] # Many small n
    n_options.extend([random.randint(11, 100) for _ in range(10)]) # Medium n
    n_options.extend([random.randint(101, 1000) for _ in range(5)]) # Larger n
    n_options.extend([random.randint(1001, 10**5) for _ in range(5)]) # Max n range
    n = random.choice(n_options)
    
    # Ensure n is at least 2 as per problem constraints
    if n < 2: n = 2

    # Choose a tree generation strategy
    tree_type_generators = [
        _generate_path_graph,
        _generate_star_graph,
        _generate_random_tree,
        _generate_specific_tree_example3_like, # Likely results in "NO"
        _generate_specific_tree_example4_like  # Likely results in "YES"
    ]
    
    # Assign weights to favor certain tree types to explore different scenarios
    # Path graphs often have nodes of degree 2 (for n > 2). Star graphs have deg 2 for n=3 (path).
    # Example3-like is specifically designed to have a deg 2 node. Example4-like is designed not to.
    weights = [20, 15, 40, 15, 10] # Total 100
    
    generator = random.choices(tree_type_generators, weights=weights, k=1)[0]
    edges = generator(n)

    # All helper functions are designed to produce n-1 edges if n >= 2.
    # The `_generate_specific_tree` functions have fallbacks for small `n`.
    # This check ensures that the edge count is always correct, even if a fallback
    # somehow failed (which shouldn't happen with current implementation).
    if len(edges) != n - 1 and n > 1:
        edges = _generate_random_tree(n) # Final fallback

    # Randomize the order of edges to prevent solutions relying on specific input order
    random.shuffle(edges)

    # Format the input string
    input_str = f"{n}\n"
    for u, v in edges:
        input_str += f"{u} {v}\n"
    return input_str


def check(stdin: str, stdout: str) -> None:
    # 1. Parse the input (stdin) to extract N and the edges.
    lines = stdin.strip().split('\n')
    n = int(lines[0])
    
    # Initialize an array to store degree counts for each node.
    # Nodes are 1-indexed (from 1 to N), so we use a list of size N+1 and ignore index 0.
    degrees = [0] * (n + 1)
    
    # Iterate through the N-1 edges to compute node degrees.
    for i in range(1, n):
        u, v = map(int, lines[i].split())
        degrees[u] += 1
        degrees[v] += 1
    
    # 2. Check for the existence of any node with degree 2.
    # A well-known property for this problem type is:
    # The answer is "NO" if and only if there is at least one node with degree 2.
    # (Note: leaves have degree 1, so a node with degree 2 is by definition not a leaf).
    has_degree_2_node = False
    for i in range(1, n + 1): # Iterate through all nodes (1 to N)
        if degrees[i] == 2:
            has_degree_2_node = True
            break # Found one, no need to check further
            
    # 3. Determine the expected output based on the derived property.
    expected_output = "NO" if has_degree_2_node else "YES"
    
    # 4. Assert that the program's output matches our expected output.
    # The output should be stripped of whitespace and converted to uppercase for case-insensitive comparison.
    assert stdout.strip().upper() == expected_output.upper(), \
        (f"Input triggered an unexpected output.\n"
         f"Input N: {n}\n"
         f"Input Edges:\n{''.join(lines[1:])}\n"
         f"Node degrees: {degrees[1:]}\n"
         f"Expected: {expected_output}\n"
         f"Got: {stdout.strip()}")