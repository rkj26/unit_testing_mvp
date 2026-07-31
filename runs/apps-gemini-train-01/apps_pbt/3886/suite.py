import random
import string
import io

# --- Constants for the problem definition ---
S0_STR = "What are you doing at the end of the world? Are you busy? Will you save us?"
P1_STR = "What are you doing while sending "  # Length 27
P2_STR = "? Are you busy? Will you send "    # Length 29
P3_STR = "?"                                # Length 1

P1_LEN = len(P1_STR)
P2_LEN = len(P2_STR)
P3_LEN = len(P3_STR)

# Max k value as per problem constraints
MAX_K = 10**18

# --- Precompute lengths L_n ---
# L_n = 2 * L_{n-1} + P1_LEN + P2_LEN + P3_LEN
# L_0 = len(S0_STR) = 69
# We precompute lengths up to an N where L_N will surely exceed MAX_K.
# L_60 is approx 1.4 * 10^18. L_61 is approx 2.8 * 10^18. So 61 is a good upper bound.
MAX_N_FOR_L_K_CALC = 61
L_VALS = {0: len(S0_STR)}
for i in range(1, MAX_N_FOR_L_K_CALC + 1):
    L_VALS[i] = 2 * L_VALS[i-1] + P1_LEN + P2_LEN + P3_LEN
    # Prevent overflow for very large N if we were to compute beyond MAX_K
    # Although not strictly needed as MAX_N_FOR_L_K_CALC already handles it.
    if L_VALS[i] > MAX_K + 100: # Add a margin
        L_VALS[i] = MAX_K + 100 

# --- Memoization for direct string construction for small N in check() ---
# This is used to verify queries for small N by directly building f_N.
# L_4 is 1959 characters. Building f_4 and storing it is fast.
# L_5 is 3975 characters. For q=10, generating 10 f_5 strings might be 40k chars total. Still very fast.
# MAX_N_DIRECT_COMPUTE = 5 is a reasonable choice for sound direct verification.
MAX_N_DIRECT_COMPUTE = 5
memo_f_strings = {0: S0_STR}

def get_f_string_for_check(n: int) -> str:
    """
    Recursively builds f_n string for small n.
    Raises ValueError if n exceeds MAX_N_DIRECT_COMPUTE to prevent re-solving the problem.
    """
    if n > MAX_N_DIRECT_COMPUTE:
        raise ValueError(f"Direct string computation limited to N <= {MAX_N_DIRECT_COMPUTE}. Got n={n}.")
    if n not in memo_f_strings:
        f_prev = get_f_string_for_check(n - 1)
        memo_f_strings[n] = P1_STR + f_prev + P2_STR + f_prev + P3_STR
    return memo_f_strings[n]


