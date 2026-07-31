import itertools
import random

from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str


# ---------------------------------------------------------------------------
# Problem-defined operator: mex(x, y) = smallest non-negative integer not in
# {x, y}, for x, y in {0, 1, 2}.  This reproduces EXACTLY the table given in
# the statement:
#     y=0 y=1 y=2
# x=0  1   2   1
# x=1  2   0   0
# x=2  1   0   0
# ---------------------------------------------------------------------------
def mex(x, y):
    if x != 0 and y != 0:
        return 0
    if x != 1 and y != 1:
        return 1
    return 2


def build_stdin(N, row, col_rest):
    # row       : a_{1,1..N}      (length N, printed on one whitespace line)
    # col_rest  : a_{2,1..N,1}    (length N-1, one per line; a_{1,1}==row[0])
    parts = [str(N), ' '.join(str(v) for v in row)]
    parts.extend(str(v) for v in col_rest)
    return '\n'.join(parts) + '\n'


def parse_stdin(stdin):
    toks = stdin.split()
    N = int(toks[0])
    row = [int(t) for t in toks[1:1 + N]]
    col_rest = [int(t) for t in toks[1 + N:1 + N + (N - 1)]]
    return N, row, col_rest


def parse_out(stdout):
    toks = stdout.split()
    assert len(toks) == 3, "output must be exactly 3 integers, got: %r" % (stdout,)
    return [int(t) for t in toks]


def brute_counts(N, row, col_rest):
    # Directly applies the defining recurrence cell-by-cell (O(N^2)); only
    # used on SMALL N, so it is a faithful, unambiguous reference.
    col = [row[0]] + col_rest            # a_{i,1} for i = 1..N
    c = [0, 0, 0]
    prev = list(row)                     # row i = 1
    for v in prev:
        c[v] += 1
    for i in range(1, N):
        cur = [0] * N
        cur[0] = col[i]
        for j in range(1, N):
            cur[j] = mex(prev[j], cur[j - 1])
        for v in cur:
            c[v] += 1
        prev = cur
    return c


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------
@st.composite
def gen_border(draw, min_n=1, max_n=120):
    """Small/medium borders biased toward structural edge patterns."""
    N = draw(st.integers(min_value=min_n, max_value=max_n))
    mode = draw(st.sampled_from(
        ['rand', 'all0', 'all1', 'all2', 'same', 'alt', 'sparse']))

    def vals(k):
        if k == 0:
            return []
        if mode == 'all0':
            return [0] * k
        if mode == 'all1':
            return [1] * k
        if mode == 'all2':
            return [2] * k
        if mode == 'same':
            v = draw(st.integers(0, 2))
            return [v] * k
        if mode == 'alt':
            a = draw(st.integers(0, 2))
            b = draw(st.integers(0, 2))
            return [a if t % 2 == 0 else b for t in range(k)]
        if mode == 'sparse':
            base = draw(st.integers(0, 2))
            lst = [base] * k
            for _ in range(draw(st.integers(0, min(k, 4)))):
                lst[draw(st.integers(0, k - 1))] = draw(st.integers(0, 2))
            return lst
        return draw(st.lists(st.integers(0, 2), min_size=k, max_size=k))

    return N, vals(N), vals(N - 1)


@st.composite
def make_input_small(draw):
    N, row, col_rest = draw(gen_border(min_n=1, max_n=120))
    return build_stdin(N, row, col_rest)


# Deterministic enumeration of the whole tiny domain (N in {1,2,3}); this is
# the region a magic-value guard would hide in.
TINY = []
for _N in (1, 2, 3):
    for _row in itertools.product((0, 1, 2), repeat=_N):
        for _col in itertools.product((0, 1, 2), repeat=_N - 1):
            TINY.append((_N, list(_row), list(_col)))


@st.composite
def make_input_tiny(draw):
    N, row, col_rest = draw(st.sampled_from(TINY))
    return build_stdin(N, row, col_rest)


def gen_by_mode(N, mode, rnd):
    if mode in ('all0', 'all1', 'all2'):
        v = int(mode[-1])
        return [v] * N, [v] * (N - 1)
    if mode == 'cyc':
        return [j % 3 for j in range(N)], [(j + 2) % 3 for j in range(N - 1)]
    return ([rnd.randint(0, 2) for _ in range(N)],
            [rnd.randint(0, 2) for _ in range(N - 1)])


