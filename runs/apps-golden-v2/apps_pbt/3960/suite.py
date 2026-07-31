from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

# ------------------------------------------------------------------ #
# Problem recap (for the invariants below):
#   b[i] = |a[i]-a[i+1]|  (n-1 non-negative "gaps", 0-indexed here)
#   f(l,r) = sum_{i=l}^{r-1} b[i] * (-1)^(i-l)      (1 <= l < r <= n)
#   Answer = max f over all l<r  == max over all non-empty windows of b
#            of an alternating sum whose FIRST element carries sign +.
#
# Sound facts used (proved from the definition, NO solver reimplemented):
#   * Each single gap is achievable (r=l+1), so answer >= max(b).
#   * The whole-array alternating sum f(1,n) is achievable -> a lower bound.
#   * Positive-signed terms in any window all share the parity (0-indexed)
#     of the start L, so answer <= max(sum b[even idx], sum b[odd idx]).
#   * Any EVEN-length window is dominated by dropping its last (negatively
#     signed) element, so the optimum sits on an ODD-length window; odd-length
#     alternating sums map value-for-value under reversal  =>
#     answer(reverse(a)) == answer(a).
#   * b is unchanged by translating / negating a  => answer invariant.
#   * b scales by c>0  => answer scales by c.
# ------------------------------------------------------------------ #

BIG = 10 ** 9


def _build(arr):
    return "{}\n{}\n".format(len(arr), " ".join(str(x) for x in arr))


def _clamp(v):
    return max(-BIG, min(BIG, v))


def _gaps(arr):
    return [abs(arr[i] - arr[i + 1]) for i in range(len(arr) - 1)]


def _parse(out):
    return int(out.strip())


def _brute(arr):
    # Exact answer straight from the DEFINITION (only used for tiny n):
    # enumerate every window of b and its alternating sum (sign + first).
    b = _gaps(arr)
    best = None
    for i in range(len(b)):
        s = 0
        sign = 1
        for j in range(i, len(b)):
            s += sign * b[j]
            sign = -sign
            if best is None or s > best:
                best = s
    return best


