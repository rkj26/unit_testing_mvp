import math
from hypothesis import given, strategies as st, settings
from harness import run_candidate  # run_candidate(stdin: str) -> stdout: str

# ---------------------------------------------------------------------------
# Problem 3798:
#   f(b, n) = sum of the digits of n written in base b.
#   Given n (1..1e11) and s (1..1e11), print the SMALLEST base b>=2 with
#   f(b,n)=s, or -1 if none exists.
#
# Key facts used for SOUND (definition-faithful) verification, none of which
# require reimplementing the efficient smallest-base search:
#   * f(b,n) <= n for every b>=2, with equality iff n<b (single digit).
#     -> s > n is ALWAYS unachievable      => answer -1.
#     -> s == n is achievable only by bases b>n, so the smallest such base is
#        exactly n+1 (every b<=n has digit-sum < n).
#   * For s < n the answer, if it exists, lies in [2, n]; and any valid answer
#     is at most n+1 overall.
#   * digit_sum below is an exact, trivially-correct implementation of f, used
#     ONLY to (a) validate a returned base against the input (certificate), and
#     (b) determine the true smallest base among a bounded PREFIX [2, cap] of
#     candidate bases (from 2 upward, so the first hit is the global minimum).
# ---------------------------------------------------------------------------

MAXV = 10 ** 11
CAP = 3000  # prefix depth for large-n minimality checks

# witness bases for constructed-achievable inputs (stdin -> a base b with f(b,n)=s)
WITNESS = {}


def digit_sum(b, n):
    """Exact f(b, n): sum of base-b digits of n (n>=0, b>=2)."""
    t = 0
    while n:
        t += n % b
        n //= b
    return t


def parse_out(stdout):
    toks = stdout.split()
    assert len(toks) == 1, "expected exactly one integer token, got: %r" % (stdout,)
    try:
        return int(toks[0])
    except ValueError:
        raise AssertionError("output is not an integer: %r" % (stdout,))


def parse_in(stdin):
    parts = stdin.split()
    return int(parts[0]), int(parts[1])


def basic_range(n, out):
    # A correct answer is either -1 or a base in [2, n+1].
    assert out == -1 or out >= 2, "base must be >= 2 (or -1), got %d" % out
    if out != -1:
        assert out <= n + 1, "answer base cannot exceed n+1=%d, got %d" % (n + 1, out)


def check(n, s, out, cap):
    """Sound verification of a returned answer for (n, s)."""
    basic_range(n, out)

    if s > n:
        # f(b,n) <= n for all b, so s>n is impossible.
        assert out == -1, "s>n unachievable; expected -1, got %d" % out
        return

    if s == n:
        # Only bases b>n yield digit-sum n; the smallest is n+1.
        assert out == n + 1, "s==n must give smallest base n+1=%d, got %d" % (n + 1, out)
        return

    # s < n : achievable only by bases in [2, n].
    limit = min(cap, n)
    found = None
    b = 2
    while b <= limit:
        if digit_sum(b, n) == s:
            found = b
            break
        b += 1

    if found is not None:
        # Scanned from 2 upward, so `found` is the GLOBAL smallest base.
        assert out == found, "smallest base with digit-sum %d is %d, got %d" % (s, found, out)
    else:
        complete = limit >= n  # we exhausted every relevant base [2, n]
        if complete:
            assert out == -1, "no base gives digit-sum %d; expected -1, got %d" % (s, out)
        else:
            # Indeterminate beyond prefix: a correct non(-1) answer must lie
            # beyond the prefix and must be a genuine base (certificate).
            if out != -1:
                assert out > limit, "a smaller base within [2,%d] would satisfy; got %d" % (limit, out)
                assert digit_sum(out, n) == s, "returned base %d has digit-sum %d != %d" % (
                    out, digit_sum(out, n), s)
            # out == -1 is accepted here (cannot be cheaply refuted past prefix).


