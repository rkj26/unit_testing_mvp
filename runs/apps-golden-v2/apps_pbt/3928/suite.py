from hypothesis import given, strategies as st, settings
from harness import run_candidate  # run_candidate(stdin: str) -> stdout: str

LETTERS = "abcdefghijklmnopqrstuvwxyz"


# ---------------------------------------------------------------------------
# Helpers (parsing + provable, input-derived bounds -- NO solving of the DP)
# ---------------------------------------------------------------------------
def _parse(stdin):
    lines = stdin.split("\n")
    n, a, b = (int(x) for x in lines[0].split())
    s = lines[1]
    return n, a, b, s


def _fmt(n, a, b, s):
    return "%d %d %d\n%s\n" % (n, a, b, s)


def _get_answer(stdin):
    out = run_candidate(stdin)
    toks = out.split()
    assert len(toks) == 1, "output must be a single integer, got %r" % (out,)
    return int(toks[0])


def _check_bounds(n, a, b, s, val):
    # d = number of DISTINCT characters. The first occurrence of every distinct
    # character can ONLY be encoded by the single-char rule (cost a): a substring
    # piece would require the character to have appeared earlier, contradicting
    # "first occurrence". Hence there are at least d single-char pieces.
    #   lower bound: d*a, and if n>d at least one MORE piece exists (cost >= min(a,b))
    #   upper bound: encode each first occurrence as a single char (d*a) and every
    #                other character as a length-1 piece, choosing the cheaper of a
    #                (single) or b (it already appeared, so it is a valid substring).
    d = len(set(s))
    lo = d * a + (min(a, b) if n > d else 0)
    hi = d * a + (n - d) * min(a, b)
    assert val >= 1, "answer must be positive, got %d" % (val,)
    assert lo <= val, "answer %d below provable lower bound %d (n=%d,a=%d,b=%d,d=%d)" % (
        val, lo, n, a, b, d)
    assert val <= hi, "answer %d above provable upper bound %d (n=%d,a=%d,b=%d,d=%d)" % (
        val, hi, n, a, b, d)


