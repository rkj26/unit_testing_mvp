```python
    import random
    import math
    from collections import Counter

    # Helper function to calculate ceil(log2 K) for K >= 1.
    # The problem states: "if K = 1, then k = 0".
    # For K > 1, k is the smallest integer such that K <= 2^k.
    # This is equivalent to (K-1).bit_length() for K >= 1.
    # Examples:
    # K=1: (1-1).bit_length() = 0.bit_length() = 0. Correct.
    # K=2: (2-1).bit_length() = 1.bit_length() = 1. Correct.
    # K=3: (3-1).bit_length() = 2.bit_length() = 2. Correct.
    # K=4: (4-1).bit_length() = 3.bit_length() = 2. Correct.
    def ceil_log2_K(K):
        if K == 0: # Problem constraints (n >= 1) imply K >= 1, so this branch should not be reached.
            return 0 
        return (K - 1).bit_length()

    def gen_input() -> str:
        # Options for n and I to cover boundaries and typical ranges.
        n_options = [1, 2, 5, 10, 50, 100, 1000, 10000, 4 * 10**4, 4 * 10**5]
        I_options = [1, 2, 5, 10, 50, 100, 1000, 10000, 10**5, 10**6, 10**7, 10**8]

        # Choose n, giving higher probability to random values within the range.
        n = random.choice(n_options)
        if random.random() < 0.7:
            n = random.randint(1, 4 * 10**5)
        n = max(1, n) # Ensure n >= 1 as per constraints

        # Choose I, giving higher probability to random values within the range.
        I = random.choice(I_options)
        if random.random() < 0.7:
            I = random.randint(1, 10**8)
        I = max(1, I) # Ensure I >= 1 as per constraints

        a = []
        
        # Strategies for generating array elements to cover diverse scenarios:
        # - All same values (K=1)
        # - Few distinct values (e.g., K << N)
        # - Many distinct values (e.g., K ~ N, or all unique)
        # - Values near boundaries (0, 10^9)
        # - Values that might trigger k-boundary conditions (K is a power of 2 or power of 2 + 1)
        # - Sorted/consecutive values
        # - Small value range, large value range
        strategy = random.randint(0, 7)

        if strategy == 0: # All elements are the same value
            val = random.randint(0, 10**9)
            a = [val] * n
        elif strategy == 1: # Few distinct values, many duplicates
            num_distinct = random.randint(1, min(n, 100)) # Small number of distinct values
            distinct_values = sorted(random.sample(range(0, 10**9), num_distinct))
            a = random.choices(distinct_values, k=n)
        elif strategy == 2: # Many distinct values (up to N), often unique elements
            if n < 4 * 10**5 and n <= 10**9: # Max N is 4e5, avoid huge range.
                num_distinct = random.randint(max(1, n // 2), n) # A significant number of distinct values
                # Create distinct values from a range wide enough to fit them without too much collision
                start_val = random.randint(0, max(0, 10**9 - (num_distinct * 2 + 1))) 
                distinct_values = sorted(random.sample(range(start_val, start_val + num_distinct * 2), num_distinct))
                a = random.choices(distinct_values, k=n)
            else: # For max N or very large num_distinct, just generate fully random elements
                a = [random.randint(0, 10**9) for _ in range(n)]
        elif strategy == 3: # Consecutive values (sorted array)
            if n <= 10**9 + 1: # Ensure the range of values doesn't exceed 10^9
                start_val = random.randint(0, max(0, 10**9 - n + 1))
                a = list(range(start_val, start_val + n))
            else:
                a = [random.randint(0, 10**9) for _ in range(n)] # Fallback
        elif strategy == 4: # Values concentrated near 0 and 10^9, or other specific boundary values
            edge_vals = [0, 1, 10**9 - 1, 10**9]
            if random.random() < 0.5 and n >= 2: # Use just two extreme values
                v1, v2 = random.sample([0, 10**9], 2)
                a = [v1] * (n // 2) + [v2] * (n - n // 2)
            else: # Use a mix of extreme values and general random values
                a = [random.choice(edge_vals + [random.randint(0, 10**9)]) for _ in range(n)]
            random.shuffle(a) # Shuffle to make order non-trivial
        elif strategy == 5: # Fully random values
            a = [random.randint(0, 10**9) for _ in range(n)]
        elif strategy == 6: # Values with K just before/after power of 2, to test ceil_log2_K logic
            possible_K_targets = [1, 2, 3, 4, 7, 8, 9, 15, 16, 17, 31, 32, 33]
            target_K = random.choice(possible_K_targets)
            target_K = min(target_K, n) # K cannot exceed N
            
            distinct_vals = random.sample(range(0, 10**9), target_K)
            a = random.choices(distinct_vals, k=n)
        elif strategy == 7: # All values fall within a relatively small range
            base = random.randint(0, max(0, 10**9 - 100))
            a = [random.randint(base, base + 99) for _ in range(n)]

        input_str = f"{n} {I}\n"
        input_str += " ".join(map(str, a)) + "\n"
        return input_str

    def check(stdin: str, stdout: str) -> None:
        # 1. Parse Input
        lines = stdin.strip().split('\n')
        n_str, I_str = lines[0].split()
        n_int = int(n_str)
        I_int = int(I_str)
        a_list = list(map(int, lines[1].split()))

        assert len(a_list) == n_int, \
            f"PARSING ERROR: Expected {n_int} elements in array, but found {len(a_list)}. Input: {stdin.strip()}"

        # 2. Parse Output
        try:
            result_changed_count = int(stdout.strip())
        except ValueError:
            raise AssertionError(f"OUTPUT FORMAT ERROR: Output is not a single integer. Got: '{stdout.strip()}'. Input: {stdin.strip()}")

        # 3. Assert output format and basic bounds
        # The number of changed elements must be non-negative and at most n.
        assert 0 <= result_changed_count <= n_int, \
            f"OUTPUT VALUE ERROR: Result changed count {result_changed_count} is out of valid range [0, {n_int}]. Input: {stdin.strip()}"

        # Calculate total bits available from disk size
        bits_disk = I_int * 8

        # Calculate k_max_from_disk: the maximum number of bits `k` per value that can fit on disk.
        # This is `floor((I*8)/n)`.
        k_max_from_disk_floor = bits_disk // n_int

        # 4. Strong Check 1: If k_max_from_disk_floor is 0.
        # This implies that `(I*8)/n < 1`. Even 1 bit per value (`k=1`) would exceed disk capacity.
        # The ONLY way to fit the file is if `k=0`, which means there must be exactly `K=1` distinct value.
        # To achieve `K=1` with minimal changes, we must choose `l=r=X` for some value `X` from the array.
        # `X` should be the most frequent value in the original array. All other values are changed to `X`.
        if k_max_from_disk_floor == 0:
            counts = Counter(a_list)
            # The problem guarantees n >= 1, so a_list is non-empty, and counts will not be empty.
            max_frequency = max(counts.values())
            
            # The expected number of changes is n - (count of the most frequent element).
            expected_changes_for_K1 = n_int - max_frequency
            assert result_changed_count == expected_changes_for_K1, \
                f"LOGIC ERROR: `k_max_from_disk_floor` is 0 (disk too small for >1 distinct values). " \
                f"Expected {expected_changes_for_K1} changes (to achieve K=1), but program output {result_changed_count}. Input: {stdin.strip()}"
            return # If this exact property holds, no further checks are needed for this specific input.

        # 5. Strong Check 2: If the original array already fits the disk.
        # This check is applicable when `k_max_from_disk_floor > 0`.
        K_original = len(set(a_list))
        k_original_bits = ceil_log2_K(K_original)
        
        bits_needed_original = n_int * k_original_bits

        if bits_needed_original <= bits_disk:
            # If the original array already fits, the optimal number of changes MUST be 0.
            assert result_changed_count == 0, \
                f"LOGIC ERROR: Original array fits on disk ({bits_needed_original} bits needed <= {bits_disk} bits available). " \
                f"Expected 0 changes, but program output {result_changed_count}. Input: {stdin.strip()}"
            return # If this exact property holds, no further checks are needed for this specific input.

        # 6. Remaining cases:
        # - `result_changed_count` is > 0.
        # - The original array does NOT fit the disk.
        # - `k_max_from_disk_floor` is > 0 (meaning K can be > 1).
        # In these scenarios, the program must have found an optimal `l, r` and compressed the array.
        # Verifying the optimality of `result_changed_count` in these cases would require re-implementing
        # the problem's solver, which is against the principles of property-based testing.
        # Without a certificate (like the `l, r` values chosen by the program) or the ability to
        # perform metamorphic testing by re-running the program on transformed inputs (which is not
        # supported by the given function signature), no further sound and non-trivial assertions
        # can be made for these cases.
```