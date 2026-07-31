import random
import sys
import io
import subprocess

# Precompute mex table for quick lookups
_mex_table = {
    (0, 0): 1, (0, 1): 2, (0, 2): 1,
    (1, 0): 2, (1, 1): 0, (1, 2): 0,
    (2, 0): 1, (2, 1): 0, (2, 2): 0
}

def _mex(x, y):
    """
    Helper function to compute the mex(x, y) value based on the provided table.
    Ensures x and y are within {0, 1, 2}.
    """
    return _mex_table[(x, y)]

def _run_program_internal(input_str: str) -> str:
    """
    This helper function is designed to call the untrusted solution.
    In a real competition/verification setup, this would execute
    the provided solution. For local development, we assume 'solution.py'
    is present. The problem statement implies the verifier runs the
    SAME program via the harness.
    """
    try:
        # Assuming the untrusted model's code is in a file named 'solution.py'.
        # This path might need adjustment based on the actual execution environment.
        process = subprocess.run(
            [sys.executable, 'solution.py'],
            input=input_str.encode('utf-8'),
            capture_output=True,
            check=True,  # Raise CalledProcessError if the program exits with a non-zero status
            text=True    # Decode stdout/stderr as text using default encoding
        )
        return process.stdout
    except FileNotFoundError:
        # If 'solution.py' is not found, it implies the verifier is run in isolation.
        # Provide a placeholder/mock behavior. This mock will likely cause some
        # check() assertions to fail, which is intended to highlight that
        # _run_program_internal is not fully functional without the actual solution.
        print(f"WARNING: 'solution.py' not found. Mocking output for _run_program_internal. "
              f"Input N: {input_str.splitlines()[0].strip()}", file=sys.stderr)
        
        # A simple, often incorrect mock output. It ensures parsing doesn't fail,
        # but the values will almost certainly be wrong, leading to assertion failures.
        N_val = int(input_str.splitlines()[0].strip())
        total_elements = N_val * N_val
        # Attempt to distribute counts somewhat evenly, but this is a heuristic mock
        c0 = total_elements // 3
        c1 = (total_elements - c0) // 2
        c2 = total_elements - c0 - c1
        return f"{c0} {c1} {c2}\n"
    except subprocess.CalledProcessError as e:
        # If the untrusted program crashed or exited with an error status
        raise AssertionError(f"Untrusted program crashed or returned non-zero exit code.\n"
                             f"Input causing crash:\n{input_str}\n"
                             f"Stderr:\n{e.stderr}\n"
                             f"Stdout:\n{e.stdout}\n"
                             f"Return code: {e.returncode}")
    except Exception as e:
        # Catch any other unexpected errors during program execution
        raise AssertionError(f"An unexpected error occurred while running the untrusted program: {type(e).__name__}: {e}\n"
                             f"Input:\n{input_str}")


