from hypothesis import given, strategies as st, settings, assume
from harness import run_candidate

# ---------------------------------------------------------------------------
# Problem 3985.
# n positive ints a[1..n]; m distinct "good pairs" (i,j) with i<j and i+j odd
# (so every pair joins an odd-1-based-index position to an even-1-based-index
# position -> the operation graph is BIPARTITE by index parity).
# Operation: pick a good pair and v>1 dividing both endpoints, divide both by v.
# Maximize the number of operations (a pair may be reused).
#
# Optimal strategy always uses primes v (a composite v costs 1 op but consumes
# more prime factors). So the answer = sum over primes p of a bipartite MAX FLOW:
#   source -> odd-index node   capacity = exponent of p in a[i]
#   even-index node -> sink     capacity = exponent of p in a[j]
#   odd-index -> even-index     capacity = infinite   (for each good pair)
#
# We NEVER recompute this optimum. We only assert sound invariants / certificates
# / metamorphic relations.
# ---------------------------------------------------------------------------

# ---- module-level sieve of primes up to ceil(sqrt(1e9)) for factor counting --
def _sieve(limit):
    is_p = bytearray([1]) * (limit + 1)
    is_p[0] = is_p[1] = 0
    for i in range(2, int(limit ** 0.5) + 1):
        if is_p[i]:
            is_p[i * i::i] = bytearray(len(is_p[i * i::i]))
    return [i for i in range(2, limit + 1) if is_p[i]]

_PRIMES = _sieve(31623)  # sqrt(1e9) ~ 31622.7


def _omega(x):
    """Total number of prime factors of x counted WITH multiplicity."""
    if x <= 1:
        return 0
    cnt = 0
    for p in _PRIMES:
        if p * p > x:
            break
        while x % p == 0:
            x //= p
            cnt += 1
    if x > 1:
        cnt += 1
    return cnt


# --------------------------- (de)serialisation ------------------------------
def _serialize(n, a, pairs):
    lines = ["{} {}".format(n, len(pairs)), " ".join(map(str, a))]
    for (i, j) in pairs:
        lines.append("{} {}".format(i, j))
    return "\n".join(lines) + "\n"


def _parse_stdin(s):
    t = s.split()
    n = int(t[0]); m = int(t[1])
    a = [int(t[2 + k]) for k in range(n)]
    base = 2 + n
    pairs = [(int(t[base + 2 * k]), int(t[base + 2 * k + 1])) for k in range(m)]
    return n, m, a, pairs


def _parse_answer(out):
    toks = out.split()
    assert len(toks) == 1, "output must be a single integer, got: {!r}".format(out)
    v = int(toks[0])
    assert v >= 0, "answer must be non-negative, got {}".format(v)
    return v


# ------------------------------- generators ---------------------------------
_SMALL_PRIMES = [2, 3, 5, 7, 11, 13]
# extreme / boundary magnitudes (all <= 1e9):
#   1                 -> no factors (never usable)
#   2                 -> single tiny factor
#   536870912 = 2^29  -> largest power of two <= 1e9 (Omega 29)
#   387420489 = 3^18  -> largest power of three <= 1e9 (Omega 18)
#   1000000000 = 2^9*5^9 -> max value, highly divisible (Omega 18)
#   999999937         -> large prime (coprime to almost everything)
#   4, 8, 9           -> small prime powers
_EXTREMES = [1, 2, 4, 8, 9, 536870912, 387420489, 1000000000, 999999937]


def _gen_smooth(draw, cap):
    """A smooth number <= cap built from small primes (creates SHARED factors)."""
    val = 1
    k = draw(st.integers(min_value=0, max_value=14))
    for _ in range(k):
        p = draw(st.sampled_from(_SMALL_PRIMES))
        if val * p <= cap:
            val *= p
        else:
            break
    return val


def _draw_n(draw):
    # bias heavily toward the small / boundary end while still reaching 100.
    return draw(st.one_of(
        st.just(2), st.just(3), st.just(4), st.just(5),
        st.integers(min_value=2, max_value=12),
        st.integers(min_value=2, max_value=100),
        st.just(100),
    ))


def _draw_values(draw, n, cap):
    mode = draw(st.sampled_from(["smooth", "equal", "extreme", "mixed"]))
    if mode == "equal":
        v = _gen_smooth(draw, cap)
        return [v] * n
    if mode == "smooth":
        return [_gen_smooth(draw, cap) for _ in range(n)]
    if mode == "extreme":
        pool = [x for x in _EXTREMES if x <= cap] or [1]
        return [draw(st.sampled_from(pool)) for _ in range(n)]
    # mixed: combine an edge structure with extreme magnitudes
    pool = [x for x in _EXTREMES if x <= cap] or [1]
    out = []
    for _ in range(n):
        if draw(st.booleans()):
            out.append(_gen_smooth(draw, cap))
        else:
            out.append(draw(st.sampled_from(pool)))
    return out


