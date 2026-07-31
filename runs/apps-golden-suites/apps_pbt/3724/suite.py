from hypothesis import given, strategies as st, settings
from harness import run_candidate

MOD = 10 ** 9 + 7


def _run_int(stdin):
    out = run_candidate(stdin).strip()
    assert out != "", "candidate produced empty output"
    try:
        val = int(out)
    except ValueError:
        raise AssertionError("output is not a single integer: %r" % out)
    return val


def _parse(stdin):
    parts = stdin.split("\n")
    n = int(parts[0])
    s = parts[1]
    return n, s


def _build(n, s):
    return "%d\n%s\n" % (n, s)


@st.composite
def make_input(draw):
    # Explore boundary size (1), tiny, small and moderate sizes.
    n = draw(st.one_of(
        st.just(1),
        st.integers(min_value=1, max_value=8),
        st.integers(min_value=1, max_value=60),
        st.integers(min_value=2, max_value=500),
    ))
    # Bias toward the full alphabet, but also hit single-letter (all-equal,
    # degenerate) and two-letter sub-alphabets to force duplicates / structure.
    sub = draw(st.sampled_from(["A", "AB", "BC", "CA", "ABC", "ABC", "ABC"]))
    s = draw(st.text(alphabet=sub, min_size=n, max_size=n))
    return _build(n, s)


@given(make_input())
@settings(max_examples=50, deadline=None)
def test_format_and_range(stdin):
    # The answer is a count taken modulo 1e9+7: a single integer in [0, MOD).
    val = _run_int(stdin)
    assert 0 <= val < MOD, "answer out of [0, MOD): %d" % val


@given(make_input())
@settings(max_examples=50, deadline=None)
def test_small_bounds_and_degenerate(stdin):
    n, s = _parse(stdin)
    val = _run_int(stdin)
    # An all-equal string admits no operation (needs S_i != S_{i+1}), so the
    # ONLY reachable string is S itself: the count is exactly 1 (any length).
    if len(set(s)) <= 1:
        assert val == 1, "all-equal string must give exactly 1, got %d" % val
    if n <= 15:
        # For n <= 15 the true count is < MOD, so the printed value equals it.
        # Reachable strings all have length in [1, n]; there are only
        # sum_{L=1..n} 3^L = (3^(n+1)-3)/2 such strings in total.
        ub = (3 ** (n + 1) - 3) // 2
        assert 1 <= val <= ub, "count %d outside [1, %d] for n=%d" % (val, ub, n)
        if n >= 2 and len(set(s)) >= 2:
            # Some adjacent pair differs -> one operation yields a strictly
            # shorter (hence distinct) string, so at least 2 strings exist.
            assert val >= 2, "non-constant string must give >= 2, got %d" % val


@given(make_input())
@settings(max_examples=50, deadline=None)
def test_reversal_invariant(stdin):
    # Each operation on reverse(S) mirrors exactly one operation on S (the
    # "replace-left / delete-right" rule maps to the reversed position), giving
    # a bijection between reachable sets -> the counts are equal.
    n, s = _parse(stdin)
    a = _run_int(stdin)
    b = _run_int(_build(n, s[::-1]))
    assert a == b, "reversal changed the count: %d vs %d" % (a, b)


@given(make_input())
@settings(max_examples=50, deadline=None)
def test_relabel_invariant(stdin):
    # The "third distinct character" rule commutes with any permutation of the
    # alphabet {A,B,C}, so relabeling every character is a bijection on
    # reachable sets -> the counts are equal. Check a 3-cycle and a swap.
    n, s = _parse(stdin)
    a = _run_int(stdin)
    cyc = s.translate(str.maketrans("ABC", "BCA"))
    swp = s.translate(str.maketrans("ABC", "BAC"))
    b = _run_int(_build(n, cyc))
    c = _run_int(_build(n, swp))
    assert a == b == c, "alphabet relabeling changed count: %d, %d, %d" % (a, b, c)
