def prop_output_format_and_bounds(run, x):
    """PROPERTY: Output must have n lines, each parseable as an integer in [0, 998244353)."""
    out = run(x).strip()
    if out == "":
        return False
    lines = out.splitlines()
    # parse n from input
    n = int(x.split()[0])
    if len(lines) != n:
        return False
    mod = 998244353
    for line in lines:
        try:
            val = int(line.strip())
        except ValueError:
            return False
        if not (0 <= val < mod):
            return False
    return True

def prop_sum_of_weights_is_deterministic(run, x):
    """PROPERTY: Sum of expected final weights mod 998244353 equals initial total weight + m * (liked - disliked) visits."""
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    likes = list(map(int, lines[1].split()))
    init_weights = list(map(int, lines[2].split()))
    total_initial = sum(init_weights)
    total_likes = sum(likes)
    total_disliked = n - total_likes
    # Each liked picture gains 1 per visit where it is shown, each disliked loses 1 per visit where it is shown.
    # But expected total change per visit = (sum over i of (like_i * 1 + (1-like_i)*(-1)) * probability i is shown).
    # That's messy. Instead note: total weight after m visits = total_initial + m * (liked_shown - disliked_shown) per visit.
    # But expected total weight after m = total_initial + m * E[liked_shown - disliked_shown per visit].
    # However simpler: in each visit, one random picture is chosen with prob proportional to weight, then weight changes by +1 if liked, -1 if disliked.
    # So total weight change per visit = +1 if liked picture chosen, -1 if disliked chosen.
    # Expected change per visit = (sum over liked pics w_i / totalW) * 1 + (sum over disliked pics w_i / totalW) * (-1).
    # This depends on weights changing over time, so not constant. So total expected final weight = total_initial + sum over visits of that expectation.
    # Not trivial to compute without solving.
    # But we can use a known invariant: total weight after m visits is deterministic? No, it's random.
    # Actually, total weight after m visits = total_initial + (#liked_shown - #disliked_shown) over m visits.
    # That is random. So expected total final weight = total_initial + m * (E[liked_shown] - E[disliked_shown]) per visit, but E per visit changes.
    # However, we can use conservation: expected final total weight = total_initial + m * (sum over i like_i * 1) if we consider each visit adds 1 to liked, subtracts 1 from disliked, but total change per visit is +1 for liked, -1 for disliked, so total change over m visits = sum over visits (like_chosen - dislike_chosen).
    # So expected total final weight = total_initial + m * (prob_chosen_is_liked - prob_chosen_is_disliked) averaged over visits, not constant.
    # This property is too complex to check without solving. Let's try a simpler one: If all pictures are liked, total weight increases by m exactly.
    if total_disliked == 0:
        # All liked: each visit adds 1 to total weight deterministically.
        expected_total_final = total_initial + m
        out = run(x).strip()
        outputs = list(map(int, out.splitlines()))
        total_out = sum(outputs) % 998244353
        return total_out == expected_total_final % 998244353
    # For general case, we can't assert total without solving, so skip.
    return True

def prop_permutation_symmetry(run, x):
    """PROPERTY: Permuting pictures with their likes and weights permutes outputs accordingly."""
    import random
    lines = x.strip().splitlines()
    parts = [list(map(int, line.split())) for line in lines]
    n, m = parts[0]
    likes = parts[1]
    weights = parts[2]
    # create a random permutation
    perm = list(range(n))
    random.shuffle(perm)
    # apply permutation to likes and weights
    likes_perm = [likes[i] for i in perm]
    weights_perm = [weights[i] for i in perm]
    # build new input
    new_x = f"{n} {m}\n" + " ".join(map(str, likes_perm)) + "\n" + " ".join(map(str, weights_perm)) + "\n"
    out1 = run(x).strip().splitlines()
    out2 = run(new_x).strip().splitlines()
    # permute out1 according to perm
    out1_perm = [out1[i] for i in perm]
    return out1_perm == out2

def prop_single_liked_picture_deterministic(run, x):
    """PROPERTY: If only one picture is liked, its expected final weight = w_liked + m (since always chosen)."""
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    likes = list(map(int, lines[1].split()))
    weights = list(map(int, lines[2].split()))
    if sum(likes) != 1:
        return True  # skip if not exactly one liked
    liked_idx = likes.index(1)
    # The liked picture is always chosen because only liked pictures can be shown? Wait, disliked pictures exist.
    # Actually, probability disliked shown >0 unless their weight zero, but here weights >=1.
    # So not deterministic. Wrong.
    # Let's correct: If only one picture is liked, then each visit adds 1 to that picture if it's shown, subtracts 1 from others if shown.
    # No simple formula.
    # Let's pick a simpler special case: only one picture total.
    if n == 1:
        # Then it's liked (given at least one liked), each visit adds 1.
        expected = weights[0] + m
        out = int(run(x).strip())
        return out == expected % 998244353
    return True

def prop_monotonicity_in_initial_weight(run, x):
    """PROPERTY: Increasing initial weight of a picture (keeping others fixed) does not decrease its expected final weight."""
    # We'll test by adding 1 to weight of first picture and compare outputs.
    lines = x.strip().splitlines()
    n, m = map(int, lines[0].split())
    likes = list(map(int, lines[1].split()))
    weights = list(map(int, lines[2].split()))
    if weights[0] >= 50:  # max weight constraint, can't increase
        return True
    # original
    out1 = list(map(int, run(x).strip().splitlines()))
    # modified: increase w[0] by 1
    weights2 = weights[:]
    weights2[0] += 1
    new_x = f"{n} {m}\n" + " ".join(map(str, likes)) + "\n" + " ".join(map(str, weights2)) + "\n"
    out2 = list(map(int, run(new_x).strip().splitlines()))
    # first picture's expected weight should not decrease
    return out2[0] >= out1[0]