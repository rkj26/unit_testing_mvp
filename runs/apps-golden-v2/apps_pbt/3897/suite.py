import re
from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

MOD = 10**9 + 7

# Small primes used for building known factorizations (fast to factor).
SMALL_PRIMES = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31]
# Genuinely prime, < 1e9 (verified). Used to exercise the large-magnitude a_i region.
BIG_PRIMES = [999999937, 998244353]


def fmt(n, a):
    """Build ONE valid STDIN string: line1 = n, line2 = space-separated a_i, trailing newline."""
    assert len(a) == n
    return "{}\n{}\n".format(n, " ".join(str(x) for x in a))


def parse_out(stdout):
    """Format invariant: output must be exactly one non-negative integer token."""
    s = stdout.strip()
    assert s != "", "empty output"
    toks = s.split()
    assert len(toks) == 1, "expected a single integer, got: {!r}".format(stdout)
    assert re.fullmatch(r"\d+", toks[0]), "not a non-negative integer: {!r}".format(toks[0])
    return int(toks[0])


def comb_mod(N, K):
    """C(N,K) mod p, exact (K! is coprime to prime p since K <= 499 < p)."""
    if K < 0 or K > N:
        return 0
    K = min(K, N - K)
    num = 1
    den = 1
    for i in range(K):
        num = num * ((N - i) % MOD) % MOD
        den = den * ((i + 1) % MOD) % MOD
    return num * pow(den, MOD - 2, MOD) % MOD


def decomp_count(n, exps):
    """Expected answer from a KNOWN prime-exponent multiset (stars-and-bars per prime)."""
    res = 1
    for e in exps:
        res = res * comb_mod(e + n - 1, n - 1) % MOD
    return res


# ---------------------------------------------------------------------------
# Test 1: FORMAT / RANGE invariants over a broad, edge-heavy input space.
# The true count mod p is always in [1, p-1] (never 0: every prime exponent
# e satisfies e + n - 1 <= 14999 < p, so no binomial is divisible by p, and a
# product of nonzero residues mod a prime is nonzero). Never assert its value.
# ---------------------------------------------------------------------------
@st.composite
def make_any(draw):
    mode = draw(st.integers(0, 6))
    if mode == 0:                                   # n = 1 (min size), any m
        n = 1
        a = [draw(st.one_of(st.integers(1, 10**9),
                            st.sampled_from([1, 2, 10**9, 999999937, 536870912])))]
    elif mode == 1:                                 # m = 1 (all ones), any n
        n = draw(st.integers(1, 500))
        a = [1] * n
    elif mode == 2:                                 # MAX size, mostly ones + a few small
        n = draw(st.integers(400, 500))
        a = [1] * n
        for _ in range(draw(st.integers(0, 12))):
            a[draw(st.integers(0, n - 1))] = draw(st.sampled_from([2, 3, 5, 6, 7, 10, 12, 100, 512]))
    elif mode == 3:                                 # EXTREME magnitudes, small n
        n = draw(st.integers(1, 5))
        a = [draw(st.sampled_from([1, 10**9, 999999937, 998244353, 536870912, 2, 999999999]))
             for _ in range(n)]
    elif mode == 4:                                 # typical random
        n = draw(st.integers(1, 40))
        a = [draw(st.integers(1, 10**6)) for _ in range(n)]
    elif mode == 5:                                 # all-equal (heavy duplicates)
        n = draw(st.integers(1, 30))
        v = draw(st.sampled_from([1, 2, 3, 6, 7, 12, 1000, 10**6]))
        a = [v] * n
    else:                                           # one distinct element among dups
        n = draw(st.integers(2, 20))
        v = draw(st.integers(2, 1000))
        a = [v] * n
        a[0] = 1
    return fmt(n, a)


@given(make_any())
@settings(max_examples=24, deadline=None)
def test_format_and_range(stdin):
    v = parse_out(run_candidate(stdin))
    assert 1 <= v <= MOD - 1, "answer out of [1, p-1]: {}".format(v)


# ---------------------------------------------------------------------------
# Test 2: CERTIFICATE for exactly-known trivial answers.
#   * n == 1  -> only decomposition is [m]         -> answer 1
#   * m == 1  -> only decomposition is [1,...,1]    -> answer 1
# ---------------------------------------------------------------------------
@st.composite
def make_trivial(draw):
    if draw(st.booleans()):
        v = draw(st.one_of(st.integers(1, 10**9),
                           st.sampled_from([1, 2, 10**9, 999999937, 998244353, 536870912])))
        return fmt(1, [v])
    n = draw(st.integers(1, 500))
    return fmt(n, [1] * n)


