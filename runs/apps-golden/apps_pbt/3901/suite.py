import itertools
from math import gcd
from functools import reduce

from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

# ---------------------------------------------------------------------------
# Problem recap (used ONLY for SOUND properties, never to recompute the optimum):
#
#   Array a of length n. Op: pick two adjacent x,y and replace one of them with
#   gcd(x,y). Minimise ops to make every element == 1. Print -1 if impossible.
#
# Facts entailed by the spec for EVERY correct solution:
#   * Overall gcd is INVARIANT under the operation, so the array can be reduced
#     to all-ones IFF gcd(all) == 1.  => answer == -1  <=>  gcd(all) != 1.
#   * Every element that starts != 1 and ends == 1 must be replaced at least
#     once, and each op replaces exactly one element, so
#         answer >= (# elements != 1).
#   * A one can always be spread to a neighbour in 1 op, and one 1 can be
#     created from the whole (gcd-1) array in n-1 ops, so
#         answer <= 2*(n-1).
#   * If >=1 one is already present, answer == (# elements != 1) exactly.
#   * When no ones are present and feasible, answer == (L-1)+(n-1) where L is
#     the length of the shortest contiguous subarray whose gcd is 1; hence
#     L = answer-n+2 must be a valid window length AND some window of that
#     length must actually have gcd 1 (necessary condition; catches undershoot).
#   * The whole problem is symmetric under reversing the array (adjacency
#     preserved, gcd symmetric):  answer(a) == answer(reverse(a)).
#
# We deliberately do NOT reimplement the shortest-subarray optimum and compare.
# ---------------------------------------------------------------------------

MAXV = 10 ** 9
BIG_PRIMES = [999999937, 999999893, 982451653]
SMALL_POOL = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15]


def build(arr):
    return "{}\n{}\n".format(len(arr), " ".join(map(str, arr)))


def parse_arr(stdin):
    lines = stdin.split("\n")
    n = int(lines[0])
    return list(map(int, lines[1].split())) if n > 0 else []


def parse_out(stdout):
    return int(stdout.strip())


def overall_gcd(arr):
    return reduce(gcd, arr)


def num_non_one(arr):
    return sum(1 for x in arr if x != 1)


def has_window_gcd1(arr, L):
    n = len(arr)
    for i in range(0, n - L + 1):
        if reduce(gcd, arr[i:i + L]) == 1:
            return True
    return False


def check_basic(arr, out):
    n = len(arr)
    assert out == -1 or out >= 0, "output must be -1 or non-negative, got {}".format(out)
    g = overall_gcd(arr)
    nn = num_non_one(arr)
    ones = n - nn
    if g != 1:
        assert out == -1, "gcd(all)={}>1 so answer must be -1, got {}".format(g, out)
    else:
        assert out != -1, "gcd(all)==1 so it is feasible, but got -1"
        assert out >= nn, "answer {} below lower bound {} (# non-one elements)".format(out, nn)
        assert out <= 2 * (n - 1), "answer {} above upper bound {}".format(out, 2 * (n - 1))
        if ones >= 1:
            assert out == nn, "with a 1 present, answer must equal {} (# non-one), got {}".format(nn, out)


def check_certificate(arr, out):
    # Only meaningful for feasible arrays that contain NO ones.
    n = len(arr)
    if n >= 2 and overall_gcd(arr) == 1 and num_non_one(arr) == n:
        L = out - n + 2
        assert 2 <= L <= n, "implied shortest coprime-window length {} out of [2,{}]".format(L, n)
        assert has_window_gcd1(arr, L), \
            "no length-{} contiguous window has gcd 1; answer {} is too small".format(L, out)


