from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str


# ---------------------------------------------------------------------------
# Problem recap (for the property derivations, NOT a solver):
#   n hills with heights a_i (1..1e5). A "house/peak" can sit on a hill that is
#   STRICTLY higher than its present neighbours. We may only DECREASE hills (cost
#   1 per unit). Peaks are necessarily non-adjacent, so the max number of peaks
#   is ceil(n/2). Output f(1),f(2),...,f(ceil(n/2)) where f(k)=min total cost to
#   obtain AT LEAST k peaks.
#
# Provable facts used below (each proven, none require solving the general DP):
#   * OUTPUT has exactly ceil(n/2) = (n+1)//2 non-negative integers.
#   * f is NON-DECREASING in k (feasible set for k1<k2 is a superset).
#   * f(1) is EXACT and cheap: min over positions i of the cost to isolate one
#     peak at i = sum over existing neighbours j of max(0, a_j - a_i + 1).
#     (proof: making i a peak forces each neighbour final < a_i; conversely
#      lowering only the two neighbours already yields >=1 peak.)
#   * UPPER BOUND U: put peaks on all EVEN indices (that is exactly ceil(n/2)
#     of them) and lower every ODD index just below the min of its even
#     neighbours. This is an achievable config, so f(k) <= f(kmax) <= U for all k.
#   * For ODD n the maximum independent set of size (n+1)/2 on a path is UNIQUE
#     (the even indices), and keeping the even hills untouched is optimal, so
#     f(kmax) == U EXACTLY.
#   * REVERSAL invariance: reversing the hill sequence preserves adjacency /
#     strictness / costs, so the whole answer is identical.
#   * GLOBAL SHIFT invariance: adding a constant to every height changes no
#     pairwise difference, so every f(k) is unchanged.
# ---------------------------------------------------------------------------


def build_stdin(a):
    n = len(a)
    return "{}\n{}\n".format(n, " ".join(map(str, a)))


def parse_stdin(stdin):
    toks = stdin.split()
    n = int(toks[0])
    a = list(map(int, toks[1:1 + n]))
    return n, a


def parse_out(stdout, expected_count):
    try:
        vals = [int(t) for t in stdout.split()]
    except ValueError:
        raise AssertionError("output contains non-integer token: %r" % stdout)
    assert len(vals) == expected_count, (
        "expected %d numbers, got %d: %r" % (expected_count, len(vals), stdout))
    return vals


def exact_f1(a):
    """Exact minimum cost to obtain at least one peak."""
    n = len(a)
    best = None
    for i in range(n):
        c = 0
        if i - 1 >= 0 and a[i - 1] >= a[i]:
            c += a[i - 1] - a[i] + 1
        if i + 1 < n and a[i + 1] >= a[i]:
            c += a[i + 1] - a[i] + 1
        best = c if best is None else min(best, c)
    return best


def upper_bound_even(a):
    """Achievable cost when every even index is a peak (== f(kmax) when n odd)."""
    n = len(a)
    U = 0
    for j in range(1, n, 2):  # odd indices
        neigh = []
        if j - 1 >= 0:
            neigh.append(a[j - 1])
        if j + 1 < n:
            neigh.append(a[j + 1])
        m = min(neigh)
        U += max(0, a[j] - (m - 1))
    return U


# --------------------------- input generators ------------------------------

@st.composite
def gen_array(draw, min_n=1, max_n=100):
    n = draw(st.integers(min_n, max_n))
    mode = draw(st.integers(0, 6))
    if mode == 0:                                   # all equal (strictness edge)
        v = draw(st.integers(1, 100000))
        a = [v] * n
    elif mode == 1:                                 # extreme magnitudes 1 / 1e5
        a = [draw(st.sampled_from([1, 2, 99999, 100000])) for _ in range(n)]
    elif mode == 2:                                 # tiny bounded domain
        a = [draw(st.integers(1, 3)) for _ in range(n)]
    elif mode == 3:                                 # already sorted ascending
        a = sorted(draw(st.integers(1, 100000)) for _ in range(n))
    elif mode == 4:                                 # sorted descending
        a = sorted((draw(st.integers(1, 100000)) for _ in range(n)), reverse=True)
    elif mode == 5:                                 # heavy duplicates
        pool = [draw(st.integers(1, 100000)) for _ in range(draw(st.integers(1, 3)))]
        a = [draw(st.sampled_from(pool)) for _ in range(n)]
    else:                                           # uniform random
        a = [draw(st.integers(1, 100000)) for _ in range(n)]
    return a


