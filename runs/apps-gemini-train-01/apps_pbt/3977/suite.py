import random
import collections

def gen_input() -> str:
    """
    Generates a valid input string for the problem.

    The generated graph is guaranteed to be stable by constructing
    k initial "partitions" (representing potential countries), assigning
    government nodes to distinct partitions, and then assigning
    remaining nodes randomly. Edges are then only added within these
    partitions to ensure no two government nodes are connected.
    """
    # Constraints: 1 <= n <= 1000, 0 <= m <= 100000, 1 <= k <= n
    # Maximum possible edges in a simple graph with n nodes is n * (n - 1) / 2.
    # m should also be capped by this for consistency.

    n = random.randint(1, 1000)
    k = random.randint(1, n)
    
    # Generate k distinct government nodes
    all_nodes = list(range(1, n + 1))
    gov_nodes = sorted(random.sample(all_nodes, k))

    # Partition nodes to ensure stability for initial edge generation.
    # We create k "virtual" components (partitions), each hosting one government node.
    # Remaining nodes are randomly assigned to one of these k partitions.
    
    # partition_assignments[i] will be a list of nodes in the i-th partition.
    partition_assignments = [[] for _ in range(k)]
    
    # Assign government nodes to their respective partitions (one per partition)
    for i in range(k):
        gov_node = gov_nodes[i]
        partition_assignments[i].append(gov_node)
    
    # Assign remaining non-government nodes to these partitions randomly
    remaining_nodes = [node for node in all_nodes if node not in gov_nodes]
    random.shuffle(remaining_nodes) # Shuffle for better distribution
    
    for node in remaining_nodes:
        # Assign to a random partition index
        target_partition_idx = random.randrange(k)
        partition_assignments[target_partition_idx].append(node)

    # Collect all possible edges that can be formed *within* these stable partitions.
    # These are the only edges allowed in the initial graph to maintain stability.
    all_possible_edges_within_partitions = []
    for p_nodes in partition_assignments:
        # Sort nodes within partition to ensure consistent edge (u, v) generation with u < v
        p_nodes.sort() 
        for i in range(len(p_nodes)):
            for j in range(i + 1, len(p_nodes)):
                u, v = p_nodes[i], p_nodes[j]
                all_possible_edges_within_partitions.append((u, v))

    # Determine m, the number of initial edges.
    # m cannot exceed the problem's limit (100,000) or the total number of
    # possible edges within the currently generated stable partition structure.
    max_m_possible = min(100000, len(all_possible_edges_within_partitions))
    m = random.randint(0, max_m_possible)
    
    # Randomly select m edges from the set of all stable possible edges
    random.shuffle(all_possible_edges_within_partitions)
    chosen_edges = all_possible_edges_within_partitions[:m]

    # Construct the final input string
    input_str_parts = []
    input_str_parts.append(f"{n} {m} {k}")
    input_str_parts.append(" ".join(map(str, gov_nodes)))
    for u, v in chosen_edges:
        input_str_parts.append(f"{u} {v}")

    return "\n".join(input_str_parts) + "\n"


def check(stdin: str, stdout: str) -> None:
    """
    Verifies properties of the program's output.

    Checks include:
    1. Output format and non-negativity.
    2. Upper bound on total edges: The final number of edges cannot exceed the maximum
       for a simple graph with N nodes.
    3. Tighter upper bound on total edges: The final number of edges cannot exceed
       the maximum possible for *any stable graph* with N nodes and K government nodes.
       This maximum is achieved when K-1 components are single nodes and one component
       contains N-K+1 nodes, resulting in (N-K+1)*(N-K)/2 edges.
    4. Exact equality for the specific case where K=1: With only one government,
       the entire graph can become a single clique, so total edges must be N*(N-1)/2.
    5. Exact equality for the specific case where M=0: With no initial edges, all nodes
       are isolated. The optimal strategy makes one component of size N-K+1 and K-1
       components of size 1. Total added edges must be (N-K+1)*(N-K)/2.
    """
    # 1. Parse input
    lines = stdin.strip().split('\n')
    n, m, k = map(int, lines[0].split())

    # 2. Parse output
    try:
        m_added = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a single integer: '{stdout}'")

    # Property 1: The number of added edges must be non-negative.
    assert m_added >= 0, f"Expected non-negative added edges, but program returned {m_added}. Input: {stdin}"

    # Calculate total edges in the final graph (initial edges + added edges)
    m_final = m + m_added

    # Property 2: The total number of edges in the final graph cannot exceed
    # the maximum possible edges for any simple graph with N nodes (N * (N - 1) / 2).
    # This is a basic sanity check, true for any graph regardless of stability.
    max_possible_edges_total_graph = n * (n - 1) // 2
    assert m_final <= max_possible_edges_total_graph, \
        f"Final edges ({m_final}) exceeds maximum possible for N={n} ({max_possible_edges_total_graph}). Input: {stdin}"

    # Property 3: The total number of edges in a stable graph with K government nodes
    # cannot exceed (N - K + 1) * (N - K) / 2.
    # This upper bound is achieved when K-1 components are single nodes and one
    # component contains N-K+1 nodes. This represents the absolute maximum edges
    # possible in *any* stable configuration.
    max_stable_edges_theoretical_bound = (n - k + 1) * (n - k) // 2
    assert m_final <= max_stable_edges_theoretical_bound, \
        f"Final edges ({m_final}) exceeds theoretical maximum for a stable graph with N={n}, K={k} ({max_stable_edges_theoretical_bound}). Input: {stdin}"

    # Property 4: If k=1, there's only one government node.
    # The stability condition ("no path between *two* government nodes") is trivially met.
    # Thus, all N nodes can form a single connected component (a clique).
    # The maximum total edges is N * (N - 1) / 2.
    if k == 1:
        assert m_final == max_possible_edges_total_graph, \
            f"When k=1, final edges should be {max_possible_edges_total_graph}, but got {m_final}. Input: {stdin}"

    # Property 5: If m=0 (no initial edges), all nodes are initially isolated.
    # In this scenario, each of the k government nodes effectively forms a component of size 1.
    # The remaining n-k non-government nodes are also isolated.
    # To maximize edges, the optimal strategy will collect all n-k isolated non-government nodes
    # and add them to *one* of the k government-node components. This makes one component of
    # size (1 + (n-k)) = (n-k+1), and the other k-1 government-node components remain size 1.
    # The total number of edges added will then be (n-k+1)*(n-k)/2 (plus 0 from k-1 singletons).
    if m == 0:
        expected_added_edges_for_m0 = (n - k + 1) * (n - k) // 2
        assert m_added == expected_added_edges_for_m0, \
            f"When m=0, expected {expected_added_edges_for_m0} added edges, but got {m_added}. Input: {stdin}"