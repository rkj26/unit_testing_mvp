from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

# Problem 3955: n numbers, at most k operations, each op multiplies one number by x.
# Maximize the bitwise OR of the sequence.  n<=200000, 1<=k<=10, 2<=x<=8, 0<=a_i<=1e9.
#
# Sound facts used below (never recompute the optimum):
#   * Doing fewer/no ops is allowed ("at most k"), so answer >= OR of the untouched array.
#   * For any single element i, applying ALL k ops to it is a valid config; its OR is
#     (OR of the other elements) | (a_i * x^k).  Every such value is ACHIEVABLE, so the
#     true optimum is >= the max of these certificates.
#   * The OR of any multiset is <= its sum, and the max attainable sum under a budget of k
#     multiply-by-x ops is sum(a) + max(a)*(x^k - 1) (concentrate all ops on the max element,
#     provable since the per-element gain is convex).  So answer <= sum(a) + max(a)*(x^k-1).
#   * Order-invariance: answer depends only on the multiset of values.
#   * Monotone in budget: more ops can never lower the optimum.
#   * Scaling every value by 2 shifts all bits up by one, doubling the optimum.
#   * A zero element contributes nothing and cannot usefully consume ops, so appending 0
#     leaves the optimum unchanged.

MAXV = 10 ** 9


def fmt(n, k, x, a):
    return "%d %d %d\n%s\n" % (n, k, x, " ".join(map(str, a)))


def parse_stdin(s):
    parts = s.split()
    n = int(parts[0]); k = int(parts[1]); x = int(parts[2])
    a = list(map(int, parts[3:3 + n]))
    return n, k, x, a


def out_int(stdout):
    toks = stdout.split()
    assert len(toks) == 1, "expected a single integer on stdout, got %r" % (stdout,)
    return int(toks[0])


@st.composite
def gen(draw, vmax=MAXV, nmax=1500, kmax=10, big=False):
    # k and x: sweep boundaries {1,kmax} and {2,8} plus the full small domains.
    k = draw(st.one_of(st.sampled_from([1, kmax]),
                       st.integers(min_value=1, max_value=kmax)))
    x = draw(st.one_of(st.sampled_from([2, 8]),
                       st.integers(min_value=2, max_value=8)))

    modes = ["rand", "extreme", "alleq", "allzero", "single", "powers", "small"]
    if big:
        modes = modes + ["maxn"]
    mode = draw(st.sampled_from(modes))

    if mode == "single":
        n = 1
    elif mode == "maxn":
        n = draw(st.sampled_from([20000, 100000, 200000]))
    else:
        n = draw(st.one_of(st.sampled_from([1, 2, 3]),
                           st.integers(min_value=1, max_value=100),
                           st.integers(min_value=1, max_value=nmax)))

    if mode == "allzero":
        a = [0] * n
    elif mode == "maxn":
        # cheap large array: a two-value pattern mixing extremes / zeros.
        v = draw(st.sampled_from([0, 1, 2, 3, vmax, vmax // 2]))
        w = draw(st.sampled_from([0, 1, vmax, vmax - 1]))
        a = [v if (i & 1) == 0 else w for i in range(n)]
    elif mode == "alleq":
        v = draw(st.one_of(st.just(0), st.just(1), st.just(vmax),
                           st.integers(min_value=0, max_value=vmax)))
        a = [v] * n
    elif mode == "extreme":
        a = draw(st.lists(st.sampled_from([0, 1, 2, vmax, vmax - 1, vmax // 2, vmax // 3]),
                          min_size=n, max_size=n))
    elif mode == "powers":
        pw = [p for p in ([0, 1] + [1 << b for b in range(0, 30)]) if p <= vmax]
        a = draw(st.lists(st.sampled_from(pw), min_size=n, max_size=n))
    elif mode == "small":
        a = draw(st.lists(st.integers(min_value=0, max_value=64),
                          min_size=n, max_size=n))
    else:  # rand: uniform, plus injected extremes/zeros
        a = draw(st.lists(st.one_of(st.integers(min_value=0, max_value=vmax),
                                    st.just(0), st.just(vmax),
                                    st.integers(min_value=0, max_value=1000)),
                          min_size=n, max_size=n))
    return fmt(n, k, x, a)


@given(gen(big=True))
@settings(max_examples=45, deadline=None)
def test_bounds(stdin):
    n, k, x, a = parse_stdin(stdin)
    val = out_int(run_candidate(stdin))
    assert val >= 0, "OR must be non-negative"

    xk = x ** k

    # Lower bound 1: doing nothing is allowed.
    or0 = 0
    for v in a:
        or0 |= v
    assert val >= or0, "output %d below zero-op OR %d" % (val, or0)

    # Lower bound 2: best "all k ops on a single element" certificate (achievable).
    prefix = [0] * (n + 1)
    for i in range(n):
        prefix[i + 1] = prefix[i] | a[i]
    suffix = [0] * (n + 1)
    for i in range(n - 1, -1, -1):
        suffix[i] = suffix[i + 1] | a[i]
    lower = 0
    for i in range(n):
        cand = prefix[i] | (a[i] * xk) | suffix[i + 1]
        if cand > lower:
            lower = cand
    assert val >= lower, "output %d below an achievable OR %d" % (val, lower)

    # Upper bound: OR <= sum <= max attainable sum under the op budget.
    upper = sum(a) + max(a) * (xk - 1)
    assert val <= upper, "output %d exceeds sum upper bound %d" % (val, upper)


@given(gen(nmax=300))
@settings(max_examples=18, deadline=None)
def test_order_invariant(stdin):
    n, k, x, a = parse_stdin(stdin)
    base = out_int(run_candidate(stdin))
    rev = out_int(run_candidate(fmt(n, k, x, list(reversed(a)))))
    assert rev == base, "answer changed under reversal: %d vs %d" % (rev, base)
    srt = out_int(run_candidate(fmt(n, k, x, sorted(a))))
    assert srt == base, "answer changed under sorting: %d vs %d" % (srt, base)


@given(gen(kmax=9, nmax=300))
@settings(max_examples=22, deadline=None)
def test_monotone_in_k(stdin):
    n, k, x, a = parse_stdin(stdin)
    v_k = out_int(run_candidate(stdin))
    v_k1 = out_int(run_candidate(fmt(n, k + 1, x, a)))
    assert v_k1 >= v_k, "extra op lowered the answer: k=%d->%d, k+1->%d" % (k, v_k, v_k1)


@given(gen(vmax=MAXV // 2, nmax=200))
@settings(max_examples=22, deadline=None)
def test_scale_by_two(stdin):
    n, k, x, a = parse_stdin(stdin)
    v1 = out_int(run_candidate(stdin))
    a2 = [v * 2 for v in a]
    v2 = out_int(run_candidate(fmt(n, k, x, a2)))
    assert v2 == 2 * v1, "doubling inputs did not double answer: %d vs %d" % (v2, 2 * v1)


@given(gen(nmax=300))
@settings(max_examples=22, deadline=None)
def test_append_zero(stdin):
    n, k, x, a = parse_stdin(stdin)
    v1 = out_int(run_candidate(stdin))
    v2 = out_int(run_candidate(fmt(n + 1, k, x, a + [0])))
    assert v2 == v1, "appending a zero changed the answer: %d vs %d" % (v2, v1)
