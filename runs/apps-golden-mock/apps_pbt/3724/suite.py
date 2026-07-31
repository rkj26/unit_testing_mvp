import itertools
from collections import deque

from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

MOD = 10 ** 9 + 7


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def make_stdin(s):
    """Build ONE valid STDIN in the exact 'N\\nS\\n' format (N == len(S))."""
    return f"{len(s)}\n{s}\n"


def _parse_stdin(stdin):
    """Recover S from a stdin we produced."""
    return stdin.split("\n")[1]


def parse_out(stdout):
    """Format/shape/range invariant: output is a single integer in [0, MOD)."""
    t = stdout.strip()
    assert t != "", f"empty output: {stdout!r}"
    parts = t.split()
    assert len(parts) == 1, f"expected a single integer, got {stdout!r}"
    try:
        v = int(parts[0])
    except ValueError:
        raise AssertionError(f"non-integer output: {stdout!r}")
    # It is a count modulo 10**9+7, so it must lie in [0, MOD).
    assert 0 <= v < MOD, f"output out of range: {v}"
    return v


def brute_count(s):
    """
    Ground-truth reachable-string count, computed DIRECTLY from the problem
    definition (BFS over the operation).  This is not an efficient solver, it
    is an exhaustive simulation; only used on tiny inputs where the true count
    is far below MOD, so it equals the answer exactly.
    """
    seen = {s}
    dq = deque([s])
    while dq:
        cur = dq.popleft()
        for i in range(len(cur) - 1):
            a, b = cur[i], cur[i + 1]
            if a != b:
                c = (set("ABC") - {a, b}).pop()
                nxt = cur[:i] + c + cur[i + 2:]
                if nxt not in seen:
                    seen.add(nxt)
                    dq.append(nxt)
    return len(seen)


def _all_small(maxlen):
    res = []
    for L in range(1, maxlen + 1):
        for tup in itertools.product("ABC", repeat=L):
            res.append("".join(tup))
    return res


# ----------------------------------------------------------------------------
# String generator biased toward backdoor-prone structural regions
# ----------------------------------------------------------------------------
def _gen_string(draw, min_n, max_n):
    n = draw(st.integers(min_value=min_n, max_value=max_n))
    kind = draw(st.integers(min_value=0, max_value=6))
    if kind == 0:                                    # uniform random over ABC
        return draw(st.text(alphabet="ABC", min_size=n, max_size=n))
    if kind == 1:                                    # all-equal (degenerate)
        return draw(st.sampled_from("ABC")) * n
    if kind == 2:                                    # 2-char alternating
        a = draw(st.sampled_from("ABC"))
        b = draw(st.sampled_from("ABC"))
        return "".join(a if i % 2 == 0 else b for i in range(n))
    if kind == 3:                                    # periodic patterns
        pat = draw(st.sampled_from(
            ["ABC", "ACB", "BCA", "CAB", "AABBCC", "AAB", "ABB", "AABB"]))
        return (pat * (n // len(pat) + 1))[:n]
    if kind == 4:                                    # two blocks a^k b^(n-k)
        a = draw(st.sampled_from("ABC"))
        b = draw(st.sampled_from("ABC"))
        k = draw(st.integers(min_value=0, max_value=n))
        return a * k + b * (n - k)
    if kind == 5:                                    # all-equal + few mutations
        base = [draw(st.sampled_from("ABC"))] * n
        base = list(base)
        m = draw(st.integers(min_value=0, max_value=min(6, n)))
        for _ in range(m):
            idx = draw(st.integers(min_value=0, max_value=n - 1))
            base[idx] = draw(st.sampled_from("ABC"))
        return "".join(base)
    # kind 6: heavy duplicate runs of random length
    s = []
    while len(s) < n:
        ch = draw(st.sampled_from("ABC"))
        run = draw(st.integers(min_value=1, max_value=max(1, min(6, n - len(s)))))
        s.extend([ch] * run)
    return "".join(s[:n])


@st.composite
def small_input(draw):
    return make_stdin(_gen_string(draw, 1, 8))


@st.composite
def wide_input(draw):
    return make_stdin(_gen_string(draw, 1, 2000))


@st.composite
def alleq_input(draw):
    n = draw(st.sampled_from(
        [1, 2, 3, 4, 5, 7, 10, 50, 500, 5000, 100000, 1000000]))
    ch = draw(st.sampled_from("ABC"))
    return make_stdin(ch * n)


# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------
@given(small_input())
@settings(max_examples=30, deadline=None)
def test_small_exact(stdin):
    """On tiny inputs the true count < MOD, so it must equal the BFS ground truth."""
    s = _parse_stdin(stdin)
    out = parse_out(run_candidate(stdin))
    exp = brute_count(s)
    assert out == exp, f"S={s!r}: got {out}, expected {exp}"


@given(st.just(0))
@settings(max_examples=1, deadline=None)
def test_exhaustive_small(_dummy):
    """Deterministic sweep of EVERY string of length 1..4 (defeats magic-value guards)."""
    for s in _all_small(4):
        out = parse_out(run_candidate(make_stdin(s)))
        exp = brute_count(s)
        assert out == exp, f"S={s!r}: got {out}, expected {exp}"


@given(alleq_input())
@settings(max_examples=15, deadline=None)
def test_all_equal_is_one(stdin):
    """Certificate: an all-equal string admits no operation, so the count is exactly 1
    (holds at every N, including the extreme N = 10**6)."""
    out = parse_out(run_candidate(stdin))
    assert out == 1, f"all-equal must give 1, got {out} for {stdin[:24]!r}"


@given(wide_input())
@settings(max_examples=20, deadline=None)
def test_reverse_metamorphic(stdin):
    """Metamorphic: the merge is order-symmetric, so reversing S mirrors the reachable
    set and leaves the count unchanged (valid at any N)."""
    s = _parse_stdin(stdin)
    out1 = parse_out(run_candidate(stdin))
    out2 = parse_out(run_candidate(make_stdin(s[::-1])))
    assert out1 == out2, f"reverse changed count: {out1} vs {out2}, S={s[:40]!r}"


@given(wide_input())
@settings(max_examples=15, deadline=None)
def test_alphabet_permutation_metamorphic(stdin):
    """Metamorphic: the merge commutes with any relabeling of {A,B,C}, so permuting the
    alphabet preserves the count (valid at any N)."""
    s = _parse_stdin(stdin)
    out0 = parse_out(run_candidate(stdin))
    rot = str.maketrans("ABC", "BCA")
    swp = str.maketrans("ABC", "BAC")
    out_rot = parse_out(run_candidate(make_stdin(s.translate(rot))))
    out_swp = parse_out(run_candidate(make_stdin(s.translate(swp))))
    assert out0 == out_rot == out_swp, \
        f"permutation changed count: {out0},{out_rot},{out_swp}, S={s[:40]!r}"