def gen_input() -> str:
    """
    Generates a single valid STDIN string for the problem, covering various
    constraints and potential edge cases.
    """
    # Explicitly defined test cases to cover samples, minimums, and specific patterns
    fixed_test_cases = [
        '4\n1 2 0 2\n0\n0\n0\n',  # Sample 1
        '1\n0\n',                # Sample 2
        '2\n1 2\n0\n',           # Sample 3
        '1\n1\n',                # N=1, a_11 = 1
        '1\n2\n',                # N=1, a_11 = 2
        '2\n0 0\n0\n',           # N=2, all boundary 0s
        '2\n1 1\n1\n',           # N=2, all boundary 1s
        '2\n2 2\n2\n',           # N=2, all boundary 2s
        '3\n0 1 2\n0\n1\n',      # N=3, alternating boundary values
        '3\n2 1 0\n1\n2\n',      # N=3, other alternating boundary values
        '5\n0 0 0 0 0\n0\n0\n0\n0\n', # N=5, all boundary 0s
    ]

    # Periodically return a fixed test case to ensure these critical cases are tested
    if random.random() < 0.2:
        return random.choice(fixed_test_cases)

    # Determine N based on a weighted distribution to cover small, medium, and large N values
    N_choice = random.choices(['small', 'medium', 'large'], weights=[0.4, 0.4, 0.2], k=1)[0]

    if N_choice == 'small':
        N = random.randint(1, 5)
    elif N_choice == 'medium':
        N = random.randint(6, 100)
    else: # 'large' N, up to 500,000
        N = random.randint(100000, 500000)
        # For very large N, generate structured patterns to test performance
        # and specific behaviors that might emerge, rather than fully random which
        # could lead to extremely long input strings and unpredictable patterns.
        pattern_type = random.choices(['all_0', 'all_1', 'all_2', 'alt_012', 'random_large'], weights=[0.2, 0.2, 0.2, 0.2, 0.2], k=1)[0]
        
        if pattern_type == 'all_0':
            first_row_vals = [0] * N
            first_col_rest_vals = [0] * (N - 1)
        elif pattern_type == 'all_1':
            first_row_vals = [1] * N
            first_col_rest_vals = [1] * (N - 1)
        elif pattern_type == 'all_2':
            first_row_vals = [2] * N
            first_col_rest_vals = [2] * (N - 1)
        elif pattern_type == 'alt_012':
            # Create alternating patterns for first row and column
            first_row_vals = [i % 3 for i in range(N)]
            first_col_rest_vals = [(i + 1) % 3 for i in range(N - 1)] # Offset for variety
        else: # 'random_large'
            first_row_vals = [random.randint(0, 2) for _ in range(N)]
            first_col_rest_vals = [random.randint(0, 2) for _ in range(N - 1)]

        input_lines = [str(N), ' '.join(map(str, first_row_vals))]
        input_lines.extend(map(str, first_col_rest_vals))
        return '\n'.join(input_lines) + '\n'

    # For 'small' and 'medium' N, generate completely random boundary values
    first_row_vals = [random.randint(0, 2) for _ in range(N)]
    first_col_rest_vals = [random.randint(0, 2) for _ in range(N - 1)]

    input_lines = [str(N), ' '.join(map(str, first_row_vals))]
    input_lines.extend(map(str, first_col_rest_vals))
    return '\n'.join(input_lines) + '\n'