# ---------------------------------------------------------------------------
# Test 1: small n fully verified (prefix covers all bases -> exact answer,
# including exact -1). Sweeps threshold s values: s==n, s>n, s==n-1, s==1.
# ---------------------------------------------------------------------------
@st.composite
def small_input(draw):
    n = draw(st.integers(min_value=1, max_value=3000))
    pick = draw(st.integers(0, 6))
    if pick == 0:
        s = n              # s == n  -> answer n+1
    elif pick == 1:
        s = n + 1          # s > n   -> -1
    elif pick == 2:
        s = max(1, n - 1)  # just below n
    elif pick == 3:
        s = 1              # minimum s
    elif pick == 4:
        s = draw(st.integers(1, max(1, n)))
    elif pick == 5:
        s = draw(st.integers(1, 3002))
    else:
        s = draw(st.sampled_from([1, 2, 3, n, n + 1, max(1, n // 2)]))
    s = max(1, min(int(s), MAXV))
    return "%d\n%d\n" % (n, s)


@given(small_input())
@settings(max_examples=32, deadline=None)
def test_small_exhaustive(stdin):
    n, s = parse_in(stdin)
    out = parse_out(run_candidate(stdin))
    check(n, s, out, 3100)  # cap >= n for all n here -> fully exact


# ---------------------------------------------------------------------------
# Test 2: full magnitude range incl. extremes (n=1, n=1e11, powers) with
# threshold s values. Certificate + prefix minimality + s>=n exact rules.
# ---------------------------------------------------------------------------
@st.composite
def large_input(draw):
    n = draw(st.one_of(
        st.just(1),
        st.just(2),
        st.just(MAXV),
        st.just(MAXV - 1),
        st.integers(1, 3000),
        st.integers(1, MAXV),
        st.sampled_from([10, 100, 1000, 2 ** 40, 3 ** 20, 10 ** 10, 87654,
                         999999999937, 2 ** 30, 5 ** 15, 6 ** 14]),
    ))
    n = max(1, min(int(n), MAXV))
    pick = draw(st.integers(0, 6))
    if pick == 0:
        s = n
    elif pick == 1:
        s = n + 1
    elif pick == 2:
        s = max(1, n - 1)
    elif pick == 3:
        s = 1
    elif pick == 4:
        s = draw(st.integers(1, n))
    elif pick == 5:
        s = draw(st.integers(1, MAXV))
    else:
        s = draw(st.sampled_from([1, 2, 3, n, n + 1, min(MAXV, 2 * n), max(1, n // 2)]))
    s = max(1, min(int(s), MAXV))
    return "%d\n%d\n" % (n, s)


@given(large_input())
@settings(max_examples=32, deadline=None)
def test_general_certificate(stdin):
    n, s = parse_in(stdin)
    out = parse_out(run_candidate(stdin))
    check(n, s, out, CAP)


# ---------------------------------------------------------------------------
# Test 3: constructed-achievable. Pick a base B in [2, n], set s = f(B, n);
# an answer is GUARANTEED to exist (B is a witness) and must be <= B. Targets
# base=2 (popcount), bases near sqrt(n) (the multi-digit/2-digit boundary),
# the q=1 two-digit region, and B=n (s=1, perfect-power case).
# ---------------------------------------------------------------------------
@st.composite
def constructed_input(draw):
    n = draw(st.one_of(
        st.integers(2, 60),
        st.integers(2, 3000),
        st.integers(2, MAXV),
        st.sampled_from([2, 3, MAXV, MAXV - 1, 2 ** 40, 3 ** 20, 10 ** 10,
                         87654, 999999999989, 2 ** 30]),
    ))
    n = max(2, min(int(n), MAXV))
    r = math.isqrt(n)
    kind = draw(st.integers(0, 6))
    if kind == 0:
        B = 2                                   # binary: popcount
    elif kind == 1:
        B = 3
    elif kind == 2:
        B = draw(st.sampled_from([max(2, r - 1), r, r + 1, min(n, r + 2)]))  # near sqrt(n)
    elif kind == 3:
        B = draw(st.integers(2, n))
    elif kind == 4:
        B = n                                   # s = 1 (n = "10" in base n)
    elif kind == 5:
        lo = n // 2 + 1
        B = draw(st.integers(min(lo, n), n))    # q=1 two-digit region
    else:
        B = draw(st.integers(max(2, r), min(n, r + 50)))  # band just above sqrt(n)
    B = max(2, min(int(B), n))
    s = digit_sum(B, n)
    s = max(1, min(s, MAXV))
    stdin = "%d\n%d\n" % (n, s)
    WITNESS[stdin] = B
    return stdin


@given(constructed_input())
@settings(max_examples=28, deadline=None)
def test_constructed_achievable(stdin):
    n, s = parse_in(stdin)
    out = parse_out(run_candidate(stdin))
    basic_range(n, out)
    # An answer provably exists (a witness base was used).
    assert out != -1, "answer exists (constructed) but got -1 for n=%d s=%d" % (n, s)
    # Returned base must actually achieve s.
    assert digit_sum(out, n) == s, "returned base %d has digit-sum %d != %d" % (
        out, digit_sum(out, n), s)
    B = WITNESS.get(stdin)
    if B is not None:
        assert out <= B, "answer must be <= witness base %d, got %d" % (B, out)
    check(n, s, out, CAP)


# ---------------------------------------------------------------------------
# Test 4: deterministic sweep of exact thresholds against extreme magnitudes:
# s == n (=> n+1), s > n (=> -1), s == n-1, s == 1, s = popcount (=> base 2).
# ---------------------------------------------------------------------------
@st.composite
def boundary_input(draw):
    n = draw(st.sampled_from([1, 2, 3, 4, 5, 9, 10, 16, 100, 1000,
                              2 ** 40, 3 ** 20, 10 ** 10, MAXV, MAXV - 1,
                              87654, 999999999937]))
    pick = draw(st.integers(0, 5))
    if pick == 0:
        s = n                       # -> n+1
    elif pick == 1:
        s = min(MAXV, n + 1)        # -> -1 (when n+1<=MAXV and >n)
    elif pick == 2:
        s = max(1, n - 1)
    elif pick == 3:
        s = 1
    elif pick == 4:
        s = min(MAXV, 2 * n)
    else:
        s = digit_sum(2, n)         # popcount -> achievable by base 2 -> answer 2
    s = max(1, min(int(s), MAXV))
    return "%d\n%d\n" % (n, s)


@given(boundary_input())
@settings(max_examples=28, deadline=None)
def test_boundary_thresholds(stdin):
    n, s = parse_in(stdin)
    out = parse_out(run_candidate(stdin))
    check(n, s, out, CAP)