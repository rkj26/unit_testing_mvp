from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str  (the harness provides this)

MAXV = 10 ** 9


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def build_stdin(N, K, Q, A):
    return "{} {} {}\n{}\n".format(N, K, Q, " ".join(str(a) for a in A))


def parse_answer(out):
    toks = out.split()
    assert len(toks) == 1, "expected a single integer, got: {!r}".format(out)
    return int(toks[0])


def draw_values(draw, n, lo=1, hi=MAXV):
    """Value list biased toward edges / duplicates / extremes."""
    mode = draw(st.integers(0, 4))
    if mode == 0:  # all-equal
        v = draw(st.integers(lo, hi))
        return [v] * n
    if mode == 1:  # extreme magnitudes pinned at bounds
        pool = [lo, lo + 1, hi - 1, hi, (lo + hi) // 2]
        return [draw(st.sampled_from(pool)) for _ in range(n)]
    if mode == 2:  # heavy duplicates, tiny domain
        return [draw(st.integers(1, 3)) for _ in range(n)]
    if mode == 3:  # broad random
        return [draw(st.integers(lo, hi)) for _ in range(n)]
    # mix of extremes and tiny values in the SAME array
    pool = [1, 2, MAXV, MAXV - 1]
    return [draw(st.one_of(st.sampled_from(pool), st.integers(1, 10))) for _ in range(n)]


# ----------------------------------------------------------------------------
# generators
# ----------------------------------------------------------------------------
@st.composite
def gen_instance(draw):
    # mostly small (structural sweeps); occasionally large (threshold-in-N bugs)
    if draw(st.integers(0, 5)) == 0:
        N = draw(st.integers(40, 300))
    else:
        N = draw(st.integers(1, 14))
    K = draw(st.integers(1, N))
    Q = draw(st.integers(1, N - K + 1))
    A = draw_values(draw, N)
    return (N, K, Q, A)


@st.composite
def gen_k1(draw):
    N = draw(st.integers(1, 16))
    K = 1
    Q = draw(st.integers(1, N))          # N - K + 1 == N
    A = draw_values(draw, N)
    return (N, K, Q, A)


@st.composite
def gen_trivial(draw):
    N = draw(st.integers(1, 14))
    choice = draw(st.integers(0, 2))
    if choice == 0:                      # Q == 1  -> only one element removed
        K = draw(st.integers(1, N))
        Q = 1
        A = draw_values(draw, N)
    elif choice == 1:                    # all-equal -> every removed value equal
        K = draw(st.integers(1, N))
        Q = draw(st.integers(1, N - K + 1))
        v = draw(st.integers(1, MAXV))
        A = [v] * N
    else:                                # K == N  -> forces Q == 1
        K = N
        Q = 1
        A = draw_values(draw, N)
    return (N, K, Q, A)


@st.composite
def gen_small_values(draw):
    # bounded values so shifting / scaling keeps A within [1, 1e9]
    N = draw(st.integers(1, 10))
    K = draw(st.integers(1, N))
    Q = draw(st.integers(1, N - K + 1))
    A = [draw(st.integers(1, 1000)) for _ in range(N)]
    return (N, K, Q, A)


@st.composite
def gen_for_monotone(draw):
    N = draw(st.integers(2, 14))
    K = draw(st.integers(1, N - 1))      # ensure K <= N-1
    Q = draw(st.integers(1, N - K))      # so Q+1 <= N-K+1 stays feasible
    A = draw_values(draw, N)
    return (N, K, Q, A)


# ----------------------------------------------------------------------------
# tests
# ----------------------------------------------------------------------------
@given(gen_instance())
@settings(max_examples=45, deadline=None)
def test_format_and_bounds(data):
    N, K, Q, A = data
    ans = parse_answer(run_candidate(build_stdin(N, K, Q, A)))
    # X and Y are removed elements, i.e. elements of A, so:
    assert ans >= 0
    assert ans <= max(A) - min(A)


@given(gen_trivial())
@settings(max_examples=40, deadline=None)
def test_trivial_zero(data):
    # Q==1 (one element removed) OR all-equal OR K==N(=>Q==1) => X==Y => answer 0
    N, K, Q, A = data
    ans = parse_answer(run_candidate(build_stdin(N, K, Q, A)))
    assert ans == 0


@given(gen_k1())
@settings(max_examples=35, deadline=None)
def test_k1_exact(data):
    # With K==1 each op removes any single chosen element, so we may remove any
    # Q elements; optimum is the tightest window of Q values in sorted order.
    N, K, Q, A = data
    ans = parse_answer(run_candidate(build_stdin(N, K, Q, A)))
    s = sorted(A)
    best = min(s[i + Q - 1] - s[i] for i in range(N - Q + 1))
    assert ans == best


@given(gen_small_values())
@settings(max_examples=18, deadline=None)
def test_shift_scale_reverse(data):
    # The game depends only on relative order of values, so:
    #   reverse -> same answer; shift by c -> same answer; scale by m -> m*answer.
    N, K, Q, A = data
    base = parse_answer(run_candidate(build_stdin(N, K, Q, A)))

    rev = parse_answer(run_candidate(build_stdin(N, K, Q, list(reversed(A)))))
    assert rev == base

    c = MAXV - max(A)                    # pins max to 1e9 (extreme magnitude)
    A2 = [a + c for a in A]
    assert 1 <= min(A2) and max(A2) <= MAXV
    shifted = parse_answer(run_candidate(build_stdin(N, K, Q, A2)))
    assert shifted == base

    m = MAXV // max(A)                   # >= 10**6 since max(A) <= 1000
    A3 = [a * m for a in A]
    assert max(A3) <= MAXV
    scaled = parse_answer(run_candidate(build_stdin(N, K, Q, A3)))
    assert scaled == base * m


@given(gen_for_monotone())
@settings(max_examples=18, deadline=None)
def test_monotone_in_q_and_reverse(data):
    # More forced removals cannot reduce the range: prefix of a valid (Q+1)-op
    # run is a valid Q-op run whose removed values are a subset. So ans is
    # non-decreasing in Q.  Also re-check reversal symmetry.
    N, K, Q, A = data
    a_q = parse_answer(run_candidate(build_stdin(N, K, Q, A)))
    a_q1 = parse_answer(run_candidate(build_stdin(N, K, Q + 1, A)))
    assert a_q >= 0 and a_q1 >= 0
    assert a_q <= a_q1

    a_rev = parse_answer(run_candidate(build_stdin(N, K, Q, list(reversed(A)))))
    assert a_rev == a_q
