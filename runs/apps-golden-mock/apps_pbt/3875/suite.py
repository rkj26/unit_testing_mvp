import itertools
from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str  (the harness provides this)

MOD = 1000000007
MAXV = 10 ** 9

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def fmt(A):
    """Build ONE valid STDIN string in this problem's exact input format."""
    return "%d\n%s\n" % (len(A), " ".join(str(a) for a in A))


def parse_input(stdin):
    toks = stdin.split()
    n = int(toks[0])
    A = [int(t) for t in toks[1:1 + n]]
    return n, A


def parse_R(out):
    """Format/shape/range invariant: output is exactly one integer in [0, MOD)."""
    toks = out.split()
    assert len(toks) == 1, "expected a single integer, got %r" % (out,)
    R = int(toks[0])
    assert 0 <= R < MOD, "output out of range [0,MOD): %d" % R
    return R


def lis_length(seq):
    """Length of the longest STRICTLY increasing subsequence (O(n^2), n<=6)."""
    n = len(seq)
    if n == 0:
        return 0
    dp = [1] * n
    best = 1
    for i in range(n):
        for j in range(i):
            if seq[j] < seq[i] and dp[j] + 1 > dp[i]:
                dp[i] = dp[j] + 1
        if dp[i] > best:
            best = dp[i]
    return best


def exact_R_bruteforce(A):
    """Exact answer by DEFINITION: average LIS over the whole (small) sample space."""
    S = 0
    for x in itertools.product(*[range(1, a + 1) for a in A]):
        S += lis_length(x)
    M = 1
    for a in A:
        M *= a
    return (S % MOD) * pow(M % MOD, MOD - 2, MOD) % MOD


def exact_R_pair(a, b):
    """Closed form for N=2: E = 1 + P(X1<X2), P = (sum_{x=1..min(a,b-1)} (b-x)) / (a*b)."""
    m = min(a, b - 1)
    if m < 0:
        m = 0
    s = m * b - m * (m + 1) // 2          # count of ordered pairs with x < y
    return (1 + (s % MOD) * pow((a * b) % MOD, MOD - 2, MOD)) % MOD


# ---------------------------------------------------------------------------
# generators -- deliberately manufacture threshold / degenerate / extreme regions
# ---------------------------------------------------------------------------

# single A_i biased to the stated MIN (1) and MAX (1e9) plus tiny/mid values.
a_value = st.one_of(
    st.just(1),
    st.just(2),
    st.just(3),
    st.just(MAXV),
    st.just(MAXV - 1),
    st.just(MAXV // 2),
    st.integers(min_value=1, max_value=MAXV),
)


@st.composite
def make_input_general(draw):
    n = draw(st.integers(min_value=1, max_value=6))
    A = [draw(a_value) for _ in range(n)]
    return fmt(A)


@st.composite
def make_input_trivial(draw):
    # LIS is provably always 1 here -> answer is exactly 1.
    kind = draw(st.integers(0, 1))
    if kind == 0:                                   # N == 1, any A_1 (incl. extremes)
        a = draw(st.sampled_from([1, 2, 3, MAXV, MAXV - 1, MAXV // 2]) |
                 st.integers(1, MAXV))
        return fmt([a])
    n = draw(st.sampled_from([1, 2, 3, 4, 5, 6]))   # all-ones, deterministic size sweep
    return fmt([1] * n)


@st.composite
def make_input_short(draw):
    # length <= 5 so we can append 1s and stay within N <= 6.
    n = draw(st.integers(min_value=1, max_value=5))
    A = [draw(a_value) for _ in range(n)]
    return fmt(A)


_CURATED = [
    [1], [2], [3],
    [1, 1], [1, 2], [2, 1], [2, 2], [3, 1], [1, 3], [3, 3],
    [1, 1, 1], [1, 2, 3], [3, 2, 1], [2, 2, 2], [1, 3, 2], [2, 1, 2],
    [3, 3, 3], [1, 2, 2], [2, 2, 1],
    [1, 2, 3, 4], [4, 3, 2, 1], [2, 2, 2, 2], [1, 1, 2, 2], [2, 1, 2, 1],
    [3, 3, 3, 3],
    [1, 2, 3, 4, 5], [5, 4, 3, 2, 1], [2, 2, 2, 2, 2], [1, 2, 1, 2, 1],
    [1, 2, 3, 4, 5, 6], [6, 5, 4, 3, 2, 1], [2, 2, 2, 2, 2, 2],
    [1, 1, 1, 1, 1, 1], [3, 1, 4, 1, 5, 2],
]


@st.composite
def make_input_small(draw):
    # small product -> exact brute force is feasible.  Mix curated structural
    # cases with random tiny values (all-equal / distinct / sorted / reversed / dup).
    if draw(st.booleans()):
        return fmt(list(draw(st.sampled_from(_CURATED))))
    n = draw(st.integers(min_value=1, max_value=6))
    A = [draw(st.integers(min_value=1, max_value=4)) for _ in range(n)]
    return fmt(A)


@st.composite
def make_input_pair(draw):
    # N == 2, heavy on boundary combos of MIN/MAX plus random extremes.
    if draw(st.booleans()):
        a, b = draw(st.sampled_from([
            (1, 1), (1, 2), (2, 1), (2, 2), (1, MAXV), (MAXV, 1),
            (MAXV, MAXV), (MAXV, MAXV - 1), (2, MAXV), (MAXV, 2),
            (1, 3), (3, 1),
        ]))
    else:
        a, b = draw(a_value), draw(a_value)
    return fmt([a, b])


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

@given(make_input_general())
@settings(max_examples=25, deadline=None)
def test_output_format(stdin):
    # FORMAT / RANGE invariant on the full domain (incl. N=6 at magnitude 1e9).
    parse_R(run_candidate(stdin))


@given(make_input_trivial())
@settings(max_examples=18, deadline=None)
def test_lis_is_one(stdin):
    # CERTIFICATE: with N==1 or all A_i==1, LIS is always 1, so E == 1.
    R = parse_R(run_candidate(stdin))
    assert R == 1, "LIS must be 1 for %r, got %d" % (stdin, R)


@given(make_input_short())
@settings(max_examples=14, deadline=None)
def test_append_one_metamorphic(stdin):
    # METAMORPHIC: appending value-1 coordinates at the END never changes the
    # LIS of any realisation (a trailing 1 can extend nothing), so E is invariant.
    n, A = parse_input(stdin)
    R1 = parse_R(run_candidate(stdin))
    A2 = A + [1] * (6 - n)          # pad to the max length 6 with neutral 1s
    R2 = parse_R(run_candidate(fmt(A2)))
    assert R1 == R2, "appending trailing 1s changed answer: %d vs %d (%r)" % (R1, R2, stdin)


@given(make_input_small())
@settings(max_examples=45, deadline=None)
def test_bruteforce_exact(stdin):
    # Exact ground truth by enumerating the whole (small) sample space.
    n, A = parse_input(stdin)
    R = parse_R(run_candidate(stdin))
    exp = exact_R_bruteforce(A)
    assert R == exp, "exact mismatch for %r: got %d, expected %d" % (stdin, R, exp)


@given(make_input_pair())
@settings(max_examples=30, deadline=None)
def test_pair_closed_form(stdin):
    # Exact ground truth for N==2 via closed form -> checks EXTREME magnitudes.
    n, A = parse_input(stdin)
    R = parse_R(run_candidate(stdin))
    exp = exact_R_pair(A[0], A[1])
    assert R == exp, "pair mismatch for %r: got %d, expected %d" % (stdin, R, exp)