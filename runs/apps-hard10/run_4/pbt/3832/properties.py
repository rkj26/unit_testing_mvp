def prop_output_length_matches_ceil_n_over_2(run, x):
    """PROPERTY: Output must contain exactly ceil(n/2) numbers."""
    lines = x.strip().splitlines()
    n = int(lines[0])
    output = run(x).strip()
    if not output:
        # No numbers printed — invalid per spec
        assert False, "Empty output"
    out_numbers = output.split()
    expected_len = (n + 1) // 2  # ceil(n/2)
    assert len(out_numbers) == expected_len, f"Expected {expected_len} numbers, got {len(out_numbers)}"

def prop_non_decreasing_sequence(run, x):
    """PROPERTY: Output numbers are non-decreasing in k."""
    output = run(x).strip()
    if not output:
        return
    nums = list(map(int, output.split()))
    for i in range(1, len(nums)):
        assert nums[i] >= nums[i - 1], f"Output not non-decreasing: {nums}"

def prop_reverse_input_same_output(run, x):
    """PROPERTY: Reversing the sequence of hills yields same output."""
    lines = x.strip().splitlines()
    n = int(lines[0])
    hills = list(map(int, lines[1].split()))
    reversed_hills = list(reversed(hills))
    new_input = f"{n}\n" + " ".join(map(str, reversed_hills)) + "\n"
    out1 = run(x).strip()
    out2 = run(new_input).strip()
    # Both outputs must have same length (ceil(n/2)) and same values
    # because problem is symmetric under reversal.
    assert out1 == out2, f"Reversed input changed output: {out1} vs {out2}"

def prop_add_constant_to_all_heights(run, x):
    """PROPERTY: Adding a constant C to all heights does not decrease output values."""
    lines = x.strip().splitlines()
    n = int(lines[0])
    hills = list(map(int, lines[1].split()))
    C = 1000  # positive constant
    new_hills = [h + C for h in hills]
    new_input = f"{n}\n" + " ".join(map(str, new_hills)) + "\n"
    out_orig = list(map(int, run(x).strip().split()))
    out_new = list(map(int, run(new_input).strip().split()))
    # Increasing heights never makes it harder to achieve k houses,
    # because we can still decrease them if needed, but now they start higher.
    # So required hours for each k should not increase.
    for k in range(len(out_orig)):
        assert out_new[k] <= out_orig[k], f"For k={k+1}, hours increased after adding constant: {out_new[k]} > {out_orig[k]}"

def prop_merge_two_independent_instances(run, x):
    """PROPERTY: Concatenating two independent hill sequences yields output where min hours for total k is at most sum of individual mins for some split of k."""
    # This is a relaxed check: we take two small instances, concatenate them,
    # and check that the output for the combined instance respects subadditivity.
    # We'll generate a simple case manually to avoid randomness.
    # Use n1=3, heights1 = [1,1,1]; n2=3, heights2 = [1,1,1]
    n1, h1 = 3, [1, 1, 1]
    n2, h2 = 3, [1, 1, 1]
    combined_n = n1 + n2
    combined_h = h1 + h2
    inp1 = f"{n1}\n" + " ".join(map(str, h1)) + "\n"
    inp2 = f"{n2}\n" + " ".join(map(str, h2)) + "\n"
    inp_combined = f"{combined_n}\n" + " ".join(map(str, combined_h)) + "\n"
    out1 = list(map(int, run(inp1).strip().split()))
    out2 = list(map(int, run(inp2).strip().split()))
    out_comb = list(map(int, run(inp_combined).strip().split()))
    # For any k_comb (1..ceil(combined_n/2)), there exists k1 <= len(out1), k2 <= len(out2)
    # with k1+k2 >= k_comb such that out_comb[k_comb-1] <= out1[k1-1] + out2[k2-1].
    # This is a necessary condition because one way to achieve k_comb houses in combined
    # is to take k1 from first part and k2 from second.
    for k_comb in range(1, len(out_comb) + 1):
        feasible = False
        for k1 in range(0, len(out1) + 1):
            for k2 in range(0, len(out2) + 1):
                if k1 + k2 >= k_comb:
                    if out_comb[k_comb - 1] <= (out1[k1 - 1] if k1 > 0 else 0) + (out2[k2 - 1] if k2 > 0 else 0):
                        feasible = True
                        break
            if feasible:
                break
        assert feasible, f"Subadditivity violated for k={k_comb}"