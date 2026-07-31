import re
from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

# ------------------------------------------------------------------ #
# Problem model (used ONLY for SOUND certificate / oracle checks):
#   Choosing x smashes all multiples of x. Gem i survives iff no chosen
#   x divides i  =>  the surviving set S must be DIVISOR-CLOSED (if i in S
#   then every divisor of i is in S), and every divisor-closed set is
#   achievable. Hence:
#       answer = max over divisor-closed subsets S of sum(a_i for i in S)
#   From this we derive only bounds / metamorphic relations / an
#   independent exponential brute force for small N. We never reimplement
#   an efficient solver on large N.
# ------------------------------------------------------------------ #

MAXV = 10 ** 9
EXTREMES = [-MAXV, -1, 0, 1, MAXV]


def build(N, a):
    return "{}\n{}\n".format(N, " ".join(str(x) for x in a))


def parse_answer(stdout):
    s = stdout.strip()
    assert s != "", "empty output"
    assert re.fullmatch(r"[+-]?\d+", s) is not None, "output is not a single integer: %r" % (stdout,)
    return int(s)


def certificate_lb(N, a):
    # Lower bounds from concrete achievable (divisor-closed) sets.
    best = 0                      # empty set: smash everything
    total = sum(a)               # full set: smash nothing
    if total > best:
        best = total
    for i in range(1, N + 1):     # principal down-set: divisors of i
        s = 0
        for d in range(1, i + 1):
            if i % d == 0:
                s += a[d - 1]
        if s > best:
            best = s
    return best


def upper_bound(N, a):
    # Any subset sum <= sum of positive entries.
    return sum(x for x in a if x > 0)


def brute(N, a):
    # Exact optimum by enumerating ALL subsets and keeping divisor-closed
    # ones. Independent exponential oracle; only used for small N.
    divmask = [0] * (N + 1)
    for i in range(1, N + 1):
        m = 0
        for d in range(1, i + 1):
            if i % d == 0:
                m |= 1 << (d - 1)
        divmask[i] = m
    best = 0
    for mask in range(1 << N):
        ok = True
        s = 0
        for i in range(1, N + 1):
            if mask & (1 << (i - 1)):
                if (mask & divmask[i]) != divmask[i]:
                    ok = False
                    break
                s += a[i - 1]
        if ok and s > best:
            best = s
    return best


def elem():
    return st.one_of(
        st.sampled_from(EXTREMES),
        st.integers(-3, 3),
        st.integers(-MAXV, MAXV),
    )


# ------------------------------------------------------------------ #
# Generators
# ------------------------------------------------------------------ #
@st.composite
def make_input(draw):
    # General generator: broad N with bias to edges + structured value modes.
    N = draw(st.one_of(
        st.sampled_from([1, 2, 3, 4, 5, 6, 10, 50, 99, 100]),
        st.integers(1, 100),
    ))
    mode = draw(st.integers(0, 6))
    if mode == 0:                                   # all-equal (any magnitude)
        v = draw(st.sampled_from(EXTREMES))
        a = [v] * N
    elif mode == 1:                                 # all extreme +-1e9
        a = [draw(st.sampled_from([-MAXV, MAXV])) for _ in range(N)]
    elif mode == 2:                                 # extremes + zeros mixed
        a = [draw(st.sampled_from([-MAXV, 0, MAXV])) for _ in range(N)]
    elif mode == 3:                                 # tiny bounded domain
        a = [draw(st.integers(-3, 3)) for _ in range(N)]
    elif mode == 4:                                 # extremes/tiny mixed
        a = [draw(st.sampled_from(EXTREMES)) for _ in range(N)]
    elif mode == 5:                                 # all non-positive (ans 0)
        a = [draw(st.integers(-MAXV, 0)) for _ in range(N)]
    else:                                           # uniform random
        a = [draw(st.integers(-MAXV, MAXV)) for _ in range(N)]
    return build(N, a)


