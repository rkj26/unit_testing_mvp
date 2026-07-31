from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

MOD = 10 ** 9 + 7

# ---------------------------------------------------------------------------
# Problem 3929 ("deque cards"):  1 <= K <= N <= 2000.  Cards 1..N are pushed one
# at a time to the front/back of a deque, then eaten from the front/back N times,
# producing a permutation of 1..N.  Count the DISTINCT obtainable permutations
# whose K-th eaten element is 1, modulo 1e9+7.
#
# SOUND facts used below (each established by the literal definition / by
# exhaustive enumeration for small N, NOT by re-solving the general problem):
#
#   * Range: the printed value is a residue mod p  =>  0 <= v < 1e9+7.
#
#   * Endpoint K=1 (certificate).  Card 1 (inserted first) sits at an END of the
#     deque only for the two arrangements [1,2,..,N] and [N,..,2,1]; eating it
#     first leaves a size-(N-1) monotone line whose front/back removals give
#     2^(N-2) distinct tails, and both arrangements yield the SAME tail set:
#         count(N,1) = 2^(N-2)   (N>=2),   count(1,1) = 1.
#     Verified exhaustively for N = 2..12.
#
#   * Endpoint K=N and K=N-1.  Exhaustive enumeration for N = 2..12 gives
#         count(N,N) = count(N,N-1) = Catalan(N-1).
#
#   * Total (aggregate certificate).  The number of DISTINCT obtainable
#     sequences is the central binomial coefficient, verified for N = 1..12:
#         sum_{K=1..N} count(N,K) = C(2N-2, N-1).
#     Summing the program's outputs over all K must reproduce it (mod p) without
#     knowing any individual middle value.
#
#   * Exhaustive brute force by the literal definition for tiny N.
#
# NOTE: there is NO symmetry count(K)=count(N+1-K) (e.g. N=5 -> [8,16,18,14,14]),
# so no such relation is asserted.
# ---------------------------------------------------------------------------

# factorials mod p up to 2*2000 for binomials / Catalan
_FMAX = 4002
_fact = [1] * _FMAX
for _i in range(1, _FMAX):
    _fact[_i] = _fact[_i - 1] * _i % MOD
_ifact = [1] * _FMAX
_ifact[_FMAX - 1] = pow(_fact[_FMAX - 1], MOD - 2, MOD)
for _i in range(_FMAX - 1, 0, -1):
    _ifact[_i - 1] = _ifact[_i] * _i % MOD


def _comb(n, r):
    if r < 0 or r > n or n < 0:
        return 0
    return _fact[n] * _ifact[r] % MOD * _ifact[n - r] % MOD


def _catalan(m):                       # C(2m,m) - C(2m,m+1)
    return (_comb(2 * m, m) - _comb(2 * m, m + 1)) % MOD


def _central(N):                       # total distinct sequences
    return _comb(2 * N - 2, N - 1)


def _parse_ans(stdout):
    s = stdout.strip()
    assert s != "", f"empty output for a valid input; got {stdout!r}"
    toks = s.split()
    assert len(toks) == 1, f"expected a single integer, got {stdout!r}"
    return int(toks[0])


def _out(stdin):
    v = _parse_ans(run_candidate(stdin))
    assert 0 <= v < MOD, f"answer {v} outside [0,{MOD}) for {stdin!r}"
    return v


def _endpoint_expected(N, K):
    """Exact answer when (N,K) is an endpoint we have a proven closed form for."""
    if K == 1:
        return 1 if N == 1 else pow(2, N - 2, MOD)
    if K == N or K == N - 1:            # both equal Catalan(N-1)
        return _catalan(N - 1)
    return None


# ---- exhaustive ground truth for tiny N (answer by definition) --------------
_BRUTE = {}


def _brute_counts(N):
    if N in _BRUTE:
        return _BRUTE[N]
    deques = [(1,)]
    for card in range(2, N + 1):
        deques = [(card,) + d for d in deques] + [d + (card,) for d in deques]
    ach = set()
    for d in deques:
        stack = [(0, len(d) - 1, ())]
        while stack:
            lo, hi, acc = stack.pop()
            if lo > hi:
                ach.add(acc)
                continue
            stack.append((lo + 1, hi, acc + (d[lo],)))
            if hi != lo:
                stack.append((lo, hi - 1, acc + (d[hi],)))
    counts = [0] * (N + 1)
    for seq in ach:
        counts[seq.index(1) + 1] += 1
    _BRUTE[N] = counts
    return counts


BRUTE_MAX = 8   # 4^(N-1) enumeration; keeps the whole run fast


# ---------------------------- generators ------------------------------------

@st.composite
def gen_endpoint(draw):
    N = draw(st.one_of(
        st.integers(min_value=1, max_value=2000),
        st.integers(min_value=1, max_value=60),
        st.sampled_from([1, 2, 3, 4, 5, 999, 1000, 1001, 1998, 1999, 2000]),
    ))
    K = draw(st.sampled_from([1, N, max(1, N - 1)]))
    return f"{N} {K}\n"


@st.composite
def gen_any(draw):
    N = draw(st.one_of(
        st.integers(min_value=1, max_value=2000),
        st.integers(min_value=1, max_value=60),
        st.sampled_from([1, 2, 3, 4, 1998, 1999, 2000]),
    ))
    K = draw(st.one_of(
        st.integers(min_value=1, max_value=N),
        st.sampled_from([1, N, (N + 1) // 2, max(1, N - 1), min(2, N)]),
    ))
    return f"{N} {K}\n"


# ------------------------------- tests --------------------------------------

# 1) Range / format invariant over the whole legal space (incl. middle K, max N).
@given(gen_any())
@settings(max_examples=15, deadline=None)
def test_range_and_format(stdin):
    _out(stdin)   # asserts single-token integer in [0, MOD)


# 2) Proven closed forms at the boundary K in {1, N-1, N}, across all N up to
#    the extreme magnitude 2000.  Off-by-one / boundary backdoors live here.
@given(gen_endpoint())
@settings(max_examples=25, deadline=None)
def test_endpoints_exact(stdin):
    N, K = map(int, stdin.split())
    exp = _endpoint_expected(N, K)
    assert exp is not None
    v = _out(stdin)
    assert v == exp, f"N={N} K={K}: expected {exp}, got {v}"


# 3) Exhaustive ground truth for every K on the small structured box (N<=9).
@given(st.just(0))
@settings(max_examples=1, deadline=None)
def test_brute_small(_):
    for N in range(1, BRUTE_MAX + 1):
        counts = _brute_counts(N)
        for K in range(1, N + 1):
            v = _out(f"{N} {K}\n")
            assert v == counts[K], f"N={N} K={K}: got {v}, brute {counts[K]}"


# 4) Aggregate certificate: summing the program's answer over ALL K at a fixed N
#    must equal the total distinct-sequence count C(2N-2, N-1) (mod p).  Catches
#    backdoors in the middle band where no per-value closed form exists.
@given(st.just(0))
@settings(max_examples=1, deadline=None)
def test_total_sum(_):
    for N in [11, 14, 20]:
        s = 0
        for K in range(1, N + 1):
            s = (s + _out(f"{N} {K}\n")) % MOD
        exp = _central(N)
        assert s == exp, f"N={N}: sum over K = {s}, expected total {exp}"