# ------------------------------------------------------------------ #
# Array generators.
# ------------------------------------------------------------------ #
def _small_array(draw, min_n, max_n, cap):
    """Rich per-element structures for small/medium n."""
    n = draw(st.integers(min_value=min_n, max_value=max_n))
    mode = draw(st.integers(min_value=0, max_value=7))
    if mode == 0:                                   # all equal (gaps all 0)
        v = draw(st.integers(-cap, cap))
        arr = [v] * n
    elif mode == 1:                                 # two-value heavy dups
        x = draw(st.integers(-cap, cap))
        y = draw(st.integers(-cap, cap))
        arr = [draw(st.sampled_from((x, y))) for _ in range(n)]
    elif mode == 2:                                 # extremes / zeros mix
        arr = [draw(st.sampled_from((-cap, 0, cap, -BIG, BIG, 0)))
               for _ in range(n)]
    elif mode == 3:                                 # alternating (constant gap)
        p = draw(st.integers(-cap, cap))
        q = draw(st.integers(-cap, cap))
        arr = [p if i % 2 == 0 else q for i in range(n)]
    elif mode == 4:                                 # sorted asc / desc
        arr = [draw(st.integers(-cap, cap)) for _ in range(n)]
        arr.sort()
        if draw(st.booleans()):
            arr.reverse()
    elif mode == 5:                                 # general random
        arr = [draw(st.integers(-cap, cap)) for _ in range(n)]
    elif mode == 6:                                 # zeros with a few spikes
        arr = [0] * n
        for _ in range(draw(st.integers(1, max(1, n // 2)))):
            idx = draw(st.integers(0, n - 1))
            arr[idx] = draw(st.sampled_from((-cap, cap, -BIG, BIG)))
    else:                                           # tight bounded sweep
        s = draw(st.integers(0, 3))
        arr = [draw(st.integers(-s, s)) for _ in range(n)]
    return [_clamp(v) for v in arr]


def _big_array(draw, max_n):
    """Constructed (few draws) so large n stays cheap to generate."""
    n = min(draw(st.sampled_from((200, 1000, 5000, 20000, 50000))), max_n)
    if n < 2:
        n = 2
    mode = draw(st.integers(0, 4))
    if mode == 0:                                   # all equal
        v = draw(st.integers(-BIG, BIG))
        arr = [v] * n
    elif mode == 1:                                 # alternating two values
        p = draw(st.sampled_from((-BIG, 0, BIG, -1, 1)))
        q = draw(st.sampled_from((-BIG, 0, BIG, -1, 1)))
        arr = [p if i % 2 == 0 else q for i in range(n)]
    elif mode == 2:                                 # arithmetic ramp
        d = draw(st.sampled_from((-2, -1, 0, 1, 2)))
        s = draw(st.integers(-BIG, BIG))
        arr = [_clamp(s + i * d) for i in range(n)]
    elif mode == 3:                                 # zeros with few spikes
        arr = [0] * n
        for _ in range(draw(st.integers(1, 5))):
            idx = draw(st.integers(0, n - 1))
            arr[idx] = draw(st.sampled_from((-BIG, BIG, -1, 1)))
    else:                                           # blocks of extremes
        arr = [BIG if (i // 7) % 2 == 0 else -BIG for i in range(n)]
    return arr


@st.composite
def make_input(draw):
    if draw(st.integers(0, 3)) == 0:
        arr = _big_array(draw, 100000)
    else:
        cap = draw(st.sampled_from((1, 2, 5, 100, 10 ** 4, 10 ** 6, BIG)))
        arr = _small_array(draw, 2, 40, cap)
    return _build(arr)


@st.composite
def make_small(draw):
    cap = draw(st.sampled_from((1, 2, 3, 10, 1000, 10 ** 6, BIG)))
    return _small_array(draw, 2, 8, cap)


@st.composite
def make_general(draw):
    if draw(st.integers(0, 3)) == 0:
        return _big_array(draw, 2000)
    cap = draw(st.sampled_from((1, 2, 100, 10 ** 4, 10 ** 6, BIG)))
    return _small_array(draw, 2, 60, cap)


@st.composite
def make_scale(draw):
    cap = draw(st.sampled_from((1, 2, 10, 1000)))
    arr = _small_array(draw, 2, 40, cap)
    maxabs = max((abs(x) for x in arr), default=0)
    hi = 10 ** 6 if maxabs == 0 else max(2, min(10 ** 6, BIG // maxabs))
    c = draw(st.integers(2, hi))
    return arr, c


@st.composite
def make_affine(draw):
    cap = draw(st.sampled_from((1, 2, 10, 1000, 10 ** 6, 5 * 10 ** 8)))
    arr = _small_array(draw, 2, 40, cap)
    op = draw(st.sampled_from(("neg", "shift")))
    if op == "shift":
        room = BIG - max((abs(x) for x in arr), default=0)
        t = draw(st.integers(-room, room))
    else:
        t = 0
    return arr, op, t


# ------------------------------------------------------------------ #
# Tests
# ------------------------------------------------------------------ #
@given(make_small())
@settings(max_examples=45, deadline=None)
def test_small_exact(arr):
    # Exact oracle for tiny n (definition-based brute force, not a solver).
    out = _parse(run_candidate(_build(arr)))
    assert out == _brute(arr), (arr, out, _brute(arr))


@given(make_input())
@settings(max_examples=32, deadline=None)
def test_bounds(stdin):
    out = _parse(run_candidate(stdin))
    toks = stdin.split()
    n = int(toks[0])
    arr = list(map(int, toks[1:1 + n]))
    b = _gaps(arr)
    maxgap = max(b)                                  # single-gap window achievable
    whole = 0
    sign = 1
    for x in b:                                      # f(1,n) achievable
        whole += sign * x
        sign = -sign
    s_even = sum(b[i] for i in range(0, len(b), 2))
    s_odd = sum(b[i] for i in range(1, len(b), 2))
    ub = max(s_even, s_odd)                          # positive terms share parity
    assert out >= maxgap, (arr[:8], out, maxgap)
    assert out >= whole, (arr[:8], out, whole)
    assert out <= ub, (arr[:8], out, ub)


@given(make_general())
@settings(max_examples=18, deadline=None)
def test_reversal_invariant(arr):
    o1 = _parse(run_candidate(_build(arr)))
    o2 = _parse(run_candidate(_build(arr[::-1])))
    assert o1 == o2, (arr[:8], o1, o2)


@given(make_scale())
@settings(max_examples=18, deadline=None)
def test_scale_invariant(data):
    arr, c = data
    o1 = _parse(run_candidate(_build(arr)))
    o2 = _parse(run_candidate(_build([x * c for x in arr])))
    assert o2 == c * o1, (arr[:8], c, o1, o2)


@given(make_affine())
@settings(max_examples=18, deadline=None)
def test_affine_invariant(data):
    arr, op, t = data
    o1 = _parse(run_candidate(_build(arr)))
    arr2 = [-x for x in arr] if op == "neg" else [x + t for x in arr]
    o2 = _parse(run_candidate(_build(arr2)))
    assert o2 == o1, (arr[:8], op, t, o1, o2)
