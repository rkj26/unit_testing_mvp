import random
import math

# The `run_program` function is assumed to be provided by the testing harness.
# It takes an stdin string and returns an stdout string.
# For local development/testing, one might mock it like this:
# def run_program(stdin_str: str) -> str:
#     # Replace this with an actual call to the program being tested,
#     # or a reference solution if available.
#     # Example for testing with a reference solution:
#     # import subprocess
#     # proc = subprocess.run(['python', 'untrusted_solution.py'], input=stdin_str, capture_output=True, text=True)
#     # return proc.stdout
#     raise NotImplementedError("The testing harness must provide the 'run_program' function.")


def gen_input() -> str:
    # Deliberately cover minimum/boundary sizes, extreme values, duplicates,
    # ties, and a wide random range.

    n_choice = random.random()
    if n_choice < 0.05: # Very small n (1 to 3)
        n = random.randint(1, 3)
    elif n_choice < 0.2: # Small n (4 to 10)
        n = random.randint(4, 10)
    elif n_choice < 0.4: # Medium n (11 to 100)
        n = random.randint(11, 100)
    else: # Large n (up to 5000)
        n = random.randint(1, 5000) # Covers minimum N also, if no other branch hit.

    a = []
    height_type_choice = random.random()

    if height_type_choice < 0.15: # All same heights
        height = random.randint(1, 100000)
        a = [height] * n
    elif height_type_choice < 0.30: # Increasing or decreasing sequence
        start_h = random.randint(1, 100000)
        step = random.randint(0, 10000) # Can have large steps
        if random.random() < 0.5: # Increasing
            a = [min(100000, start_h + i * step) for i in range(n)]
        else: # Decreasing
            a = [max(1, start_h - i * step) for i in range(n)]
        # Ensure values are within [1, 100000]
        a = [max(1, min(100000, h)) for h in a]
    elif height_type_choice < 0.45: # Alternating high/low or low/high
        h1 = random.randint(1, 100000)
        h2 = random.randint(1, 100000)
        a = [h1 if i % 2 == 0 else h2 for i in range(n)]
    elif height_type_choice < 0.60: # Heights close to each other (e.g., small variance)
        base_h = random.randint(1, 99990)
        a = [random.randint(base_h, min(100000, base_h + 10)) for _ in range(n)]
    elif height_type_choice < 0.75: # Heights far apart (e.g., low and high values interspersed)
        low_h = random.randint(1, 50000)
        high_h = random.randint(50001, 100000)
        a = [random.choice([low_h, high_h]) for _ in range(n)]
    else: # Fully random heights
        a = [random.randint(1, 100000) for _ in range(n)]

    # Special case for n=1: It should always have 0 cost.
    if n == 1:
        a = [random.randint(1, 100000)] # Value doesn't matter, cost is 0.

    return f"{n}\n{' '.join(map(str, a))}\n"


def parse_input(stdin: str):
    """Parses the input string into n and a list of heights."""
    lines = stdin.strip().split('\n')
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    return n, a

def parse_output(stdout: str):
    """Parses the output string into a list of costs."""
    return [int(x) for x in stdout.strip().split()]

def check(stdin: str, stdout: str) -> None:
    n, a = parse_input(stdin)
    ans_out = parse_output(stdout)

    # Property 1: Output length must match ceil(n/2)
    expected_k_count = math.ceil(n / 2)
    assert len(ans_out) == expected_k_count, \
        f"Output length mismatch for n={n}. Expected {expected_k_count} values, got {len(ans_out)}."

    # Property 2: All output values must be non-negative integers.
    for i, cost in enumerate(ans_out):
        assert isinstance(cost, int), f"Cost for k={i+1} is not an integer: {cost}."
        assert cost >= 0, f"Cost for k={i+1} is negative: {cost}."

    # Property 3: Monotonicity - Cost for 'k' houses must be less than or equal to cost for 'k+1' houses.
    # This is because the problem asks for "at least k hills". If we can achieve k+1 hills for cost C,
    # we have also achieved k hills for cost C. Therefore, min_cost(k) <= min_cost(k+1).
    for i in range(len(ans_out) - 1):
        assert ans_out[i] <= ans_out[i+1], \
            f"Costs are not non-decreasing for n={n}, a={a}. " \
            f"Cost for k={i+1} is {ans_out[i]}, but cost for k={i+2} is {ans_out[i+1]}. " \
            f"Expected ans[{i}] <= ans[{i+1}]."

    # Property 4: Upper bound for ans_out[0] (cost for k=1).
    # We calculate the minimum cost to make ANY single hill a peak.
    # The actual optimal cost for k=1 must be less than or equal to this.
    min_cost_single_peak_candidate = float('inf')

    if n == 1:
        min_cost_single_peak_candidate = 0 # Single hill is always a peak with 0 cost.
    else:
        # Cost to make hill `i` a peak is `max(0, a[i-1] - (a[i]-1)) + max(0, a[i+1] - (a[i]-1))`
        # (for 0 < i < n-1), or just one term for endpoints.
        
        # Check first hill (index 0)
        cost_for_0_as_peak = max(0, a[1] - a[0] + 1)
        min_cost_single_peak_candidate = min(min_cost_single_peak_candidate, cost_for_0_as_peak)

        # Check last hill (index n-1)
        cost_for_n_minus_1_as_peak = max(0, a[n-2] - a[n-1] + 1)
        min_cost_single_peak_candidate = min(min_cost_single_peak_candidate, cost_for_n_minus_1_as_peak)

        # Check middle hills (index i from 1 to n-2)
        for i in range(1, n - 1):
            cost_for_i_as_peak = max(0, a[i-1] - a[i] + 1) + max(0, a[i+1] - a[i] + 1)
            min_cost_single_peak_candidate = min(min_cost_single_peak_candidate, cost_for_i_as_peak)
    
    # Assert that the program's reported cost for k=1 is not higher than this trivial upper bound.
    assert ans_out[0] <= min_cost_single_peak_candidate, \
        f"Cost for k=1 ({ans_out[0]}) exceeds a trivial upper bound ({min_cost_single_peak_candidate}) " \
        f"for n={n}, a={a}."

    # Property 5: Metamorphic relation - Invariance under array reversal.
    # The problem logic is symmetric with respect to array order.
    # Reversing the input array should yield the exact same sequence of minimum costs.
    a_reversed = a[::-1]
    stdin_reversed = f"{n}\n{' '.join(map(str, a_reversed))}\n"

    # The `run_program` function is provided by the testing harness.
    # It executes the untrusted model's program and returns its stdout.
    stdout_reversed = run_program(stdin_reversed)
    ans_out_reversed = parse_output(stdout_reversed)

    assert len(ans_out_reversed) == expected_k_count, \
        f"Output length mismatch for reversed input (n={n}, a_rev={a_reversed}). " \
        f"Expected {expected_k_count}, got {len(ans_out_reversed)}."
    
    assert ans_out == ans_out_reversed, \
        f"Output not invariant under array reversal for n={n}. " \
        f"Original input {a}, Output: {ans_out}\n" \
        f"Reversed input {a_reversed}, Output: {ans_out_reversed}"