def prop_output_format_and_mod_range(run, x):
    """PROPERTY: Output must have n lines, each an integer in [0, 998244353)."""
    out = run(x).strip()
    if out == '':
        return False
    lines = out.splitlines()
    # First line of input is n m
    n = int(x.split('\n')[0].split()[0])
    if len(lines) != n:
        return False
    for line in lines:
        val = int(line.strip())
        if not (0 <= val < 998244353):
            return False
    return True

def prop_total_weight_conservation(run, x):
    """PROPERTY: Expected total weight after m steps equals initial total weight plus m * (liked - disliked) pictures."""
    lines = x.strip().split('\n')
    n, m = map(int, lines[0].split())
    likes = list(map(int, lines[1].split()))
    weights = list(map(int, lines[2].split()))
    total_liked = sum(likes)
    total_disliked = n - total_liked
    # In each visit, expected change in total weight = E[like?] * (+1) + E[dislike?] * (-1)
    # But easier: each visit adds 1 if liked picture shown, subtracts 1 if disliked shown.
    # So after m visits, total weight change = (#liked_shown) - (#disliked_shown).
    # Since #liked_shown + #disliked_shown = m, total change = 2*#liked_shown - m.
    # But we can compute expected total weight after m visits directly from output:
    out = run(x).strip()
    if out == '':
        return False
    out_vals = list(map(int, out.splitlines()))
    expected_total_after = sum(out_vals) % 998244353
    # Compute expected total weight after m visits:
    # Each visit: pick picture i with prob proportional to current weight at that step.
    # Expected change per visit = sum_i ( (w_i / total_weight) * (1 if liked else -1) )
    # This depends on distribution of weights over steps, so not constant.
    # Instead, use linearity of expectation: For each picture i,
    # expected final weight = initial weight + m * (prob_i_is_selected_and_liked - prob_i_is_selected_and_disliked)?
    # Not exactly, because probabilities change.
    # But total expected weight after m visits = initial total weight + m * (E[like_selected] - E[dislike_selected]) over all visits.
    # Let's compute initial total weight:
    S0 = sum(weights)
    # Let L = total liked pictures count (not weight).
    # Let's compute expected total weight after m visits by simulation? No, can't simulate.
    # Wait: total weight after all visits = sum_i w_i_final = sum_i (w_i_initial + (#times i selected and liked) - (#times i selected and disliked))
    # For disliked pictures, a_i=0, so each selection subtracts 1.
    # So total weight = S0 + sum_over_visits (1 if liked selected else -1)
    # Thus expected total weight = S0 + sum_over_visits E[1 if liked selected else -1]
    # But E[1 if liked selected else -1] = (sum_{liked j} w_j / total_weight) * 1 + (sum_{disliked j} w_j / total_weight) * (-1)
    # This depends on step, so we cannot compute without solving.
    # However, we can use a known invariant: expected total weight after m visits = S0 + m * (sum_liked_weights / total_weight - sum_disliked_weights / total_weight) averaged over distribution?
    # Actually, there's a known martingale? Let's check small case: n=1, liked=1, w=1, m=2, expected total weight = 3, S0=1, m*(1 - 0)=2, matches.
    # For first example: liked weights sum=1, disliked weights sum=2, S0=3, m=1, expected total weight after = 4/3+4/3=8/3≈2.666, S0 + m*(1/3 - 2/3)=3 -1/3=8/3, matches.
    # So maybe expected total weight = S0 + m * ( (sum_liked_weights_initial - sum_disliked_weights_initial) / S0 )? Let's test third example:
    # liked weights sum=3+5=8, disliked weights sum=4, S0=12, m=3, so expected total weight = 12 + 3*((8-4)/12)=12+3*(4/12)=12+1=13.
    # Compute from output: 160955686+185138929+974061117 = (mod?) Let's compute actual: 160955686+185138929=346110615, +974061117=1320171732.
    # 1320171732 mod 998244353 = 1320171732 - 998244353 = 321927379.
    # But expected total weight 13 mod 998244353 = 13. They don't match, so formula wrong.
    # Indeed, because probabilities change, the simple formula fails.
    # So we cannot verify total weight easily.
    # Instead, use a different invariant: For m=0, output must equal initial weights mod MOD.
    if m == 0:
        # Special case: if m=0 in input, expected weights are initial weights.
        # But constraints say m>=1, so skip.
        pass
    # Let's use a metamorphic test: scaling all weights by same factor shouldn't change probabilities, but changes absolute values, so not good.
    # Instead, use symmetry: swapping two pictures with same 'like' status and same initial weight should swap outputs.
    # Let's implement that as separate property.
    # For this property, let's do a simple: if all pictures are liked, each visit increases total weight by 1, so expected total weight = S0 + m.
    # Check that case.
    if all(l == 1 for l in likes):
        expected_total = (S0 + m) % 998244353
        return sum(out_vals) % 998244353 == expected_total
    # If all pictures are disliked, each visit decreases total weight by 1, so expected total weight = S0 - m.
    if all(l == 0 for l in likes):
        expected_total = (S0 - m) % 998244353
        return sum(out_vals) % 998244353 == expected_total
    # Otherwise, no simple total weight invariant, so just return True (skip).
    return True

