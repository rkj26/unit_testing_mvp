import bisect
from collections import Counter

from hypothesis import given, strategies as st, settings

from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str


# --------------------------------------------------------------------------
# Problem 3790:
#   Base array a_1..a_n (1<=a_i<=300).  Full array = base repeated T times
#   (length n*T), i.e. a_i = a_{i-n} for i>n.  1<=n<=100, 1<=T<=1e7.
#   Output = length of the longest NON-DECREASING subsequence of the full
#   array.
#
# Facts used below (all provable from the spec, no need to solve the problem):
#   * m = max multiplicity of any value in the base.  Taking every copy of
#     that value across all T periods gives a constant (hence non-decreasing)
#     subsequence of length m*T  =>  ans >= m*T.
#   * The base is a contiguous block of the full array => ans >= LNDS(base).
#   * BLOCK BOUND: any non-decreasing subsequence, restricted to one of the T
#     periods, is a non-decreasing subsequence of the base, so contributes at
#     most LNDS(base).  Summing over the T periods => ans <= T*LNDS(base).
#     (This is also subadditivity: ans(a+b) <= ans(a)+ans(b).)
#   * Order-preserving relabelling of the values leaves LNDS unchanged.
#   * reverse+order-reversing-negate leaves LNDS of the full array unchanged
#     (LNDS(negate(reverse(X))) = LNDS(X)); and full(reverse-negate(base)) =
#     negate(reverse(full(base))) by periodicity.
# --------------------------------------------------------------------------


def lnds_length(arr):
    """Length of the longest NON-DECREASING subsequence (patience sorting)."""
    tails = []
    for x in arr:
        i = bisect.bisect_right(tails, x)
        if i == len(tails):
            tails.append(x)
        else:
            tails[i] = x
    return len(tails)


def max_multiplicity(base):
    return max(Counter(base).values())


def parse_out(stdout):
    toks = stdout.split()
    assert len(toks) == 1, "expected exactly one integer token, got: %r" % (stdout,)
    return int(toks[0])


def fmt(n, T, base):
    assert len(base) == n
    assert 1 <= n <= 100 and 1 <= T <= 10 ** 7
    assert all(1 <= v <= 300 for v in base)
    return "%d %d\n%s\n" % (n, T, " ".join(map(str, base)))


def _n_strategy():
    return st.one_of(
        st.just(1),
        st.just(2),
        st.just(3),
        st.just(99),
        st.just(100),
        st.integers(1, 8),
        st.integers(1, 100),
    )


