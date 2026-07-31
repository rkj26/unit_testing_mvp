from hypothesis import given, strategies as st, settings, HealthCheck
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str  (the harness provides this)

# ---------------------------------------------------------------------------
# Problem 3996 -- "cups and key".
#
# Three cups, key starts under the middle one. Each turn the middle cup is
# swapped with the left or right cup (each w.p. 1/2). After n turns we want
# P(key under the middle cup), n = product(a_i), reported as the reduced
# fraction p/q, printed as (p mod M) / (q mod M) with M = 1e9+7.
#
# Tracking the key position (M / L / R) gives  p_0 = 1, p_{t+1} = (1 - p_t)/2,
# whose closed form is
#       p_n = (2^{n-1} + (-1)^n) / 3      over      2^{n-1}      (n >= 1),
# and this fraction is ALREADY irreducible:
#   * denominator q = 2^{n-1}  -- its only prime factor is 2.
#   * 3 | (2^{n-1}+(-1)^n) exactly, so the numerator p = (2^{n-1}+(-1)^n)/3 is
#     an odd integer, hence gcd(p, q) = 1.
# (Verified against every provided example, incl. the 18-digit one.)
#
# Because M = 1e9+7 is an odd prime coprime to 2, we can compute the printed
# residues from a *closed form* via Fermat (exponent reduced mod M-1); this is a
# deterministic CERTIFICATE, not a search/DP re-solve:
#       y = q mod M = 2^{n-1} mod M          (a power of two -> 1 <= y <= M-1)
#       x = p mod M = (y + (-1)^n) * inv3 mod M
# n mod (M-1) = prod(a_i mod (M-1));  n is even iff some a_i is even.
#
# Assertions used (all provable, none tie-dependent):
#   * exact reduced fraction (strongest certificate),
#   * format / range invariants (y is a power of two so never 0 mod M),
#   * parity certificate 3x - y == (-1)^n (independent of the exact value),
#   * cross-n metamorphic recurrence (q doubles; x_{n+1} == y_n - x_n),
#   * product-preserving invariance (permute / merge factors / append 1s),
#   * the provided examples.
# ---------------------------------------------------------------------------

M = 10**9 + 7
PHI = M - 1                      # 2^PHI == 1 (mod M), gcd(2, M) = 1
INV3 = pow(3, M - 2, M)
MAXA = 10**18                    # max a_i


def to_stdin(arr):
    return "%d\n%s\n" % (len(arr), " ".join(str(a) for a in arr))


def arr_from_stdin(stdin):
    return [int(t) for t in stdin.split()[1:]]


def expected(arr):
    """Exact reduced residues (x, y) = (p mod M, q mod M) via closed form."""
    n_even = any(a % 2 == 0 for a in arr)     # n even iff some factor even
    nmod = 1
    for a in arr:
        nmod = (nmod * (a % PHI)) % PHI        # n mod (M-1)
    em1 = (nmod - 1) % PHI                      # (n-1) mod (M-1); n-1 >= 0
    y = pow(2, em1, M)                          # 2^{n-1} mod M
    sign = 1 if n_even else (M - 1)            # (-1)^n
    x = ((y + sign) % M) * INV3 % M
    return x, y


def extract(out):
    """Parse 'x/y', tolerant of surrounding whitespace. Returns (x, y)."""
    s = out.strip()
    parts = s.split("/")
    assert len(parts) == 2, "output is not of the form x/y: %r" % (out,)
    a, b = parts[0].strip(), parts[1].strip()
    assert a.isdigit() and b.isdigit(), "non-numeric x/y: %r" % (out,)
    x, y = int(a), int(b)
    # x = p mod M in [0, M-1]; y = q mod M = 2^{n-1} mod M in [1, M-1] (never 0).
    assert 0 <= x < M, "x=%d out of range [0,M)" % (x,)
    assert 1 <= y < M, "y=%d out of range [1,M); denominator is a power of 2" % (y,)
    return x, y