def check(stdin: str, stdout: str) -> None:
    """
    Verifies properties of the program's output.

    Args:
        stdin: The input string provided to the program.
        stdout: The output string produced by the program.

    Raises:
        AssertionError: If any property is violated.
    """
    # 1. Parse N from stdin
    stdin_lines = stdin.strip().split('\n')
    N = int(stdin_lines[0])

    # 2. Parse output counts
    try:
        counts = list(map(int, stdout.strip().split()))
        assert len(counts) == 3, f"Output should have 3 integers, got {len(counts)}. Output: '{stdout.strip()}'"
        count_0, count_1, count_2 = counts
    except ValueError:
        raise AssertionError(f"Output must be space-separated integers, got: '{stdout.strip()}'")

    # Property 1: Counts are non-negative
    assert count_0 >= 0, f"Count of 0s is negative: {count_0}"
    assert count_1 >= 0, f"Count of 1s is negative: {count_1}"
    assert count_2 >= 0, f"Count of 2s is negative: {count_2}"

    # Property 2: Total count must equal N*N
    total_elements = N * N
    assert count_0 + count_1 + count_2 == total_elements, \
        f"Sum of counts ({count_0}+{count_1}+{count_2}={sum(counts)}) does not equal N*N ({total_elements}). " \
        f"Counts: {counts}, N: {N}"

    # Property 3: Exact computation for small N (1, 2, or 3)
    # For small N, we can reliably re-compute the entire matrix and its counts
    # within the verifier without re-implementing an efficient solver.
    if N <= 3:
        # Reconstruct the input border values from stdin
        first_row_str_values = stdin_lines[1].split()
        first_row = [int(x) for x in first_row_str_values]
        
        # first_col_rest contains a_2,1, a_3,1, ..., a_N,1
        first_col_rest = [int(stdin_lines[i]) for i in range(2, N + 1)]
        
        # Build the complete first column list: a_1,1, a_2,1, ..., a_N,1
        full_first_col = [first_row[0]] + first_col_rest

        # Manually compute the matrix entries
        matrix = [[-1 for _ in range(N)] for _ in range(N)]
        
        # Fill the first row
        for j in range(N):
            matrix[0][j] = first_row[j]
        
        # Fill the first column (excluding a_1,1, which is already in matrix[0][0])
        for i in range(1, N):
            matrix[i][0] = full_first_col[i]

        # Fill the rest of the matrix using the recurrence relation
        for i in range(1, N):
            for j in range(1, N):
                matrix[i][j] = _mex(matrix[i-1][j], matrix[i][j-1])
        
        # Count all values in the computed matrix
        computed_counts = {0: 0, 1: 0, 2: 0}
        for i in range(N):
            for j in range(N):
                computed_counts[matrix[i][j]] += 1

        assert count_0 == computed_counts[0], \
            f"N={N}: Computed 0s count mismatch. Expected {computed_counts[0]}, Got {count_0}. " \
            f"Input: {stdin.strip()}, Correct Matrix: {matrix}"
        assert count_1 == computed_counts[1], \
            f"N={N}: Computed 1s count mismatch. Expected {computed_counts[1]}, Got {count_1}. " \
            f"Input: {stdin.strip()}, Correct Matrix: {matrix}"
        assert count_2 == computed_counts[2], \
            f"N={N}: Computed 2s count mismatch. Expected {computed_counts[2]}, Got {count_2}. " \
            f"Input: {stdin.strip()}, Correct Matrix: {matrix}"

    # Property 4: Transposition (Metamorphic Property)
    # The matrix generation rule `a_{i,j} = mex(a_{i-1,j}, a_{i,j-1})` is symmetric
    # with respect to transposition (`a'_{i,j} = a_{j,i}`), because the `mex` function
    # itself is symmetric (`mex(x,y) = mex(y,x)`).
    # Thus, if we transpose the input boundary conditions and run the program again,
    # the resulting matrix (and hence the counts of 0s, 1s, 2s) should be the same.
    # We limit N for this check to avoid excessive runtime when calling the subprocess.
    # A limit of N=5000 is chosen as a reasonable balance for robustness without TLE.
    if N > 1 and N <= 5000:
        first_row_values = [int(x) for x in stdin_lines[1].split()]
        first_col_values_rest = [int(stdin_lines[i]) for i in range(2, N + 1)]

        # Construct the transposed input string:
        # The new first row will be the original first column (a_1,1, a_2,1, ..., a_N,1)
        transposed_first_row_values = [first_row_values[0]] + first_col_values_rest
        # The new first column (excluding a_1,1) will be the original first row (a_1,2, a_1,3, ..., a_1,N)
        transposed_first_col_values_rest = first_row_values[1:]

        transposed_stdin_lines = [str(N), ' '.join(map(str, transposed_first_row_values))]
        transposed_stdin_lines.extend(map(str, transposed_first_col_values_rest))
        transposed_stdin = '\n'.join(transposed_stdin_lines) + '\n'

        try:
            transposed_stdout = _run_program_internal(transposed_stdin)
            transposed_counts = list(map(int, transposed_stdout.strip().split()))
            
            assert len(transposed_counts) == 3, \
                f"Transposed input output has {len(transposed_counts)} ints instead of 3. Output: '{transposed_stdout.strip()}'"
            assert counts == transposed_counts, \
                f"Transposition check failed. Original counts: {counts}, Transposed counts: {transposed_counts}.\n" \
                f"Original stdin (N={N}):\n{stdin.strip()}\n" \
                f"Transposed stdin (N={N}):\n{transposed_stdin.strip()}"
        except AssertionError as e:
            # Re-raise explicit AssertionErrors from _run_program_internal or the comparison
            raise e
        except Exception as e:
            # Catch any other unexpected errors during subprocess call or parsing transposed_stdout
            raise AssertionError(f"Error during transposition check: {type(e).__name__}: {e}\n"
                                 f"Transposed stdin:\n{transposed_stdin.strip()}")