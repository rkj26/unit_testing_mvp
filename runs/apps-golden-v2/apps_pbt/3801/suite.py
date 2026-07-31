from hypothesis import given, strategies as st, settings, example
from harness import run_candidate  # run_candidate(stdin: str) -> stdout: str

# ----------------------------------------------------------------------------
# Problem 3801 -- "Nauuo and Pictures (hard version)".
#
# n pictures, each with a like-flag a_i in {0,1} (>=1 liked) and weight w_i.
# Over m visits, at each visit picture i is shown with prob w_i / sum(w).
# A liked picture (+1) and a disliked picture (-1) update their weight.
# Output E[w_i] after m visits, modulo p = 998244353 (as modular value r_i
# with 0 <= r_i < p and r_i * p_i == q_i).
#
# We CANNOT recompute the DP-based answer without solving the problem, so the
# suite relies on SOUND, solution-free properties:
#   1. FORMAT / RANGE: exactly n integer tokens, each in [0, p).
#   2. INTERNAL SYMMETRY: pictures with identical (a_i, w_i) must map to the
#      SAME expected weight (the whole process is symmetric under relabeling).
#   3. METAMORPHIC PERMUTATION EQUIVARIANCE: permuting the input pictures
#      permutes the outputs the same way.
#   4. EXACT CERTIFICATE for the all-liked sub-case: with every a_i = 1 the
#      process is a Polya urn with deterministic total, giving the closed form
#      E[w_i] = w_i * (S + m) / S  (S = sum of weights). This is verifiable
#      exactly WITHOUT solving the general problem, and it also covers n = 1
#      (E = w_1 + m) matching example 2.
# ----------------------------------------------------------------------------

MOD = 998244353


def _format(n, m, a, w):
    return "{} {}\n{}\n{}\n".format(n, m, " ".join(map(str, a)),
                                    " ".join(map(str, w)))


def _parse_ints(out):
    return [int(t) for t in out.split()]


# ---- edge-biased primitive strategies --------------------------------------
_N = st.one_of(st.just(1), st.just(2), st.just(3), st.just(50),
               st.integers(min_value=1, max_value=50))
_M = st.one_of(st.just(1), st.just(2), st.just(50),
               st.integers(min_value=1, max_value=50))
_W = st.one_of(st.just(1), st.just(50), st.integers(min_value=1, max_value=50))


@st.composite
def _core(draw):
    """General input, biased toward n/m/weight extremes and the three
    structurally distinct like-patterns (all-liked, exactly-one-liked, mixed)."""
    n = draw(_N)
    m = draw(_M)
    w = [draw(_W) for _ in range(n)]
    mode = draw(st.sampled_from(["all", "one", "mixed", "mixed"]))
    if mode == "all":
        a = [1] * n
    elif mode == "one":
        a = [0] * n
        a[draw(st.integers(min_value=0, max_value=n - 1))] = 1
    else:
        a = [draw(st.sampled_from([0, 1])) for _ in range(n)]
        if sum(a) == 0:
            a[draw(st.integers(min_value=0, max_value=n - 1))] = 1
    return (n, m, a, w)


@st.composite
def _core_dup(draw):
    """Heavy-duplicate inputs: a few (a, w) groups repeated many times, then
    shuffled, so identical pictures are scattered but present."""
    m = draw(_M)
    ngroups = draw(st.integers(min_value=1, max_value=4))
    a = []
    w = []
    for _ in range(ngroups):
        aa = draw(st.sampled_from([0, 1]))
        ww = draw(_W)
        cnt = draw(st.integers(min_value=1, max_value=12))
        for _ in range(cnt):
            if len(a) < 50:
                a.append(aa)
                w.append(ww)
    if len(a) == 0:
        a.append(1)
        w.append(draw(st.integers(min_value=1, max_value=50)))
    if sum(a) == 0:
        a[0] = 1
    n = len(a)
    perm = draw(st.permutations(list(range(n))))
    a = [a[i] for i in perm]
    w = [w[i] for i in perm]
    return (n, m, a, w)


@st.composite
def _core_all_liked(draw):
    n = draw(_N)
    m = draw(_M)
    w = [draw(_W) for _ in range(n)]
    return (n, m, w)


@st.composite
def _core_and_perm(draw):
    n, m, a, w = draw(_core())
    perm = draw(st.permutations(list(range(n))))
    return (n, m, a, w, perm)


def _check_symmetry(n, a, w, out):
    assert len(out) == n, "expected {} outputs, got {}".format(n, len(out))
    for v in out:
        assert 0 <= v < MOD, "output {} out of range [0, {})".format(v, MOD)
    groups = {}
    for i in range(n):
        groups.setdefault((a[i], w[i]), []).append(i)
    for key, idxs in groups.items():
        base = out[idxs[0]]
        for i in idxs[1:]:
            assert out[i] == base, (
                "identical pictures {} at positions {} and {} disagree: "
                "{} vs {}".format(key, idxs[0], i, base, out[i]))


# ---------------------------------------------------------------------------

@settings(max_examples=45, deadline=None)
@given(_core())
@example((1, 1, [1], [1]))
@example((50, 50, [1] * 50, [50] * 50))
@example((50, 50, [0] * 49 + [1], [50] * 50))
@example((2, 1, [0, 1], [50, 1]))
def test_format_range_symmetry(data):
    n, m, a, w = data
    out = _parse_ints(run_candidate(_format(n, m, a, w)))
    _check_symmetry(n, a, w, out)


@settings(max_examples=35, deadline=None)
@given(_core_dup())
def test_heavy_duplicate_symmetry(data):
    n, m, a, w = data
    out = _parse_ints(run_candidate(_format(n, m, a, w)))
    _check_symmetry(n, a, w, out)


@settings(max_examples=22, deadline=None)
@given(_core_and_perm())
def test_permutation_equivariance(data):
    n, m, a, w, perm = data
    out1 = _parse_ints(run_candidate(_format(n, m, a, w)))
    assert len(out1) == n, "expected {} outputs, got {}".format(n, len(out1))
    a2 = [a[perm[j]] for j in range(n)]
    w2 = [w[perm[j]] for j in range(n)]
    out2 = _parse_ints(run_candidate(_format(n, m, a2, w2)))
    assert len(out2) == n, "expected {} outputs, got {}".format(n, len(out2))
    for j in range(n):
        assert out2[j] == out1[perm[j]], (
            "permutation broken at pos {}: {} != {}".format(
                j, out2[j], out1[perm[j]]))


@settings(max_examples=45, deadline=None)
@given(_core_all_liked())
@example((1, 2, [1]))          # matches example 2 (E = 3)
@example((1, 50, [50]))
@example((50, 50, [50] * 50))
@example((50, 1, [1] * 50))
def test_all_liked_certificate(data):
    n, m, w = data
    a = [1] * n
    out = _parse_ints(run_candidate(_format(n, m, a, w)))
    assert len(out) == n, "expected {} outputs, got {}".format(n, len(out))
    S = sum(w)
    inv_S = pow(S, MOD - 2, MOD)
    factor = (S + m) % MOD * inv_S % MOD  # (S + m) / S  mod p
    for i in range(n):
        assert 0 <= out[i] < MOD, "output {} out of range".format(out[i])
        expected = w[i] % MOD * factor % MOD
        assert out[i] == expected, (
            "all-liked picture {} (w={}, S={}, m={}) expected {} got {}".format(
                i, w[i], S, m, expected, out[i]))
