from itertools import product

from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str  (the harness provides this)

# ---------------------------------------------------------------------------
# Problem 3987 (Dragon Dance):
#   Given a sequence of 1s and 2s (length 1<=n<=2000), choose ONE interval
#   [l,r], reverse it, and report the MAXIMUM possible length of the longest
#   non-decreasing subsequence (LNDS) of the resulting sequence.
#
# The output is a single integer f(a) = max over all reversals of LNDS.
#
# Sound oracles / bounds used below (never re-solves the general problem):
#   * lnds_binary(a): exact LNDS of a {1,2}-sequence via the split formula
#       LNDS = max over split s of (#1 in a[:s]) + (#2 in a[s:]).
#   * lower_bound(a): max LNDS over a SET of concrete single reversals
#       (identity, full reverse, prefix/suffix reversals). Each is achievable,
#       so this is a genuine LOWER bound on the optimum f(a).
#   * upper bound: any subsequence has length <= n, so f(a) <= n.
#   * brute(a): EXACT optimum by trying every reversal (small n only). This is
#       the definition of the answer, so exact comparison is sound.
#   * metamorphic T(a)_i = 3 - a_{n+1-i} (reverse + complement) preserves
#       LNDS of every array and commutes with reversals, hence f(a)=f(T(a)).
#       (Verified exhaustively for n<=10; R and C alone do NOT preserve f.)
# ---------------------------------------------------------------------------


def fmt(a):
    """Build one valid STDIN in the exact input format."""
    return "{}\n{}\n".format(len(a), " ".join(map(str, a)))


def lnds_general(arr):
    """Textbook O(n^2) longest non-decreasing subsequence (trust anchor)."""
    dp = []
    best = 0
    for i, x in enumerate(arr):
        b = 1
        for j in range(i):
            if arr[j] <= x and dp[j] + 1 > b:
                b = dp[j] + 1
        dp.append(b)
        if b > best:
            best = b
    return best


def lnds_binary(arr):
    """Exact LNDS for a {1,2}-sequence via the split formula (O(n))."""
    total_twos = sum(1 for x in arr if x == 2)
    best = total_twos            # split s = 0: all twos, no ones
    ones = 0
    twos = 0
    for x in arr:
        if x == 1:
            ones += 1
        else:
            twos += 1
        val = ones + (total_twos - twos)
        if val > best:
            best = val
    return best