def gen_input() -> str:
    buffer = io.StringIO()
    
    # Generate q: number of queries
    # Prioritize boundary q values (1, 10) and intermediate values (2, 5)
    q_choices = [1, 2, 5, 10]
    q = random.choice(q_choices) if random.random() < 0.7 else random.randint(1, 10) # 70% chance of boundary q, 30% random

    buffer.write(f"{q}\n")
    
    queries = []
    for _ in range(q):
        n_val = -1
        k_val = -1
        
        # Determine the type of n (0 <= n <= 10^5)
        n_type = random.choice(['small', 'medium_L_k', 'large_L_k', 'boundary'])
        
        if n_type == 'small':
            n_val = random.randint(0, MAX_N_DIRECT_COMPUTE)
        elif n_type == 'medium_L_k':
            # N where L_n can be comparable to k (up to MAX_K)
            n_val = random.randint(MAX_N_DIRECT_COMPUTE + 1, MAX_N_FOR_L_K_CALC)
        elif n_type == 'large_L_k':
            # N where L_n is definitely > MAX_K
            n_val = random.randint(MAX_N_FOR_L_K_CALC + 1, 10**5)
        elif n_type == 'boundary':
            n_val = random.choice([0, 1, MAX_N_DIRECT_COMPUTE, MAX_N_DIRECT_COMPUTE + 1, MAX_N_FOR_L_K_CALC, MAX_N_FOR_L_K_CALC + 1, 10**5])

        # Get L_n for the chosen n_val, using MAX_K + 100 as a proxy for effectively infinite length
        current_Ln = L_VALS.get(n_val, MAX_K + 100) 

        # Determine the type of k (1 <= k <= 10^18)
        k_type = random.choice(['small', 'medium', 'large', 'out_of_bounds', 'fixed_part', 'recursive_part', 'boundary_k'])
        
        if k_type == 'small':
            # k in the very beginning of the string
            k_val = random.randint(1, min(current_Ln, 100)) if current_Ln >= 1 else 1
        elif k_type == 'medium':
            # k somewhere in the middle (if current_Ln allows)
            k_val = random.randint(int(min(current_Ln, MAX_K) * 0.1), int(min(current_Ln, MAX_K) * 0.9))
            k_val = max(1, k_val)
        elif k_type == 'large':
            # k near the end of the string (if current_Ln allows) or near MAX_K
            k_val = random.randint(int(min(current_Ln, MAX_K) * 0.9), min(current_Ln, MAX_K))
            k_val = max(1, k_val)
        elif k_type == 'out_of_bounds':
            # k is greater than L_n (only possible if L_n <= MAX_K)
            if current_Ln < MAX_K:
                k_val = random.randint(int(current_Ln) + 1, MAX_K)
            else: # If current_Ln is effectively > MAX_K, k cannot be out of bounds
                k_val = random.randint(1, MAX_K) # Fallback to a valid k
            k_val = max(1, k_val)
        elif k_type == 'fixed_part':
            # k falls into one of the P1, P2, P3 fixed segments
            if n_val == 0: # For n=0, S0_STR is the "fixed part"
                k_val = random.randint(1, len(S0_STR))
            else:
                choice = random.choice(['P1', 'P2', 'P3'])
                if choice == 'P1':
                    k_val = random.randint(1, P1_LEN)
                elif choice == 'P2':
                    prev_L = L_VALS.get(n_val - 1, MAX_K + 100)
                    start_k = P1_LEN + prev_L + 1
                    end_k = P1_LEN + prev_L + P2_LEN
                    if start_k > end_k or start_k > MAX_K: # Handle cases where prev_L is very small or start_k is too large
                        k_val = random.randint(1, MAX_K) # Fallback
                    else:
                        k_val = random.randint(int(max(1, start_k)), int(min(MAX_K, end_k)))
                elif choice == 'P3':
                    prev_L = L_VALS.get(n_val - 1, MAX_K + 100)
                    start_k = P1_LEN + 2 * prev_L + P2_LEN + 1
                    end_k = P1_LEN + 2 * prev_L + P2_LEN + P3_LEN
                    if start_k > end_k or start_k > MAX_K:
                        k_val = random.randint(1, MAX_K) # Fallback
                    else:
                        k_val = random.randint(int(max(1, start_k)), int(min(MAX_K, end_k)))
        elif k_type == 'recursive_part':
            # k falls into one of the f_{n-1} recursive segments
            if n_val == 0: # For n=0, it's all f_0
                k_val = random.randint(1, len(S0_STR))
            else:
                choice = random.choice(['f_prev_1', 'f_prev_2'])
                prev_L = L_VALS.get(n_val - 1, MAX_K + 100)
                if prev_L == 0: # If previous string is empty, no recursive part
                     k_val = random.randint(1, MAX_K) # Fallback
                else:
                    if choice == 'f_prev_1':
                        start_k = P1_LEN + 1
                        end_k = P1_LEN + prev_L
                    elif choice == 'f_prev_2':
                        start_k = P1_LEN + prev_L + P2_LEN + 1
                        end_k = P1_LEN + 2 * prev_L + P2_LEN
                    
                    if start_k > end_k or start_k > MAX_K:
                        k_val = random.randint(1, MAX_K) # Fallback
                    else:
                        k_val = random.randint(int(max(1, start_k)), int(min(MAX_K, end_k)))
        elif k_type == 'boundary_k':
            # Specific boundary points for k (1, L_n, L_n+1, MAX_K, etc.)
            boundary_points = [1, 2]
            if n_val > 0:
                prev_L = L_VALS.get(n_val - 1, MAX_K + 100)
                boundary_points.extend([
                    P1_LEN, P1_LEN + 1, # around first fixed part
                    P1_LEN + prev_L, P1_LEN + prev_L + 1, # around first recursive part
                    P1_LEN + prev_L + P2_LEN, P1_LEN + prev_L + P2_LEN + 1, # around second fixed part
                    P1_LEN + 2*prev_L + P2_LEN, P1_LEN + 2*prev_L + P2_LEN + 1, # around second recursive part
                ])
            
            # Add boundary points related to current_Ln and MAX_K
            if current_Ln < MAX_K:
                boundary_points.extend([int(current_Ln) - 1, int(current_Ln), int(current_Ln) + 1])
            boundary_points.extend([MAX_K - 1, MAX_K])
            
            # Filter and choose a k from valid boundary points
            valid_boundary_k_options = [int(p) for p in boundary_points if 1 <= p <= MAX_K]
            if not valid_boundary_k_options:
                k_val = random.randint(1, MAX_K) # Fallback
            else:
                k_val = random.choice(valid_boundary_k_options)

        # Final clamping for k
        k_val = max(1, min(k_val, MAX_K))
        queries.append((n_val, k_val))
        buffer.write(f"{n_val} {k_val}\n")
            
    return buffer.getvalue()