def _check_core(stdin, vals):
    """Run every sound property that needs only the input + this output."""
    n, a = parse_stdin(stdin)
    kmax = (n + 1) // 2
    assert len(vals) == kmax
    # range + monotonicity
    for v in vals:
        assert v >= 0, "negative cost %d" % v
    for i in range(1, len(vals)):
        assert vals[i] >= vals[i - 1], "answers must be non-decreasing: %r" % vals
    # exact first value
    assert vals[0] == exact_f1(a), (
        "f(1) mismatch: got %d expected %d for a=%r" % (vals[0], exact_f1(a), a))
    # achievable upper bound on every entry
    U = upper_bound_even(a)
    for v in vals:
        assert v <= U, "cost %d exceeds achievable upper bound %d" % (v, U)
    # exact last value when n is odd (unique maximum peak set)
    if n % 2 == 1:
        assert vals[-1] == U, (
            "f(kmax) mismatch for odd n: got %d expected %d" % (vals[-1], U))


# ------------------------------- tests -------------------------------------

@st.composite
def make_input_general(draw):
    return build_stdin(draw(gen_array(min_n=1, max_n=100)))


@given(make_input_general())
@settings(max_examples=45, deadline=None)
def test_format_bounds_and_certificates(stdin):
    n, _ = parse_stdin(stdin)
    vals = parse_out(run_candidate(stdin), (n + 1) // 2)
    _check_core(stdin, vals)


@st.composite
def make_input_large(draw):
    n = draw(st.integers(200, 800))
    mode = draw(st.integers(0, 3))
    if mode == 0:
        a = [draw(st.sampled_from([1, 100000])) for _ in range(n)]
    elif mode == 1:
        v = draw(st.integers(1, 100000))
        a = [v] * n
    elif mode == 2:
        a = [draw(st.integers(1, 4)) for _ in range(n)]
    else:
        a = [draw(st.integers(1, 100000)) for _ in range(n)]
    return build_stdin(a)


@given(make_input_large())
@settings(max_examples=3, deadline=None)
def test_large_n(stdin):
    n, _ = parse_stdin(stdin)
    vals = parse_out(run_candidate(stdin), (n + 1) // 2)
    _check_core(stdin, vals)


@st.composite
def make_input_small_sweep(draw):
    # Deterministically reachable small bounded box: n in 1..5, heights in 1..3.
    n = draw(st.integers(1, 5))
    a = draw(st.lists(st.integers(1, 3), min_size=n, max_size=n))
    return build_stdin(a)


@given(make_input_small_sweep())
@settings(max_examples=60, deadline=None)
def test_small_sweep(stdin):
    n, _ = parse_stdin(stdin)
    vals = parse_out(run_candidate(stdin), (n + 1) // 2)
    _check_core(stdin, vals)


@st.composite
def make_input_reversal(draw):
    return build_stdin(draw(gen_array(min_n=1, max_n=80)))


@given(make_input_reversal())
@settings(max_examples=14, deadline=None)
def test_reversal_invariance(stdin):
    n, a = parse_stdin(stdin)
    rev_stdin = build_stdin(list(reversed(a)))
    v1 = parse_out(run_candidate(stdin), (n + 1) // 2)
    v2 = parse_out(run_candidate(rev_stdin), (n + 1) // 2)
    _check_core(stdin, v1)
    assert v1 == v2, "reversing the hills must give the same answer: %r vs %r" % (v1, v2)


@st.composite
def make_input_shift(draw):
    n = draw(st.integers(1, 80))
    a = [draw(st.integers(1, 50000)) for _ in range(n)]
    delta = draw(st.integers(1, 50000))
    b = [x + delta for x in a]           # still within [2, 100000]
    return build_stdin(a), build_stdin(b)


@given(make_input_shift())
@settings(max_examples=14, deadline=None)
def test_global_shift_invariance(pair):
    stdin_a, stdin_b = pair
    n, _ = parse_stdin(stdin_a)
    cnt = (n + 1) // 2
    va = parse_out(run_candidate(stdin_a), cnt)
    vb = parse_out(run_candidate(stdin_b), cnt)
    _check_core(stdin_a, va)
    assert va == vb, "adding a constant to all heights must not change costs: %r vs %r" % (va, vb)