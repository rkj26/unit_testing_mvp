import random

def gen_input() -> str:
    """
    Generates a single STDIN string for the problem, covering various test cases.
    It produces valid inputs satisfying the constraints: 1 <= K <= N <= 2000.
    """
    test_type = random.randint(0, 5)

    if test_type == 0:  # Minimum N, K
        N = 1
        K = 1
    elif test_type == 1:  # Small N, K
        N = random.randint(2, 5)
        K = random.randint(1, N)
    elif test_type == 2:  # Maximum N, K or around N/2
        N = 2000
        K = random.choice([1, N, N // 2, random.randint(1, N)])
    elif test_type == 3:  # K at boundaries for various N
        N = random.randint(6, 2000)
        K = random.choice([1, 2, N - 1, N])
    elif test_type == 4:  # K near center for various N
        N = random.randint(6, 2000)
        # Ensure K is within [1, N]
        K = random.randint(max(1, N // 2 - 5), min(N, N // 2 + 5))
    else:  # Wide random range
        N = random.randint(1, 2000)
        K = random.randint(1, N)
    
    return f"{N} {K}\n"

def check(stdin: str, stdout: str) -> None:
    """
    Asserts properties that the CORRECT output MUST satisfy.
    Raises AssertionError if any property is violated.
    """
    MOD = 10**9 + 7

    # 1. Parse input N, K
    try:
        N_str, K_str = stdin.strip().split()
        N = int(N_str)
        K = int(K_str)
    except ValueError:
        raise AssertionError(f"Invalid stdin format: '{stdin}'")
    
    # 2. Parse stdout
    try:
        output_val_str = stdout.strip()
        output_val = int(output_val_str)
    except ValueError:
        raise AssertionError(f"Output is not an integer: '{stdout}'")

    # 3. Assert output format and range
    assert output_val >= 0, f"Output {output_val} is negative for N={N}, K={K}."
    assert output_val < MOD, f"Output {output_val} is not modulo {MOD} for N={N}, K={K}."
    assert stdout.endswith('\n'), f"Output '{stdout}' does not end with a newline for N={N}, K={K}."
    assert output_val_str == stdout.strip(), \
        f"Output '{stdout}' has leading/trailing whitespace or extra lines for N={N}, K={K}."

    # 4. Assert specific known small cases (trivial to verify manually)
    # These are small N values where the answer can be easily derived or is given in examples.
    if N == 1 and K == 1:
        assert output_val == 1, f"Expected 1 for N=1, K=1, got {output_val}."
    elif N == 2 and K == 1:
        assert output_val == 1, f"Expected 1 for N=2, K=1, got {output_val} (from example)."
    elif N == 2 and K == 2: # By symmetry with K=1, and trivial to verify manually.
        assert output_val == 1, f"Expected 1 for N=2, K=2, got {output_val}."
    elif N == 3 and K == 1: # Verified through manual trace (sequences: (1,2,3), (1,3,2))
        assert output_val == 2, f"Expected 2 for N=3, K=1, got {output_val}."
    elif N == 3 and K == 2: # Verified through manual trace (sequences: (2,1,3), (3,1,2))
        assert output_val == 2, f"Expected 2 for N=3, K=2, got {output_val}."
    elif N == 3 and K == 3: # Verified through manual trace (sequences: (3,2,1), (2,3,1))
        assert output_val == 2, f"Expected 2 for N=3, K=3, got {output_val}."

    # 5. Metamorphic Relation / Known sequence property for K=1 or K=N (Catalan numbers)
    # It is a known property for this problem that the answer for K=1 or K=N
    # is the (N-1)-th Catalan number, C_{N-1}.
    # C_n = C(2n, n) / (n+1) mod p
    if K == 1 or K == N:
        catalan_idx = N - 1 # We need C_{N-1}
        
        # Precompute factorials and inverse factorials for combinations modulo MOD.
        # Max argument for nCr needed for C_n is 2n. So for C_{N-1}, it's 2*(N-1).
        MAX_COMB_ARG = 2 * catalan_idx if catalan_idx >= 0 else 0

        fact = [1] * (MAX_COMB_ARG + 1)
        inv = [1] * (MAX_COMB_ARG + 1)
        for i in range(1, MAX_COMB_ARG + 1):
            fact[i] = (fact[i-1] * i) % MOD
        
        # Compute modular inverse for fact[MAX_COMB_ARG] using Fermat's Little Theorem
        # (a^(p-2) mod p is inverse of a mod p for prime p)
        if MAX_COMB_ARG >= 0: # Ensure MAX_COMB_ARG is valid for indexing
            inv[MAX_COMB_ARG] = pow(fact[MAX_COMB_ARG], MOD - 2, MOD)
            for i in range(MAX_COMB_ARG - 1, -1, -1):
                inv[i] = (inv[i+1] * (i+1)) % MOD

        # Function to compute nCr_mod_p(n, r)
        def nCr_mod_p(n, r):
            if r < 0 or r > n:
                return 0
            return fact[n] * inv[r] % MOD * inv[n-r] % MOD
        
        # Calculate C_{catalan_idx} = nCr(2*catalan_idx, catalan_idx) * (catalan_idx + 1)^(-1) mod MOD
        if catalan_idx == 0: # C_0 = 1
            expected_catalan = 1
        else:
            term1 = nCr_mod_p(2 * catalan_idx, catalan_idx)
            term2 = pow(catalan_idx + 1, MOD - 2, MOD) # (n+1)^(-1) mod p
            expected_catalan = (term1 * term2) % MOD
        
        assert output_val == expected_catalan, \
            f"For N={N}, K={K} (K=1 or K=N), expected C_{catalan_idx} = {expected_catalan}, got {output_val}."