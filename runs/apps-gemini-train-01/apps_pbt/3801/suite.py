import random

def gen_input() -> str:
    """
    Generates a single valid input string for the problem.
    Constraints:
    1 <= n <= 50
    1 <= m <= 50
    a_i is either 0 or 1. At least one picture is liked (a_i=1).
    1 <= w_i <= 50
    """
    n = random.randint(1, 50)
    m = random.randint(1, 50) 

    a = [random.randint(0, 1) for _ in range(n)]
    # Ensure at least one picture is liked, as per problem statement
    if sum(a) == 0:
        a[random.randint(0, n - 1)] = 1

    w = [random.randint(1, 50) for _ in range(n)]

    input_str = f"{n} {m}\n"
    input_str += " ".join(map(str, a)) + "\n"
    input_str += " ".join(map(str, w)) + "\n"
    return input_str

MOD = 998244353

def parse_input(stdin: str):
    """Parses the input string into problem variables."""
    lines = stdin.strip().split('\n')
    n, m = map(int, lines[0].split())
    a = list(map(int, lines[1].split()))
    w = list(map(int, lines[2].split()))
    return n, m, a, w

def parse_output(stdout: str):
    """Parses the output string into a list of integers."""
    # The examples show one integer per line.
    return [int(x) for x in stdout.strip().split('\n')]

def mod_inv(val, mod=MOD):
    """Computes modular multiplicative inverse."""
    return pow(val, mod - 2, mod)

def check(stdin: str, stdout: str) -> None:
    """
    Asserts properties that the correct output must satisfy.
    """
    n, m, a, w = parse_input(stdin)
    output_r = parse_output(stdout)

    # Property 1: Output format and range check
    # The output must contain exactly n integers.
    assert len(output_r) == n, f"Output should have {n} integers, got {len(output_r)}"
    # Each output integer r_i must be within the valid modulo range [0, MOD-1].
    for val in output_r:
        assert 0 <= val < MOD, f"Output value {val} out of range [0, {MOD-1}]"

    # Property 2: Base case for m=1
    # For m=1, the expected weight of picture k, E[w_k], can be calculated directly.
    # E[w_k] = sum_{j=1..n} P(j chosen) * (weight of k after j is chosen)
    # P(j chosen) = w_j / W_total (where W_total = sum(w_i))
    # If j != k, w_k does not change.
    # If j == k, w_k changes by +1 if a_k=1, or by -1 if a_k=0 (capped at 0).
    # Since initial w_i >= 1, if a_k=0 and w_k is chosen, it becomes w_k-1 (which is >=0).
    # So the change is (a_k*2 - 1).
    # Thus, E[w_k] = (sum_{j!=k} w_j/W_total) * w_k + (w_k/W_total) * (w_k + (a_k*2 - 1))
    # E[w_k] = (W_total - w_k)/W_total * w_k + (w_k/W_total) * (w_k + (a_k*2 - 1))
    # E[w_k] = w_k - w_k^2/W_total + w_k^2/W_total + w_k * (a_k*2 - 1) / W_total
    # E[w_k] = w_k + w_k * (a_k*2 - 1) / W_total
    if m == 1:
        W_total_initial = sum(w)
        inv_W_total = mod_inv(W_total_initial)
        
        expected_weights_for_m1 = []
        for i in range(n):
            # delta_val is +1 if liked (a[i]=1), and -1 if disliked (a[i]=0).
            # This is simplified because w[i] is guaranteed to be >=1 initially,
            # so w[i]-1 for disliked items will always be >=0 for m=1.
            delta_val = (a[i] * 2 - 1) % MOD

            # Calculate expected_w_i_mod = (w[i] + (w[i] * delta_val) / W_total_initial) % MOD
            term_numerator = (w[i] % MOD * delta_val) % MOD
            expected_w_i_mod = (w[i] % MOD + term_numerator * inv_W_total) % MOD
            # Ensure the result is non-negative, as Python's % can return negative for negative dividends
            expected_w_i_mod = (expected_w_i_mod + MOD) % MOD 
            
            expected_weights_for_m1.append(expected_w_i_mod)
        
        for i in range(n):
            assert output_r[i] == expected_weights_for_m1[i], \
                f"m=1 check failed for picture {i}: Input w[{i}]={w[i]}, a[{i}]={a[i]}, W_total_initial={W_total_initial}. " \
                f"Expected E[w_{i}] = {expected_weights_for_m1[i]}, Got {output_r[i]}."

    # Property 3: Symmetry for all liked and equal initial weights
    # If all pictures are liked (a_i=1 for all i) AND all initial weights are equal (w_i = C for all i),
    # then due to complete symmetry, the expected final weights of all pictures must be equal.
    is_all_liked = all(val == 1 for val in a)
    is_all_weights_equal = (n > 0) and all(val == w[0] for val in w) # n>0 is guaranteed by constraints

    if is_all_liked and is_all_weights_equal:
        for i in range(1, n):
            assert output_r[i] == output_r[0], \
                f"Symmetry check failed: All pictures liked and equal initial weights, " \
                f"but E[w_{i}] ({output_r[i]}) != E[w_0] ({output_r[0]})"