def _draw_pairs(draw, n):
    odds = [i for i in range(1, n + 1) if i % 2 == 1]
    evens = [i for i in range(1, n + 1) if i % 2 == 0]
    all_pairs = []
    for o in odds:
        for e in evens:
            lo, hi = (o, e) if o < e else (e, o)
            all_pairs.append((lo, hi))
    # all_pairs is guaranteed non-empty (n>=2 => >=1 odd and >=1 even index)
    maxm = min(100, len(all_pairs))
    # sometimes take the COMPLETE bipartite pair set (structural edge)
    if len(all_pairs) <= 100 and draw(st.booleans()):
        return all_pairs
    idxs = draw(st.sets(st.integers(min_value=0, max_value=len(all_pairs) - 1),
                        min_value=1, max_value=maxm))
    return [all_pairs[i] for i in sorted(idxs)]


@st.composite
def make_input(draw, cap=10 ** 9):
    n = _draw_n(draw)
    a = _draw_values(draw, n, cap)
    pairs = _draw_pairs(draw, n)
    return _serialize(n, a, pairs)


@st.composite
def make_input_small(draw):
    # values small enough that squaring stays <= 1e9 (31622^2 < 1e9)
    n = _draw_n(draw)
    cap = 31622
    a = [_gen_smooth(draw, cap) for _ in range(n)]
    pairs = _draw_pairs(draw, n)
    return _serialize(n, a, pairs)


# --------------------------------- tests ------------------------------------
@given(make_input())
@settings(max_examples=45, deadline=None)
def test_format_and_upper_bound(stdin):
    """Output is a single non-negative int, and <= min(OddOmega, EvenOmega)
    over positions that appear in some pair. Each operation joins an odd-index
    to an even-index and removes >=1 prime factor from each side, so #ops is
    bounded by the total prime-factor count available on either parity side."""
    n, m, a, pairs = _parse_stdin(stdin)
    ans = _parse_answer(run_candidate(stdin))

    used = set()
    for (i, j) in pairs:
        used.add(i); used.add(j)
    odd_omega = sum(_omega(a[p - 1]) for p in used if p % 2 == 1)
    even_omega = sum(_omega(a[p - 1]) for p in used if p % 2 == 0)
    ub = min(odd_omega, even_omega)
    assert ans <= ub, "answer {} exceeds sound upper bound {}".format(ans, ub)


@given(make_input())
@settings(max_examples=20, deadline=None)
def test_reverse_invariant(stdin):
    """Reversing the array and remapping each pair (i,j) -> (n+1-j, n+1-i)
    yields an ISOMORPHIC instance (same value-edges, i+j parity preserved),
    so the answer must be identical."""
    n, m, a, pairs = _parse_stdin(stdin)
    ra = list(reversed(a))
    rpairs = [(n + 1 - j, n + 1 - i) for (i, j) in pairs]  # already lo<hi
    ans0 = _parse_answer(run_candidate(stdin))
    ans1 = _parse_answer(run_candidate(_serialize(n, ra, rpairs)))
    assert ans0 == ans1, "reverse changed answer: {} vs {}".format(ans0, ans1)


@given(make_input())
@settings(max_examples=20, deadline=None)
def test_set_to_one_monotone(stdin):
    """Setting any value to 1 removes all its factors -> node capacity drops to
    0 for every prime -> max flow can only decrease. Answer must not increase."""
    n, m, a, pairs = _parse_stdin(stdin)
    used = sorted({p for pr in pairs for p in pr})
    # target the in-pair position with the most factors (most impactful).
    k = max(used, key=lambda p: _omega(a[p - 1]))
    ans0 = _parse_answer(run_candidate(stdin))
    b = list(a); b[k - 1] = 1
    ans1 = _parse_answer(run_candidate(_serialize(n, b, pairs)))
    assert ans1 <= ans0, "reducing a value raised the answer: {} -> {}".format(ans0, ans1)


@given(make_input())
@settings(max_examples=20, deadline=None)
def test_add_pair_monotone(stdin):
    """Adding a new (distinct, valid) good pair only adds routing options ->
    max flow can never decrease for any prime. Answer must not decrease."""
    n, m, a, pairs = _parse_stdin(stdin)
    assume(m < 100)
    odds = [i for i in range(1, n + 1) if i % 2 == 1]
    evens = [i for i in range(1, n + 1) if i % 2 == 0]
    all_pairs = set()
    for o in odds:
        for e in evens:
            all_pairs.add((o, e) if o < e else (e, o))
    unused = sorted(all_pairs - set(pairs))
    assume(bool(unused))
    aug = pairs + [unused[0]]
    ans0 = _parse_answer(run_candidate(stdin))
    ans1 = _parse_answer(run_candidate(_serialize(n, a, aug)))
    assert ans1 >= ans0, "adding a pair lowered the answer: {} -> {}".format(ans0, ans1)


@given(make_input_small())
@settings(max_examples=15, deadline=None)
def test_square_doubles(stdin):
    """Squaring every value doubles every prime exponent -> all node capacities
    double -> every prime's max flow doubles (integer capacity scaling) -> total
    answer doubles exactly."""
    n, m, a, pairs = _parse_stdin(stdin)
    ans0 = _parse_answer(run_candidate(stdin))
    sq = [x * x for x in a]
    ans1 = _parse_answer(run_candidate(_serialize(n, sq, pairs)))
    assert ans1 == 2 * ans0, "squaring values should double answer: {} vs 2*{}".format(ans1, ans0)