@st.composite
def make_input_med(draw):
    # small AND fairly large N; values via a seeded RNG so we don't pay the
    # cost of drawing huge lists element-by-element.
    N = draw(st.one_of(st.integers(1, 60), st.integers(200, 1500)))
    mode = draw(st.sampled_from(['all0', 'all1', 'all2', 'cyc', 'rand']))
    rnd = random.Random(draw(st.integers(0, 2 ** 31)))
    row, col_rest = gen_by_mode(N, mode, rnd)
    return build_stdin(N, row, col_rest)


@st.composite
def make_input_large(draw):
    N = draw(st.one_of(
        st.integers(1, 300),
        st.integers(1000, 3000),
        st.sampled_from([5000, 10000, 20000]),
    ))
    mode = draw(st.sampled_from(['all0', 'all1', 'all2', 'cyc', 'rand']))
    rnd = random.Random(draw(st.integers(0, 2 ** 31)))
    row, col_rest = gen_by_mode(N, mode, rnd)
    return build_stdin(N, row, col_rest)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@given(make_input_small())
@settings(max_examples=35, deadline=None)
def test_exact_small(stdin):
    # Exact certificate check: recompute the matrix from the definition.
    N, row, col_rest = parse_stdin(stdin)
    out = parse_out(run_candidate(stdin))
    exp = brute_counts(N, row, col_rest)
    assert out == exp, "counts mismatch for N=%d: got %r expected %r" % (N, out, exp)


@given(make_input_tiny())
@settings(max_examples=70, deadline=None)
def test_exact_tiny_sweep(stdin):
    N, row, col_rest = parse_stdin(stdin)
    out = parse_out(run_candidate(stdin))
    exp = brute_counts(N, row, col_rest)
    assert out == exp, "counts mismatch for N=%d: got %r expected %r" % (N, out, exp)


@given(make_input_large())
@settings(max_examples=10, deadline=None)
def test_shape_and_sum(stdin):
    # Sound for ANY N: exactly 3 non-negative counts summing to N*N.
    N, _, _ = parse_stdin(stdin)
    out = parse_out(run_candidate(stdin))
    total = N * N
    assert all(v >= 0 for v in out), "counts must be non-negative: %r" % (out,)
    assert all(v <= total for v in out), "count exceeds N*N: %r (N=%d)" % (out, N)
    assert sum(out) == total, "counts must sum to N*N=%d, got %r" % (total, out)


@given(make_input_med())
@settings(max_examples=14, deadline=None)
def test_transpose_invariant(stdin):
    # The mex table is symmetric, so transposing the border permutes the
    # matrix entries -> the three counts are invariant. Works at any N.
    N, row, col_rest = parse_stdin(stdin)
    out1 = parse_out(run_candidate(stdin))
    full_col = [row[0]] + col_rest
    t_stdin = build_stdin(N, full_col, row[1:])   # swap first row / column
    out2 = parse_out(run_candidate(t_stdin))
    assert sum(out1) == N * N
    assert out1 == out2, "transpose must preserve counts (N=%d): %r vs %r" % (N, out1, out2)


@given(make_input_med())
@settings(max_examples=14, deadline=None)
def test_prefix_monotone(stdin):
    # The top-left K x K block is fully determined by the size-K prefix of the
    # border, so each digit's count over the prefix is <= its count over the
    # full matrix (a subset of the same cells). Works at any N.
    N, row, col_rest = parse_stdin(stdin)
    full = parse_out(run_candidate(stdin))
    assert sum(full) == N * N
    if N >= 2:
        K = N - 1
        pref_stdin = build_stdin(K, row[:K], col_rest[:K - 1])
        pref = parse_out(run_candidate(pref_stdin))
        assert sum(pref) == K * K, "prefix counts must sum to K*K=%d, got %r" % (K * K, pref)
        assert all(v >= 0 for v in pref)
        for i in range(3):
            assert pref[i] <= full[i], "prefix count exceeds full: %r vs %r" % (pref, full)