# ---------------------------------------------------------------------------
# String generators biased toward structural edges
# ---------------------------------------------------------------------------
@st.composite
def _gen_string(draw, n):
    mode = draw(st.integers(0, 4))
    if mode == 0:  # all-equal (max duplication -> substring-heavy DP)
        return draw(st.sampled_from(LETTERS)) * n
    if mode == 1 and n <= 26:  # all-distinct (forces every piece to be single)
        chars = draw(st.lists(st.sampled_from(list(LETTERS)),
                              min_size=n, max_size=n, unique=True))
        return "".join(chars)
    if mode == 2:  # small alphabet, heavy repeats
        k = draw(st.integers(2, 4))
        alpha = draw(st.lists(st.sampled_from(list(LETTERS)),
                              min_size=k, max_size=k, unique=True))
        return draw(st.text(alphabet="".join(alpha), min_size=n, max_size=n))
    if mode == 3 and n >= 2:  # periodic
        p = draw(st.integers(2, min(5, n)))
        k = draw(st.integers(1, min(4, p)))
        alpha = draw(st.lists(st.sampled_from(list(LETTERS)),
                              min_size=k, max_size=k, unique=True))
        base = draw(st.text(alphabet="".join(alpha), min_size=p, max_size=p))
        return (base * (n // p + 1))[:n]
    return draw(st.text(alphabet=LETTERS, min_size=n, max_size=n))


@st.composite
def _gen_costs(draw, hi=5000):
    # a: pinned extremes mixed with uniform
    a = draw(st.one_of(st.sampled_from([1, 2, 3, hi, hi - 1, hi // 2]),
                       st.integers(1, hi)))
    a = max(1, min(hi, a))
    # b: deliberately hit the a-vs-b and 2a thresholds (strict-vs-inclusive bugs)
    m = draw(st.integers(0, 2))
    if m == 0:
        b = a + draw(st.sampled_from([-1, 0, 1]))
    elif m == 1:
        b = 2 * a + draw(st.sampled_from([-1, 0, 1]))
    else:
        b = draw(st.one_of(st.sampled_from([1, 2, hi, hi - 1]),
                           st.integers(1, hi)))
    b = max(1, min(hi, b))
    return a, b


@st.composite
def make_input(draw):
    n = draw(st.one_of(st.sampled_from([1, 2, 3, 26, 27, 50]),
                       st.integers(1, 120)))
    a, b = draw(_gen_costs())
    s = draw(_gen_string(n))
    return _fmt(n, a, b, s)


@st.composite
def make_input_small(draw):
    # smaller n and moderate costs so metamorphic transforms stay in-bounds
    n = draw(st.one_of(st.sampled_from([1, 2, 3, 8]),
                       st.integers(1, 40)))
    a, b = draw(_gen_costs(hi=2000))
    s = draw(_gen_string(n))
    return _fmt(n, a, b, s)


# ---------------------------------------------------------------------------
# Deterministic sweep over hand-crafted threshold / degenerate corners
# ---------------------------------------------------------------------------
def _build_cases():
    cases = []

    def add(n, a, b, s):
        assert len(s) == n
        cases.append(_fmt(n, a, b, s))

    # n == 1 (minimum size), extreme costs
    for a, b in [(1, 1), (5000, 1), (1, 5000), (5000, 5000), (2500, 2500)]:
        add(1, a, b, "a")
    # all-equal, sweep b around a=4 (a-1,a,a+1) and around 2a=8 (2a-1,2a,2a+1)
    for b in [1, 3, 4, 5, 7, 8, 9, 5000]:
        add(6, 4, b, "a" * 6)
    add(6, 1, 5000, "a" * 6); add(6, 5000, 1, "a" * 6); add(6, 1, 1, "a" * 6)
    # all-distinct (answer forced to n*a)
    add(4, 1, 1, "abcd"); add(4, 10, 1, "abcd"); add(5, 3, 1, "abcde")
    add(26, 5000, 1, LETTERS); add(26, 1, 5000, LETTERS); add(26, 1, 1, LETTERS)
    # periodic / structured
    add(8, 3, 1, "ab" * 4); add(9, 3, 1, "abc" * 3); add(12, 5, 2, "abc" * 4)
    add(6, 3, 1, "aabbcc"); add(6, 3, 2, "aabbcc"); add(7, 3, 2, "abcabca")
    # all-equal length 10, extreme + threshold costs
    for a, b in [(5000, 1), (1, 5000), (3, 2), (2, 3), (1, 1)]:
        add(10, a, b, "a" * 10)
    # provided examples
    add(3, 3, 1, "aba"); add(4, 1, 1, "abcd"); add(4, 10, 1, "aaaa")
    # slightly larger repetitive
    add(50, 7, 3, "a" * 50); add(40, 3, 7, "a" * 40)
    add(10, 2, 1, "aabbaabbaa"); add(12, 4, 3, "aabb" * 3)
    return cases


_CASES = _build_cases()


@st.composite
def make_edge_input(draw):
    return draw(st.sampled_from(_CASES))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@given(make_input())
@settings(max_examples=50, deadline=None)
def test_bounds(stdin):
    n, a, b, s = _parse(stdin)
    val = _get_answer(stdin)
    _check_bounds(n, a, b, s, val)


@given(make_edge_input())
@settings(max_examples=70, deadline=None)
def test_edge_sweep(stdin):
    n, a, b, s = _parse(stdin)
    val = _get_answer(stdin)
    _check_bounds(n, a, b, s, val)
    if n == 1:
        assert val == a, "n=1 must cost exactly a=%d, got %d" % (a, val)


@given(make_input_small())
@settings(max_examples=15, deadline=None)
def test_relabel_invariant(stdin):
    # Applying a bijection on the alphabet preserves the equality pattern of the
    # string, hence every substring relationship and the optimal cost are unchanged.
    n, a, b, s = _parse(stdin)
    base = _get_answer(stdin)
    _check_bounds(n, a, b, s, base)
    rev = "".join(chr(219 - ord(c)) for c in s)          # z<->a mirror
    rot = "".join(chr((ord(c) - 97 + 13) % 26 + 97) for c in s)  # rot13
    a1 = _get_answer(_fmt(n, a, b, rev))
    a2 = _get_answer(_fmt(n, a, b, rot))
    assert base == a1, "alphabet relabeling changed cost: %d vs %d" % (base, a1)
    assert base == a2, "alphabet relabeling changed cost: %d vs %d" % (base, a2)


@given(make_input_small())
@settings(max_examples=18, deadline=None)
def test_scaling(stdin):
    # Every valid decomposition's cost scales linearly with (a,b); the argmin is
    # invariant to positive scaling, so the optimum scales by the same factor.
    n, a, b, s = _parse(stdin)
    base = _get_answer(stdin)
    _check_bounds(n, a, b, s, base)
    c = min(2, 5000 // max(a, b))
    if c >= 2:
        scaled = _get_answer(_fmt(n, a * c, b * c, s))
        assert scaled == c * base, "cost not linear in (a,b): %d != %d*%d" % (
            scaled, c, base)


@given(make_input_small())
@settings(max_examples=15, deadline=None)
def test_monotonic(stdin):
    # The optimal cost is non-decreasing in a and in b (raising a unit cost cannot
    # make any fixed decomposition cheaper, so the min cannot drop).
    n, a, b, s = _parse(stdin)
    base = _get_answer(stdin)
    _check_bounds(n, a, b, s, base)
    a2 = min(5000, a + 9)
    b2 = min(5000, b + 9)
    if a2 > a:
        up_a = _get_answer(_fmt(n, a2, b, s))
        assert up_a >= base, "answer must be non-decreasing in a: %d < %d" % (up_a, base)
    if b2 > b:
        up_b = _get_answer(_fmt(n, a, b2, s))
        assert up_b >= base, "answer must be non-decreasing in b: %d < %d" % (up_b, base)