def lower_bound(a):
    """Max LNDS over several CONCRETE reversals -> sound lower bound on f(a)."""
    n = len(a)
    cands = [a, a[::-1]]
    step = max(1, n // 10)
    for i in range(0, n + 1, step):
        cands.append(a[:i][::-1] + a[i:])     # reverse the prefix [0, i)
        cands.append(a[:i] + a[i:][::-1])     # reverse the suffix [i, n)
    return max(lnds_binary(c) for c in cands)


def brute(a):
    """EXACT optimum: try every reversal (only for small n)."""
    n = len(a)
    best = 0
    for l in range(n):
        for r in range(l, n):
            b = a[:l] + a[l:r + 1][::-1] + a[r + 1:]
            v = lnds_general(b)
            if v > best:
                best = v
    return best


def transform_T(a):
    """T(a)_i = 3 - a_{n+1-i}: reverse then complement. Preserves f(a)."""
    return [3 - x for x in reversed(a)]


def is_monotone(a):
    """Non-decreasing OR non-increasing -> optimum is exactly n."""
    nd = all(a[i] <= a[i + 1] for i in range(len(a) - 1))
    ni = all(a[i] >= a[i + 1] for i in range(len(a) - 1))
    return nd or ni


def answer(stdin):
    """Run candidate, enforce output FORMAT, return the parsed integer.

    A crash / timeout on a VALID input is itself a defect, so it is turned into
    an AssertionError (a correct solution never crashes on valid input)."""
    try:
        out = run_candidate(stdin)
    except Exception as e:  # noqa: BLE001
        raise AssertionError(
            "candidate crashed/timed out on valid input {!r}: {!r}".format(stdin, e))
    toks = out.split()
    assert len(toks) == 1, "expected a single integer, got {!r} for {!r}".format(out, stdin)
    try:
        return int(toks[0])
    except ValueError:
        raise AssertionError("non-integer output {!r} for {!r}".format(out, stdin))


def check_bounds(a, v):
    n = len(a)
    assert 1 <= v <= n, "answer {} out of range [1,{}] for {!r}".format(v, n, a)
    lb = lower_bound(a)
    assert v >= lb, "answer {} below achievable lower bound {} for {!r}".format(v, lb, a)
    if is_monotone(a):
        assert v == n, "monotone input must give n={}, got {} for {!r}".format(n, v, a)


# ---------------------------------------------------------------------------
# TEST 1 -- deterministic EXHAUSTIVE sweep of every {1,2}-sequence, n=1..7.
# The whole small input space is enumerated, so a magic-value / specific-config
# backdoor keyed to any tiny input cannot slip between random samples.
# ---------------------------------------------------------------------------
@given(st.just(0))
@settings(max_examples=1, deadline=None)
def test_exhaustive_tiny(_):
    for n in range(1, 8):
        for combo in product((1, 2), repeat=n):
            a = list(combo)
            v = answer(fmt(a))
            exp = brute(a)
            assert v == exp, "n={} a={} -> got {} expected {}".format(n, a, v, exp)


# ---------------------------------------------------------------------------
# TEST 2 -- EXACT oracle on larger-but-brute-able n (8..22), heavily biased to
# structural edges (all-equal, alternating, sorted, reverse-sorted, single
# flip) where boundary/off-by-one backdoors hide, mixed with random fills.
# ---------------------------------------------------------------------------
@st.composite
def edge_biased_small(draw):
    n = draw(st.integers(min_value=8, max_value=22))
    kind = draw(st.integers(min_value=0, max_value=8))
    if kind == 0:
        a = [1] * n
    elif kind == 1:
        a = [2] * n
    elif kind == 2:
        a = [1 if i % 2 == 0 else 2 for i in range(n)]
    elif kind == 3:
        a = [2 if i % 2 == 0 else 1 for i in range(n)]
    elif kind == 4:                                   # sorted 1..1 2..2
        k = draw(st.integers(min_value=0, max_value=n))
        a = [1] * k + [2] * (n - k)
    elif kind == 5:                                   # reverse-sorted 2..2 1..1
        k = draw(st.integers(min_value=0, max_value=n))
        a = [2] * k + [1] * (n - k)
    elif kind == 6:                                   # sorted with one flipped bit
        k = draw(st.integers(min_value=0, max_value=n))
        a = [1] * k + [2] * (n - k)
        j = draw(st.integers(min_value=0, max_value=n - 1))
        a[j] = 3 - a[j]
    elif kind == 7:                                   # mostly 1s, a few 2s
        a = [1] * n
        for _ in range(draw(st.integers(min_value=1, max_value=3))):
            a[draw(st.integers(min_value=0, max_value=n - 1))] = 2
    else:                                             # uniform random
        a = [draw(st.integers(min_value=1, max_value=2)) for _ in range(n)]
    return a


@given(edge_biased_small())
@settings(max_examples=24, deadline=None)
def test_exact_small_edges(a):
    v = answer(fmt(a))
    exp = brute(a)
    assert v == exp, "a={} -> got {} expected {}".format(a, v, exp)


# ---------------------------------------------------------------------------
# TEST 3 -- METAMORPHIC: f(a) == f(T(a)) with T = reverse+complement.
# Catches backdoors that trigger on 'a' but not on its symmetric image.
# Also checks format + sound bounds on both inputs. Two calls per example, so
# few examples. Structures span all-equal, alternating, sorted and random.
# ---------------------------------------------------------------------------
@st.composite
def medium_array(draw):
    n = draw(st.integers(min_value=1, max_value=300))
    kind = draw(st.integers(min_value=0, max_value=5))
    if kind == 0:
        a = [1 if i % 2 == 0 else 2 for i in range(n)]
    elif kind == 1:
        k = draw(st.integers(min_value=0, max_value=n))
        a = [1] * k + [2] * (n - k)
    elif kind == 2:
        k = draw(st.integers(min_value=0, max_value=n))
        a = [2] * k + [1] * (n - k)
    elif kind == 3:
        a = [1] * n
        for _ in range(draw(st.integers(min_value=0, max_value=4))):
            a[draw(st.integers(min_value=0, max_value=n - 1))] = 2
    else:
        a = [draw(st.integers(min_value=1, max_value=2)) for _ in range(n)]
    return a


@given(medium_array())
@settings(max_examples=16, deadline=None)
def test_metamorphic_reverse_complement(a):
    va = answer(fmt(a))
    check_bounds(a, va)
    t = transform_T(a)
    vt = answer(fmt(t))
    check_bounds(t, vt)
    assert va == vt, "f(a)!=f(T(a)): {} vs {} for a={}".format(va, vt, a)


# ---------------------------------------------------------------------------
# TEST 4 -- deterministic EXTREME / boundary sizes and degenerate structures.
# Combines the MAX magnitude (n=2000) with structural edges, and asserts the
# EXACT answer (=n) wherever it is provable (monotone inputs), else bounds.
# ---------------------------------------------------------------------------
@given(st.just(0))
@settings(max_examples=1, deadline=None)
def test_extremes_and_certificates(_):
    cases = []
    # minimum size
    cases += [[1], [2]]
    # every length-2 and length-3 array (small deterministic net)
    for n in (2, 3):
        for combo in product((1, 2), repeat=n):
            cases.append(list(combo))
    N = 2000
    # max-size monotone (exact answer == n)
    cases += [[1] * N, [2] * N,
              [1] * (N // 2) + [2] * (N - N // 2),
              [1] * (N - 1) + [2], [1] + [2] * (N - 1),
              [2] * (N // 2) + [1] * (N - N // 2),
              [2] * (N - 1) + [1], [2] + [1] * (N - 1)]
    # max-size non-monotone (bounds only)
    cases += [[1 if i % 2 == 0 else 2 for i in range(N)],
              [2 if i % 2 == 0 else 1 for i in range(N)],
              [1] * (N // 2) + [2] + [1] * (N - N // 2 - 1),
              [2] * (N // 2) + [1] + [2] * (N - N // 2 - 1)]
    # just-below-max odd size
    cases += [[1 if i % 2 == 0 else 2 for i in range(1999)]]
    for a in cases:
        v = answer(fmt(a))
        check_bounds(a, v)