def check(stdin: str, stdout: str) -> None:
    input_lines = stdin.strip().split('\n')
    q = int(input_lines[0])
    
    queries = []
    for i in range(1, q + 1):
        n_str, k_str = input_lines[i].split()
        queries.append((int(n_str), int(k_str)))

    # Property 1: Output length must match q
    assert len(stdout) == q, f"Output length mismatch: Expected {q} chars, got {len(stdout)} chars."

    # Property 2: Output characters must be valid
    # Valid characters are letters, spaces, question marks, and the dot (for out-of-bounds)
    valid_chars_set = set(string.ascii_letters + string.whitespace + '? .')
    for char in stdout:
        assert char in valid_chars_set, f"Output contains invalid character: '{char}'"

    # Property 3: Verify each query result
    for i in range(q):
        n, k = queries[i]
        c_out = stdout[i]

        expected_char = None
        
        # Case A: n is small enough for direct string construction
        if n <= MAX_N_DIRECT_COMPUTE:
            f_n_str = get_f_string_for_check(n) # Safely computes f_n for small n
            if k > len(f_n_str):
                expected_char = '.'
            else:
                expected_char = f_n_str[k-1]
        else:
            # Case B: n is too large for direct string construction, check fixed parts and bounds.
            
            # Determine effective length of f_n. If n is very large, L_n will exceed MAX_K.
            # We use MAX_K + 100 as a proxy for "effectively infinite" length for k up to MAX_K.
            current_Ln = L_VALS.get(n, MAX_K + 100) 

            # Check if k is out of bounds
            if k > current_Ln:
                expected_char = '.'
            # Check for characters in the fixed prefix/suffix parts of f_n.
            # (Recursive parts f_{n-1} cannot be verified without solving or making sub-queries,
            # so we only verify the non-recursive fixed string parts.)
            else: # k is within bounds and n > MAX_N_DIRECT_COMPUTE
                len_prev_str_part = L_VALS.get(n-1, MAX_K + 100) # Length of f_{n-1} for placement logic

                # Part 1: "What are you doing while sending " (P1_STR)
                if 1 <= k <= P1_LEN:
                    expected_char = P1_STR[k-1]
                # Part 2: "? Are you busy? Will you send " (P2_STR)
                elif P1_LEN + len_prev_str_part < k <= P1_LEN + len_prev_str_part + P2_LEN:
                    adjusted_k = k - (P1_LEN + len_prev_str_part)
                    expected_char = P2_STR[adjusted_k-1]
                # Part 3: "?" (P3_STR)
                elif P1_LEN + 2 * len_prev_str_part + P2_LEN < k <= P1_LEN + 2 * len_prev_str_part + P2_LEN + P3_LEN:
                    adjusted_k = k - (P1_LEN + 2 * len_prev_str_part + P2_LEN)
                    expected_char = P3_STR[adjusted_k-1]
                # If k falls into the f_{n-1} recursive parts, we cannot make an assertion.
                # This is sound, as we are not re-solving the problem.

        if expected_char is not None:
            assert c_out == expected_char, \
                f"Query {i+1} (n={n}, k={k}): Expected '{expected_char}', got '{c_out}'."