# ---------------------------------------------------------------------------
# Generators -- manufacture the rare trigger regions.
# ---------------------------------------------------------------------------
@st.composite
def make_input(draw):
    mode = draw(st.sampled_from(
        ["rand", "ones", "alleq", "infeasible", "largeL", "extreme", "maxn", "tiny"]))

    if mode == "tiny":                                   # singleton / tiny sweep + extremes
        n = draw(st.integers(1, 4))
        pool = [1, 2, 3, 4, 5, 6, 7, 9, 10, 15] + BIG_PRIMES + [MAXV]
        arr = [draw(st.sampled_from(pool)) for _ in range(n)]
    elif mode == "rand":                                 # broad random, whole value range
        n = draw(st.integers(1, 40))
        arr = [draw(st.one_of(st.integers(1, MAXV), st.sampled_from(SMALL_POOL)))
               for _ in range(n)]
    elif mode == "ones":                                 # ones-present regime (exact answer)
        n = draw(st.integers(1, 40))
        pool = [1, 1, 1, 2, 3, 4, 5, 6, 7, 10, 12, 15] + BIG_PRIMES + [MAXV]
        arr = [draw(st.sampled_from(pool)) for _ in range(n)]
    elif mode == "alleq":                                # all-equal (0 or -1), any size
        n = draw(st.integers(1, 2000))
        c = draw(st.sampled_from([1, 2, 3, 7, 10, 999999937, MAXV]))
        arr = [c] * n
    elif mode == "infeasible":                           # common factor => must be -1
        p = draw(st.sampled_from([2, 3, 5, 7, 11]))
        n = draw(st.integers(2, 60))
        arr = [p * draw(st.integers(1, MAXV // p)) for _ in range(n)]
    elif mode == "largeL":                               # forces shortest window length 3
        n = draw(st.integers(3, 60))
        pat = draw(st.sampled_from(
            [[6, 10, 15], [10, 15, 6], [15, 6, 10],
             [30, 42, 35], [42, 35, 30], [35, 30, 42]]))
        arr = [pat[i % 3] for i in range(n)]
    elif mode == "extreme":                              # extremes mixed with tiny
        n = draw(st.integers(1, 60))
        pool = [1, 2, MAXV, 999999937, 999999893, 536870912, 387420489, 999999999]
        arr = [draw(st.sampled_from(pool)) for _ in range(n)]
    else:                                                # maxn: max size structural edges
        n = 2000
        kind = draw(st.sampled_from(
            ["allone", "one_end", "coprime_start", "alleven", "pattern"]))
        if kind == "allone":
            arr = [1] * n
        elif kind == "one_end":
            arr = [draw(st.sampled_from([2, 3, 4, 6, MAXV]))] * (n - 1) + [1]
        elif kind == "coprime_start":
            arr = [2, 3] + [draw(st.sampled_from([4, 6, 8, 9, 10, MAXV]))] * (n - 2)
        elif kind == "alleven":
            arr = [draw(st.sampled_from([2, 4, 6, 8, 10]))] * n
        else:
            arr = [[6, 10, 15][i % 3] for i in range(n)]
    return build(arr)


@st.composite
def make_ones_input(draw):
    n = draw(st.integers(1, 60))
    pool = [1, 1, 2, 3, 4, 5, 6, 7, 10, 12, 15, 21, 35] + BIG_PRIMES + [MAXV]
    arr = [draw(st.sampled_from(pool)) for _ in range(n)]
    arr[draw(st.integers(0, n - 1))] = 1          # guarantee at least one 1
    return build(arr)


@st.composite
def make_small_input(draw):
    # no 1s => exercises the ones==0 branch (feasible & infeasible) with varied L
    n = draw(st.integers(1, 12))
    pool = [2, 3, 4, 5, 6, 7, 9, 10, 12, 14, 15, 21, 35]
    arr = [draw(st.sampled_from(pool)) for _ in range(n)]
    return build(arr)


# Deterministic sweep of the tightly-bounded small box (defeats magic-value guards).
_sweep_pool = [1, 2, 3, 4, 5, 6, 9, 10]
SWEEP_CASES = []
for _n in (1, 2):
    for _combo in itertools.product(_sweep_pool, repeat=_n):
        SWEEP_CASES.append(build(list(_combo)))
for _t in [
    [6, 10, 15], [6, 15, 10], [10, 6, 15], [15, 10, 6], [10, 15, 6], [15, 6, 10],
    [30, 42, 35], [2, 3, 4], [4, 6, 3], [9, 6, 4], [1, 2, 3], [2, 1, 3], [2, 3, 1],
    [MAXV, 999999937, 2], [999999937, 2, 3], [4, 6, 9], [6, 9, 4], [9, 4, 6],
    [2, 4, 8], [3, 9, 27], [5, 10, 15], [1, 1, 2], [7, 7, 7],
]:
    SWEEP_CASES.append(build(_t))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@given(make_input())
@settings(max_examples=30, deadline=None)
def test_format_feasibility_and_append(stdin):
    arr = parse_arr(stdin)
    out = parse_out(run_candidate(stdin))
    check_basic(arr, out)
    # Metamorphic/certificate: appending a 1 makes it feasible with a 1 present,
    # so the answer must be exactly (# non-one elements of the original array).
    if len(arr) < 2000:
        out2 = parse_out(run_candidate(build(arr + [1])))
        exp = num_non_one(arr)
        assert out2 == exp, "after appending a 1 answer must be {} (# non-one), got {}".format(exp, out2)


@given(make_ones_input())
@settings(max_examples=30, deadline=None)
def test_ones_certificate(stdin):
    arr = parse_arr(stdin)
    out = parse_out(run_candidate(stdin))
    check_basic(arr, out)          # includes exact answer == (# non-one) when a 1 is present


@given(make_input())
@settings(max_examples=20, deadline=None)
def test_reverse_symmetry(stdin):
    arr = parse_arr(stdin)
    out1 = parse_out(run_candidate(stdin))
    out2 = parse_out(run_candidate(build(arr[::-1])))
    assert out1 == out2, "reversing the array must not change the answer: {} vs {}".format(out1, out2)
    check_basic(arr, out1)


@given(make_small_input())
@settings(max_examples=30, deadline=None)
def test_shortest_window_certificate(stdin):
    arr = parse_arr(stdin)
    out = parse_out(run_candidate(stdin))
    check_basic(arr, out)
    check_certificate(arr, out)


@given(st.just(0))
@settings(max_examples=1, deadline=None)
def test_small_exhaustive(_):
    for stdin in SWEEP_CASES:
        arr = parse_arr(stdin)
        out = parse_out(run_candidate(stdin))
        check_basic(arr, out)
        check_certificate(arr, out)