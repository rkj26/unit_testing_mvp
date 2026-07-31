from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str  (the harness provides this)

# ---------------------------------------------------------------------------
# Problem model (used only for SOUND oracles / bounds -- never assumes the
# candidate's internal algorithm).
#
# Base 7. Hours part shows values 0..n-1 using the smallest number of base-7
# places able to display n-1 (at least 1 place). Minutes part likewise for
# 0..m-1. Count moments (h,t) where ALL displayed digits (across both parts)
# are pairwise distinct.
# ---------------------------------------------------------------------------

MAXV = 10 ** 9


def _width(count):
    """Smallest number of base-7 places needed to display 0..count-1 (>=1)."""
    w = 1
    p = 7
    while p < count:      # need 7^w >= count
        p *= 7
        w += 1
    return w


def _digits(x, w):
    """Base-7 digits of x, exactly w of them (little-endian; leading zeros)."""
    ds = []
    for _ in range(w):
        ds.append(x % 7)
        x //= 7
    return ds


def _perm(k):
    """Number of ways to place k distinct digits chosen from {0..6}. 0 if k>7."""
    if k > 7:
        return 0
    r = 1
    for i in range(k):
        r *= (7 - i)
    return r


def _brute(n, m):
    """Naive independent reference (only for small n, m)."""
    a = _width(n)
    b = _width(m)
    if a + b > 7:
        return 0
    vh = []
    for h in range(n):
        d = _digits(h, a)
        s = set(d)
        if len(s) == a:            # hour has all-distinct digits
            vh.append(s)
    vt = []
    for t in range(m):
        d = _digits(t, b)
        s = set(d)
        if len(s) == b:            # minute has all-distinct digits
            vt.append(s)
    total = 0
    for sh in vh:
        for stt in vt:
            if sh.isdisjoint(stt):
                total += 1
    return total


def _parse_out(raw):
    s = raw.strip()
    assert s != "", "empty output"
    toks = s.split()
    assert len(toks) == 1, "output must be a single integer token: %r" % raw
    return int(s)   # raises ValueError -> failure if not an integer


_INTERESTING = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 14, 42, 47, 48, 49, 50]
_BIG = [1, 2, 6, 7, 8, 48, 49, 50, 342, 343, 344, 2400, 2401, 2402,
        117648, 117649, 823542, 823543, 40353607, 40353608,
        7 ** 10, MAXV, MAXV - 1]


# ---------------------------------------------------------------------------
# Test 1: exact match vs a naive independent brute force on small inputs.
# Deliberately samples the base-7 width transitions (7/8, 48/49/50).
# ---------------------------------------------------------------------------
@st.composite
def small_input(draw):
    n = draw(st.one_of(st.sampled_from(_INTERESTING), st.integers(1, 50)))
    m = draw(st.one_of(st.sampled_from(_INTERESTING), st.integers(1, 50)))
    return "%d %d\n" % (n, m)


@given(small_input())
@settings(max_examples=50, deadline=None)
def test_matches_brute_force(stdin):
    p = stdin.split()
    n, m = int(p[0]), int(p[1])
    ans = _parse_out(run_candidate(stdin))
    exp = _brute(n, m)
    assert ans == exp, "n=%d m=%d expected %d got %d" % (n, m, exp, ans)


# ---------------------------------------------------------------------------
# Test 2: saturated case n=7^a, m=7^b -> every a-digit / b-digit display is
# realizable, so the count is exactly P(7, a+b) (=0 when a+b>7). Hits exact
# power-of-7 thresholds and large magnitudes; deterministic sweep of a,b.
# ---------------------------------------------------------------------------
@st.composite
def power_input(draw):
    a = draw(st.integers(1, 10))   # 7^10 = 282475249 <= 1e9
    b = draw(st.integers(1, 10))
    return "%d %d\n" % (7 ** a, 7 ** b)


@given(power_input())
@settings(max_examples=45, deadline=None)
def test_saturated_powers_exact(stdin):
    p = stdin.split()
    n, m = int(p[0]), int(p[1])
    a, b = _width(n), _width(m)
    ans = _parse_out(run_candidate(stdin))
    exp = _perm(a + b)             # 0 automatically when a+b > 7
    assert ans == exp, "n=7^%d m=7^%d expected %d got %d" % (a, b, exp, ans)


# ---------------------------------------------------------------------------
# Test 3: range / bound invariants valid for ALL magnitudes up to 1e9.
#   * non-negative
#   * <= n*m (can't exceed total number of moments)
#   * <= P(7, a+b) (injective map from valid moment to a+b distinct digits)
#   * a+b > 7 forces exactly 0 (only 7 distinct digits exist)
# ---------------------------------------------------------------------------
@st.composite
def any_input(draw):
    n = draw(st.one_of(st.sampled_from(_BIG), st.integers(1, MAXV)))
    m = draw(st.one_of(st.sampled_from(_BIG), st.integers(1, MAXV)))
    return "%d %d\n" % (n, m)


@given(any_input())
@settings(max_examples=50, deadline=None)
def test_bounds_and_zero(stdin):
    p = stdin.split()
    n, m = int(p[0]), int(p[1])
    a, b = _width(n), _width(m)
    ans = _parse_out(run_candidate(stdin))
    assert ans >= 0, "negative count %d" % ans
    ub = min(n * m, _perm(a + b))
    assert ans <= ub, "n=%d m=%d ans=%d exceeds ub=%d (a=%d b=%d)" % (n, m, ans, ub, a, b)
    if a + b > 7:
        assert ans == 0, "a+b=%d>7 must give 0, got %d" % (a + b, ans)


# ---------------------------------------------------------------------------
# Test 4 (metamorphic): swapping hours<->minutes is a bijection on valid
# moments, so count(n,m) == count(m,n). Works at any magnitude.
# ---------------------------------------------------------------------------
@given(any_input())
@settings(max_examples=18, deadline=None)
def test_symmetry(stdin):
    p = stdin.split()
    n, m = int(p[0]), int(p[1])
    a1 = _parse_out(run_candidate("%d %d\n" % (n, m)))
    a2 = _parse_out(run_candidate("%d %d\n" % (m, n)))
    assert a1 == a2, "count(%d,%d)=%d != count(%d,%d)=%d" % (n, m, a1, m, n, a2)


# ---------------------------------------------------------------------------
# Test 5 (metamorphic): within a single base-7 width band the display of each
# hour is fixed, so enlarging n (same width) can only add valid moments:
# count(n1,m) <= count(n2,m) when width(n1)==width(n2) and n1<=n2.
# ---------------------------------------------------------------------------
@st.composite
def band_input(draw):
    w = draw(st.integers(1, 10))
    lo = 1 if w == 1 else 7 ** (w - 1) + 1
    hi = 7 ** w
    n1 = draw(st.integers(lo, hi))
    n2 = draw(st.integers(lo, hi))
    if n1 > n2:
        n1, n2 = n2, n1
    m = draw(st.one_of(st.sampled_from(_BIG), st.integers(1, MAXV)))
    return (n1, n2, m)


@given(band_input())
@settings(max_examples=18, deadline=None)
def test_monotonic_within_band(data):
    n1, n2, m = data
    assert _width(n1) == _width(n2)     # generator invariant
    a1 = _parse_out(run_candidate("%d %d\n" % (n1, m)))
    a2 = _parse_out(run_candidate("%d %d\n" % (n2, m)))
    assert a1 <= a2, "count(%d,%d)=%d > count(%d,%d)=%d (same band)" % (n1, m, a1, n2, m, a2)