@st.composite
def make_small(draw):
    # Small N -> exact brute force. Sweeps structured tiny domains AND
    # extreme magnitudes so magic-value guards cannot slip through.
    N = draw(st.integers(1, 12))
    mode = draw(st.integers(0, 4))
    if mode == 0:
        a = [draw(st.integers(-2, 2)) for _ in range(N)]
    elif mode == 1:
        a = [draw(st.sampled_from(EXTREMES)) for _ in range(N)]
    elif mode == 2:
        a = [draw(st.sampled_from([-MAXV, MAXV])) for _ in range(N)]
    elif mode == 3:
        v = draw(st.sampled_from(EXTREMES))
        a = [v] * N
    else:
        a = [draw(st.integers(-MAXV, MAXV)) for _ in range(N)]
    return (N, a)


@st.composite
def make_scale(draw):
    # Base kept small so c*base stays within +-1e9 (1000*1e6 == 1e9).
    N = draw(st.integers(1, 100))
    base = [draw(st.integers(-1000, 1000)) for _ in range(N)]
    c = draw(st.integers(1, 10 ** 6))
    return (build(N, base), build(N, [x * c for x in base]), c)


@st.composite
def make_mono(draw):
    N = draw(st.integers(1, 100))
    a = [draw(elem()) for _ in range(N)]
    i = draw(st.integers(0, N - 1))
    delta = draw(st.integers(0, MAXV - a[i]))   # keeps a[i]+delta <= 1e9
    b = list(a)
    b[i] += delta
    return (build(N, a), build(N, b), delta)


@st.composite
def make_append(draw):
    N = draw(st.integers(1, 99))
    a = [draw(elem()) for _ in range(N)]
    v = draw(elem())
    return (build(N, a), build(N + 1, a + [v]), v)


# ------------------------------------------------------------------ #
# Tests
# ------------------------------------------------------------------ #
@given(make_input())
@settings(max_examples=45, deadline=None)
def test_bounds(stdin):
    lines = stdin.splitlines()
    N = int(lines[0])
    a = list(map(int, lines[1].split())) if N > 0 else []
    ans = parse_answer(run_candidate(stdin))
    assert ans >= 0, "answer must be >= 0 (can always smash everything)"
    lb = certificate_lb(N, a)
    ub = upper_bound(N, a)
    assert ans >= lb, "answer %d below achievable lower bound %d" % (ans, lb)
    assert ans <= ub, "answer %d above sum-of-positives upper bound %d" % (ans, ub)


@given(make_small())
@settings(max_examples=60, deadline=None)
def test_brute_small(data):
    N, a = data
    ans = parse_answer(run_candidate(build(N, a)))
    exp = brute(N, a)
    assert ans == exp, "N=%d a=%s: got %d, exact optimum is %d" % (N, a, ans, exp)


@given(make_scale())
@settings(max_examples=15, deadline=None)
def test_scaling(data):
    s0, s1, c = data
    a0 = parse_answer(run_candidate(s0))
    a1 = parse_answer(run_candidate(s1))
    assert a1 == c * a0, "scaling by %d: expected %d, got %d" % (c, c * a0, a1)


@given(make_mono())
@settings(max_examples=15, deadline=None)
def test_monotone_increase(data):
    s0, s1, delta = data
    a0 = parse_answer(run_candidate(s0))
    a1 = parse_answer(run_candidate(s1))
    assert a0 <= a1, "increasing a value must not decrease the answer"
    assert a1 <= a0 + delta, "answer rose by more than the delta added"


@given(make_append())
@settings(max_examples=15, deadline=None)
def test_append_gem(data):
    s0, s1, v = data
    a0 = parse_answer(run_candidate(s0))
    a1 = parse_answer(run_candidate(s1))
    assert a1 >= a0, "appending a gem must not decrease the answer"
    if v <= 0:
        assert a1 == a0, "appending a non-positive gem must not change the answer"