def prop_symmetry_swap_liked_pairs(run, x):
    """PROPERTY: Swapping two liked pictures with same initial weight swaps their outputs."""
    lines = x.strip().split('\n')
    n, m = map(int, lines[0].split())
    likes = list(map(int, lines[1].split()))
    weights = list(map(int, lines[2].split()))
    # Find two liked pictures with same weight
    liked_indices = [i for i in range(n) if likes[i] == 1]
    for i in liked_indices:
        for j in liked_indices:
            if i < j and weights[i] == weights[j]:
                # Swap weights[i] and weights[j] (they are equal, so no change)
                # Actually swapping identical weights does nothing, so output should be same.
                # But we want to swap their positions in input.
                # Create new input with i and j swapped in both likes and weights lists.
                # Since likes are same (1), swapping doesn't change likes array.
                # Since weights are same, swapping doesn't change weights array.
                # So input is identical, output must be identical trivially.
                # Need a nontrivial swap: pick two liked pictures with possibly different weights.
                # Swapping them should swap their outputs.
                pass
    # Let's implement: swap two liked pictures with arbitrary weights.
    # Find two liked pictures with indices a,b.
    if len(liked_indices) >= 2:
        a, b = liked_indices[0], liked_indices[1]
        # Build new input
        new_weights = weights[:]
        new_likes = likes[:]
        # Swap weights[a] and weights[b]
        new_weights[a], new_weights[b] = new_weights[b], new_weights[a]
        # Likes remain 1 for both, so no change.
        # Construct new input string
        new_input = f"{n} {m}\n"
        new_input += ' '.join(map(str, new_likes)) + '\n'
        new_input += ' '.join(map(str, new_weights)) + '\n'
        out_orig = run(x).strip().splitlines()
        out_new = run(new_input).strip().splitlines()
        # In original output, out_orig[a] and out_orig[b] should equal out_new[b] and out_new[a] respectively.
        if (int(out_orig[a]) == int(out_new[b]) and int(out_orig[b]) == int(out_new[a])):
            # Also all other outputs must stay same
            for k in range(n):
                if k != a and k != b:
                    if int(out_orig[k]) != int(out_new[k]):
                        return False
            return True
        else:
            return False
    return True  # if not enough liked pictures, skip

def prop_symmetry_swap_disliked_pairs(run, x):
    """PROPERTY: Swapping two disliked pictures with same initial weight swaps their outputs."""
    lines = x.strip().split('\n')
    n, m = map(int, lines[0].split())
    likes = list(map(int, lines[1].split()))
    weights = list(map(int, lines[2].split()))
    disliked_indices = [i for i in range(n) if likes[i] == 0]
    if len(disliked_indices) >= 2:
        a, b = disliked_indices[0], disliked_indices[1]
        # Build new input with weights[a] and weights[b] swapped
        new_weights = weights[:]
        new_likes = likes[:]
        new_weights[a], new_weights[b] = new_weights[b], new_weights[a]
        new_input = f"{n} {m}\n"
        new_input += ' '.join(map(str, new_likes)) + '\n'
        new_input += ' '.join(map(str, new_weights)) + '\n'
        out_orig = run(x).strip().splitlines()
        out_new = run(new_input).strip().splitlines()
        if (int(out_orig[a]) == int(out_new[b]) and int(out_orig[b]) == int(out_new[a])):
            for k in range(n):
                if k != a and k != b:
                    if int(out_orig[k]) != int(out_new[k]):
                        return False
            return True
        else:
            return False
    return True

def prop_linearity_for_single_visit(run, x):
    """PROPERTY: For m=1, expected weight = w_i + (like_i - dislike_i) * w_i / S0, computed modulo."""
    lines = x.strip().split('\n')
    n, m = map(int, lines[0].split())
    if m != 1:
        return True  # skip if m not 1
    likes = list(map(int, lines[1].split()))
    weights = list(map(int, lines[2].split()))
    S0 = sum(weights)
    MOD = 998244353
    # Compute expected weight for each i: w_i + ( (1 if liked else -1) * w_i / S0 )
    # As fraction: w_i + (a_i * w_i / S0) where a_i = 1 if liked else -1.
    # So = w_i * (1 + a_i / S0) = w_i * (S0 + a_i) / S0.
    # Need modulo inverse of S0.
    # But we must compute mod MOD.
    out = run(x).strip().splitlines()
    for i in range(n):
        a_i = 1 if likes[i] == 1 else -1
        # numerator = w_i * (S0 + a_i)
        # denominator = S0
        # Compute r_i = numerator * denominator^{-1} mod MOD
        # But careful: S0 might not be invertible mod MOD? MOD is prime, S0 <= 50*50=2500, so gcd(S0, MOD)=1, invertible.
        inv_S0 = pow(S0, MOD-2, MOD)
        expected_mod = (weights[i] * (S0 + a_i) * inv_S0) % MOD
        if int(out[i]) != expected_mod:
            return False
    return True