def check_certificate(x, y, n_even):
    """Parity certificate 3x - y == (-1)^n (mod M): ties p to q via parity."""
    target = 1 if n_even else (M - 1)
    assert (3 * x - y) % M == target, (
        "certificate 3x-y == %s failed: x=%d y=%d n_even=%s got=%d"
        % ("+1" if n_even else "-1", x, y, n_even, (3 * x - y) % M)
    )


# Two heavy inputs (max k = 1e5) built once, reused cheaply.
BIG_ONES = to_stdin([1] * 100000)   # n = 1  (all odd)
BIG_TWOS = to_stdin([2] * 100000)   # n = 2^100000 (even, huge exponent)

# Values chosen to hit exact Fermat/exponent thresholds and magnitude extremes.
EDGE_VALUES = [
    1, 2, 3, 4, 5, 6, 7, 8, 9,
    M - 1, M, M + 1,          # n-1 == M-1 (exponent wraps to 0) sits right here
    2 * (M - 1),
    10**9, 10**9 - 1,
    MAXA, MAXA - 1, MAXA - 2, # extreme magnitude, both parities
    999999999999999999,       # max-ish odd
    999999999999999997,
]
ODD_VALUES = [v for v in EDGE_VALUES if v % 2 == 1] + [1, 3, 5, 7, 9]
EVEN_VALUES = [v for v in EDGE_VALUES if v % 2 == 0] + [2, 4, 6, 8]


@st.composite
def make_input(draw):
    """Targeted inputs: minimal/all-ones, extremes, parity-forced arrays,
    boundary magnitudes, and (rarely) the max-k heavy inputs."""
    r = draw(st.integers(min_value=0, max_value=99))
    if r < 4:
        return BIG_ONES
    if r < 8:
        return BIG_TWOS
    mode = r % 7
    if mode == 0:
        # all ones -> n == 1 (minimal), variable k
        return to_stdin([1] * draw(st.integers(min_value=1, max_value=25)))
    if mode == 1:
        # single element pinned at an edge / threshold value
        return to_stdin([draw(st.sampled_from(EDGE_VALUES))])
    if mode == 2:
        # fully random small array over the whole magnitude range
        k = draw(st.integers(min_value=1, max_value=8))
        return to_stdin([draw(st.integers(min_value=1, max_value=MAXA)) for _ in range(k)])
    if mode == 3:
        # all-odd array -> n odd  (forces (-1)^n = -1 branch)
        k = draw(st.integers(min_value=1, max_value=6))
        return to_stdin([draw(st.sampled_from(ODD_VALUES)) for _ in range(k)])
    if mode == 4:
        # contains at least one even -> n even (forces (-1)^n = +1 branch)
        k = draw(st.integers(min_value=1, max_value=5))
        arr = [draw(st.sampled_from(ODD_VALUES)) for _ in range(k)]
        arr.append(draw(st.sampled_from(EVEN_VALUES)))
        return to_stdin(arr)
    if mode == 5:
        # pure powers of two -> n is a power of 2 (even), structured exponent
        exps = [draw(st.integers(min_value=0, max_value=59)) for _ in range(draw(st.integers(1, 6)))]
        return to_stdin([2 ** e for e in exps])
    # mix of ones with extremes / boundaries
    k = draw(st.integers(min_value=2, max_value=6))
    return to_stdin([draw(st.sampled_from([1, MAXA, M, M - 1, M + 1, 2, 3])) for _ in range(k)])


@given(make_input())
@settings(max_examples=40, deadline=None, suppress_health_check=list(HealthCheck))
def test_exact_reduced_fraction(stdin):
    """Strongest check: the printed residues must equal the (provably)
    irreducible p/q reduced mod M, computed via the closed form."""
    x, y = extract(run_candidate(stdin))
    xe, ye = expected(arr_from_stdin(stdin))
    assert (x, y) == (xe, ye), "expected %d/%d got %d/%d" % (xe, ye, x, y)