@given(make_trivial())
@settings(max_examples=20, deadline=None)
def test_trivial_answers(stdin):
    v = parse_out(run_candidate(stdin))
    assert v == 1, "n==1 or m==1 must give exactly 1, got {}".format(v)


# ---------------------------------------------------------------------------
# Test 3: METAMORPHIC - the answer depends only on the multiset {a_i} / on m
# and n, never on order. Permuting the input must not change the output.
# ---------------------------------------------------------------------------
@st.composite
def make_perm(draw):
    n = draw(st.integers(1, 10))
    a = [draw(st.one_of(st.integers(1, 60),
                        st.sampled_from([1, 2, 3, 4, 6, 1000000000])))
         for _ in range(n)]
    return a


@given(make_perm())
@settings(max_examples=12, deadline=None)
def test_permutation_invariance(a):
    n = len(a)
    o_base = parse_out(run_candidate(fmt(n, a)))
    # sorted() is a canonical permutation (differs from base whenever a is unsorted).
    o_sorted = parse_out(run_candidate(fmt(n, sorted(a))))
    assert o_base == o_sorted, \
        "order changed the answer: {} vs {}".format(o_base, o_sorted)


# ---------------------------------------------------------------------------
# Test 4: METAMORPHIC - multiplicativity over coprime parts. For fixed n, the
# count is multiplicative: if gcd(m1,m2)=1 then f(m1*m2,n)=f(m1,n)*f(m2,n).
# A uses only primes {2,3}; B uses only {5,7} (coprime); C[i]=A[i]*B[i] has
# product m1*m2 and length n. All values stay <= ~5.3e6 <= 1e9.
# ---------------------------------------------------------------------------
@st.composite
def make_coprime_triple(draw):
    n = draw(st.integers(1, 8))
    A, B = [], []
    for _ in range(n):
        A.append((2 ** draw(st.integers(0, 5))) * (3 ** draw(st.integers(0, 3))))
        B.append((5 ** draw(st.integers(0, 3))) * (7 ** draw(st.integers(0, 2))))
    C = [A[i] * B[i] for i in range(n)]
    return fmt(n, A), fmt(n, B), fmt(n, C)


@given(make_coprime_triple())
@settings(max_examples=8, deadline=None)
def test_multiplicativity_coprime(triple):
    sa, sb, sc = triple
    oa = parse_out(run_candidate(sa))
    ob = parse_out(run_candidate(sb))
    oc = parse_out(run_candidate(sc))
    assert oc == oa * ob % MOD, \
        "multiplicativity broken: f(m1m2)={} but f(m1)*f(m2)={}".format(oc, oa * ob % MOD)


# ---------------------------------------------------------------------------
# Test 5: CERTIFICATE from a CONSTRUCTED factorization. We build the list from
# known prime factors (never factoring an arbitrary input), so we know the exact
# prime-exponent multiset of m and can validate the count via stars-and-bars.
# Covers: min/max n, single prime, prime powers, multi-prime, a_i pinned at
# exactly 1e9 (=2^9*5^9), and a large prime a_i.
# ---------------------------------------------------------------------------
@st.composite
def make_constructed(draw):
    n = draw(st.one_of(st.just(1), st.just(2), st.integers(1, 40), st.just(500)))
    a = [1] * n
    exp = {}

    # Optional edge seeds combining structure with extreme magnitude.
    if draw(st.booleans()):                         # a slot pinned EXACTLY at 1e9 = 2^9 * 5^9
        j = draw(st.integers(0, n - 1))
        if a[j] == 1:
            a[j] = 10**9
            exp[2] = exp.get(2, 0) + 9
            exp[5] = exp.get(5, 0) + 9
    if draw(st.booleans()):                         # a slot = large prime (exponent-1 factor, big magnitude)
        j = draw(st.integers(0, n - 1))
        if a[j] == 1:
            q = draw(st.sampled_from(BIG_PRIMES))
            a[j] = q
            exp[q] = exp.get(q, 0) + 1

    # Random small-prime insertions (fast to factor even at n=500).
    for _ in range(draw(st.integers(0, 20))):
        p = draw(st.sampled_from(SMALL_PRIMES))
        j = draw(st.integers(0, n - 1))
        if a[j] * p <= 10**9:
            a[j] *= p
            exp[p] = exp.get(p, 0) + 1

    expected = decomp_count(n, list(exp.values()))
    return fmt(n, a), expected


@given(make_constructed())
@settings(max_examples=26, deadline=None)
def test_constructed_factorization(case):
    stdin, expected = case
    v = parse_out(run_candidate(stdin))
    assert v == expected, "constructed decomposition count mismatch: got {}, expected {}".format(v, expected)
