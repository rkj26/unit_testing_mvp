import random
import math

def gen_input() -> str:
    # Generate n, ranging from 1 to 24.
    # Bias towards smaller values and boundary values to stress test.
    n_options = [1, 2, 3, 4, 5, 6, 7, 8] + [random.randint(9, 23) for _ in range(3)] + [24, 24]
    n = random.choice(n_options)

    c_values_list = []

    if n == 1:
        # For n=1, the only possible subtree size is 1.
        c_values_list = [1]
    else:
        # A valid tree must have exactly one node with subtree size 'n' (the root).
        # The other n-1 nodes must have subtree sizes between 1 and n-1.

        # Strategies for generating c_i values (excluding 'n'):
        distribution_type = random.choices(
            ['random_spread', 'many_ones', 'few_distinct', 'high_values', 'low_values'],
            weights=[0.4, 0.2, 0.2, 0.1, 0.1], k=1
        )[0]

        if distribution_type == 'many_ones':
            # Generate a large number of 1s (leaves), then some other values.
            num_ones = random.randint(1, n - 1)
            c_values_list = [1] * num_ones
            for _ in range(n - 1 - num_ones):
                c_values_list.append(random.randint(2, n - 1))
        elif distribution_type == 'few_distinct':
            # Generate a small number of distinct values (other than 1 and n) and repeat them.
            num_distinct_others = random.randint(1, min(n - 1, 4))
            distinct_values = [random.randint(1, n - 1) for _ in range(num_distinct_others)]
            c_values_list = [random.choice(distinct_values) for _ in range(n - 1)]
        elif distribution_type == 'high_values':
            # Generate values mostly in the upper range (closer to n-1).
            lower_bound = max(1, n - random.randint(2, min(n - 1, 6)))
            c_values_list = [random.randint(lower_bound, n - 1) for _ in range(n - 1)]
        elif distribution_type == 'low_values':
            # Generate values mostly in the lower range (closer to 1).
            upper_bound = random.randint(1, min(n - 1, 6))
            c_values_list = [random.randint(1, upper_bound) for _ in range(n - 1)]
        else: # 'random_spread' or fallback
            # Default to a general random spread of values.
            c_values_list = [random.randint(1, n - 1) for _ in range(n - 1)]

        # Add the root's subtree size 'n' and shuffle to randomize its position.
        c_values_list.append(n)
        random.shuffle(c_values_list)

    return f"{n}\n{' '.join(map(str, c_values_list))}\n"


def check(stdin: str, stdout: str) -> None:
    # 1. Parse input (n and c_values).
    lines = stdin.strip().split('\n')
    n = int(lines[0])
    c_values_str = lines[1].split()
    c_values = [int(x) for x in c_values_str]

    # 2. Check output format: Must be "YES" or "NO".
    assert stdout.strip() in {"YES", "NO"}, \
        f"Output must be 'YES' or 'NO', but got '{stdout.strip()}' for input:\n{stdin}"

    # 3. Property: There must be exactly one node with subtree size 'n'.
    # Only the root node can have a subtree size equal to the total number of nodes 'n'.
    num_n_occurrences = c_values.count(n)
    if num_n_occurrences != 1:
        # If this condition is violated, it's impossible to form a valid tree.
        # The program MUST output "NO".
        assert stdout.strip() == "NO", \
            f"Input has {num_n_occurrences} occurrences of n={n} in c_values. " \
            f"Expected 'NO', but got '{stdout.strip()}' for input:\n{stdin}"
        # If it's "NO" due to this, we can stop checking further necessary conditions.
        return

    # 4. Property: Minimum number of leaves (nodes with c_i = 1).
    # Each internal node must have at least two children.
    # Let 'L' be the number of leaves (nodes with c_i = 1) and 'I' be the number of internal nodes.
    # We know L + I = n.
    # In any tree with n nodes, there are n-1 edges. Each edge connects an internal node to one of its children.
    # The sum of out-degrees of all internal nodes equals the total number of edges (n-1).
    # Since each internal node must have an out-degree (number of children) of at least 2,
    # the sum of out-degrees is at least 2 * I.
    # So, 2 * I <= n - 1.
    # Substituting I = n - L:
    # 2 * (n - L) <= n - 1
    # 2n - 2L <= n - 1
    # n + 1 <= 2L
    # L >= (n + 1) / 2
    # The minimum number of leaves (c_i=1) required is math.ceil((n + 1) / 2.0).

    num_ones = c_values.count(1)
    min_leaves_required = math.ceil((n + 1) / 2.0)

    if num_ones < min_leaves_required:
        # If there are not enough leaves (nodes with c_i=1) to satisfy the condition,
        # it's impossible to form a valid tree. The program MUST output "NO".
        assert stdout.strip() == "NO", \
            f"Input has {num_ones} leaves (c_i=1), but at least {min_leaves_required} are required for n={n}. " \
            f"Expected 'NO', but got '{stdout.strip()}' for input:\n{stdin}"
        # If it's "NO" due to this, we can stop checking further necessary conditions.
        return

    # Note: These properties are necessary conditions for a "YES" answer.
    # Passing these checks does NOT guarantee a "YES" answer (as seen in Example 2).
    # However, failing these checks PROVES that the answer must be "NO".
    # This makes these assertions sound for catching incorrect "YES" outputs.