@given(make_input())
@settings(max_examples=25, deadline=None, suppress_health_check=list(HealthCheck))
def test_format_and_certificate(stdin):
    """Format/range invariants + parity certificate (independent of the exact
    value): catches malformed output, out-of-range residues, zero denominator,
    and any p/q pair inconsistent with 3x - y == (-1)^n."""
    x, y = extract(run_candidate(stdin))
    n_even = any(a % 2 == 0 for a in arr_from_stdin(stdin))
    check_certificate(x, y, n_even)


PROVIDED = [
    ("1\n2\n", 1, 2),
    ("3\n1 1 1\n", 0, 1),
    ("1\n983155795040951739\n", 145599903, 436799710),
]


@given(st.just(0))
@settings(max_examples=1, deadline=None)
def test_provided_examples(_):
    for stdin, ex_x, ex_y in PROVIDED:
        x, y = extract(run_candidate(stdin))
        n_even = any(a % 2 == 0 for a in arr_from_stdin(stdin))
        check_certificate(x, y, n_even)
        assert (x, y) == (ex_x, ex_y), (
            "provided example %r expected %d/%d got %d/%d" % (stdin, ex_x, ex_y, x, y)
        )


# n and n+1 as single-element arrays (both must be <= 1e18).
N_STRATEGY = st.one_of(
    st.integers(min_value=1, max_value=MAXA - 1),
    st.sampled_from([1, 2, 3, 4, 5, 6, 7, 8,
                     M - 2, M - 1, M, M + 1, 2 * (M - 1),
                     10**9, 10**9 - 1, MAXA - 2, MAXA - 1]),
)


@given(N_STRATEGY)
@settings(max_examples=12, deadline=None)
def test_recurrence(n):
    """Metamorphic across consecutive n (independent of the closed form):
    q = 2^{n-1} doubles, and p_{n+1} = (1 - p_n)/2  =>  x_{n+1} == y_n - x_n."""
    xa, ya = extract(run_candidate(to_stdin([n])))
    xb, yb = extract(run_candidate(to_stdin([n + 1])))
    check_certificate(xa, ya, n % 2 == 0)
    check_certificate(xb, yb, (n + 1) % 2 == 0)
    assert yb == (2 * ya) % M, "denominator did not double: n=%d ya=%d yb=%d" % (n, ya, yb)
    assert xb == (ya - xa) % M, (
        "probability recurrence failed: n=%d xa=%d ya=%d xb=%d (expected %d)"
        % (n, xa, ya, xb, (ya - xa) % M)
    )


@st.composite
def product_preserving_pair(draw):
    """Two arrays with identical product n: one keeps factors f1,f2 separate,
    the other merges them (f1*f2), appends some 1s, and is permuted."""
    base_k = draw(st.integers(min_value=0, max_value=5))
    base = [draw(st.one_of(st.integers(min_value=1, max_value=MAXA),
                           st.sampled_from([1, 2, 3, MAXA, M])))
            for _ in range(base_k)]
    f1 = draw(st.integers(min_value=1, max_value=10**9))
    f2 = draw(st.integers(min_value=1, max_value=MAXA // f1))  # f1*f2 <= 1e18 -> valid element
    ones = draw(st.integers(min_value=0, max_value=4))
    list_a = base + [f1, f2]
    list_b = list(draw(st.permutations(base + [f1 * f2] + [1] * ones)))
    return list_a, list_b


@given(product_preserving_pair())
@settings(max_examples=12, deadline=None)
def test_product_preserving(pair):
    """Reordering, merging factors, and appending 1s all leave n = prod(a_i)
    unchanged, so the answer must be byte-for-byte identical."""
    list_a, list_b = pair
    n_even = any(a % 2 == 0 for a in list_a)  # product parity is order-independent
    xa, ya = extract(run_candidate(to_stdin(list_a)))
    xb, yb = extract(run_candidate(to_stdin(list_b)))
    check_certificate(xa, ya, n_even)
    assert (xa, ya) == (xb, yb), (
        "product-preserving transform changed the answer: %d/%d vs %d/%d" % (xa, ya, xb, yb)
    )