@st.composite
def _base_array(draw, n):
    mode = draw(st.sampled_from(
        ["equal", "asc", "desc", "two", "heavy", "extreme", "sorted", "random"]))
    if mode == "equal":                       # all-equal -> m == LNDS == n (exact regime)
        v = draw(st.integers(1, 300))
        return [v] * n
    if mode in ("asc", "desc"):               # strictly monotone distinct
        if n == 1:
            return [draw(st.integers(1, 300))]
        max_g = max(1, 299 // (n - 1))
        g = draw(st.integers(1, max_g))
        start = draw(st.integers(1, 300 - g * (n - 1)))
        arr = [start + i * g for i in range(n)]
        return arr[::-1] if mode == "desc" else arr
    if mode == "two":                         # two-valued -> heavy duplicates
        lo = draw(st.integers(1, 299))
        hi = draw(st.integers(lo + 1, 300))
        return [draw(st.sampled_from([lo, hi])) for _ in range(n)]
    if mode == "heavy":                       # few distinct values, big multiplicity
        k = draw(st.integers(1, min(3, n)))
        vals = draw(st.lists(st.integers(1, 300),
                             min_size=k, max_size=k, unique=True))
        return [draw(st.sampled_from(vals)) for _ in range(n)]
    if mode == "extreme":                     # values pinned at the 1 / 300 bounds
        return [draw(st.sampled_from([1, 300])) for _ in range(n)]
    if mode == "sorted":                      # non-decreasing with duplicates
        arr = draw(st.lists(st.integers(1, 300), min_size=n, max_size=n))
        return sorted(arr)
    return draw(st.lists(st.integers(1, 300), min_size=n, max_size=n))  # random


def _T_general(draw, n):
    # bias hard toward T=1, the T~n algorithmic branch boundary, and T at the
    # extreme 1e7 upper bound, mixed with uniform draws.
    return draw(st.one_of(
        st.just(1),
        st.just(2),
        st.sampled_from([max(1, n - 1), n, n + 1, 2 * n, 3 * n]),
        st.just(10 ** 7),
        st.just(10 ** 7 - 1),
        st.integers(1, 500),
        st.integers(1, 10 ** 7),
    ))


@st.composite
def make_general(draw):
    n = draw(_n_strategy())
    base = draw(_base_array(n))
    T = draw(_T_general(draw, n))
    return fmt(n, T, base)


@st.composite
def make_small(draw):
    # keep n*T small so we can materialise the full array and check EXACTLY.
    n = draw(st.integers(1, 40))
    cap = max(1, 2500 // n)
    base = draw(_base_array(n))
    T = draw(st.one_of(
        st.just(1),
        st.sampled_from([max(1, n - 1), n, n + 1]),   # cross the T~n boundary
        st.integers(1, cap),
    ))
    T = min(max(1, T), cap)
    return fmt(n, T, base)


# --------------------------------------------------------------------------
# 1) Format + universal, provable bounds (covers the full T range incl. 1e7).
# --------------------------------------------------------------------------
@given(make_general())
@settings(max_examples=45, deadline=None)
def test_format_and_bounds(stdin):
    n, T = map(int, stdin.split("\n")[0].split())
    base = list(map(int, stdin.split("\n")[1].split()))
    ans = parse_out(run_candidate(stdin))

    m = max_multiplicity(base)
    L = lnds_length(base)
    lo = max(m * T, L)
    hi = T * L

    assert ans >= 1, (n, T, base, ans)
    assert ans >= lo, ("lower bound", n, T, base, ans, lo)
    assert ans <= hi, ("upper bound", n, T, base, ans, hi)
    # exact squeezes (lo == hi in these regimes):
    if T == 1:
        assert ans == L, ("T=1 exact", base, ans, L)
    if m == L:
        assert ans == m * T, ("constant-optimal exact", base, T, ans, m * T)


# --------------------------------------------------------------------------
# 2) Brute-force oracle on small n*T: exact answer via materialised array.
# --------------------------------------------------------------------------
@given(make_small())
@settings(max_examples=40, deadline=None)
def test_brute_exact_small(stdin):
    n, T = map(int, stdin.split("\n")[0].split())
    base = list(map(int, stdin.split("\n")[1].split()))
    ans = parse_out(run_candidate(stdin))
    expected = lnds_length(base * T)
    assert ans == expected, (n, T, base, ans, expected)


# --------------------------------------------------------------------------
# 3) Metamorphic: order-reversing negate + reverse leaves the answer fixed.
# --------------------------------------------------------------------------
@given(make_general())
@settings(max_examples=18, deadline=None)
def test_metamorphic_reverse_negate(stdin):
    n, T = map(int, stdin.split("\n")[0].split())
    base = list(map(int, stdin.split("\n")[1].split()))
    ans1 = parse_out(run_candidate(stdin))
    base2 = [301 - v for v in reversed(base)]
    ans2 = parse_out(run_candidate(fmt(n, T, base2)))
    assert ans1 == ans2, ("reverse-negate", base, base2, T, ans1, ans2)


# --------------------------------------------------------------------------
# 4) Metamorphic: order-preserving relabelling of values leaves answer fixed.
# --------------------------------------------------------------------------
@given(make_general())
@settings(max_examples=18, deadline=None)
def test_metamorphic_relabel(stdin):
    n, T = map(int, stdin.split("\n")[0].split())
    base = list(map(int, stdin.split("\n")[1].split()))
    ans1 = parse_out(run_candidate(stdin))

    distinct = sorted(set(base))
    k = len(distinct)
    if k == 1:
        targets = [1]
    else:
        step = 299 // (k - 1)
        targets = [1 + i * step for i in range(k)]   # strictly increasing, <=300
    mapping = dict(zip(distinct, targets))
    base2 = [mapping[v] for v in base]

    ans2 = parse_out(run_candidate(fmt(n, T, base2)))
    assert ans1 == ans2, ("relabel", base, base2, T, ans1, ans2)


# --------------------------------------------------------------------------
# 5) Metamorphic: monotonicity in T + subadditive (block) upper bound.
#      ans(T_small) <= ans(T_large) <= ans(T_small) + delta*LNDS(base)
# --------------------------------------------------------------------------
@given(make_general())
@settings(max_examples=16, deadline=None)
def test_metamorphic_T_monotone(stdin):
    n, T = map(int, stdin.split("\n")[0].split())
    base = list(map(int, stdin.split("\n")[1].split()))
    L = lnds_length(base)
    MAXT = 10 ** 7

    if MAXT - T > 0:
        delta = min(max(1, n), MAXT - T)
        T_small, T_large = T, T + delta
    else:                                   # T is already at the maximum
        delta = min(max(1, n), T - 1)
        T_small, T_large = T - delta, T

    ans_small = parse_out(run_candidate(fmt(n, T_small, base)))
    ans_large = parse_out(run_candidate(fmt(n, T_large, base)))

    assert ans_large >= ans_small, ("monotone", base, T_small, T_large, ans_small, ans_large)
    assert ans_large <= ans_small + delta * L, (
        "subadditive", base, T_small, T_large, ans_small, ans_large, delta, L)