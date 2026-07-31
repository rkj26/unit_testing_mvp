from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str
from math import gcd

COORD = 10 ** 6
P = 300  # restricted point magnitude for tests that construct bounded separating lines


# ---------------------------------------------------------------------------
# Helpers (NOT a solver: used only to build inputs with KNOWN local status and
# to check format/range/metamorphic relations -- never to compute the optimum
# of an arbitrary opponent-shaped input.)
# ---------------------------------------------------------------------------
def norm_key(a, b, c):
    """Canonical key so two proportional coefficient triples (== the SAME road)
    map to the same value -- used to guarantee road distinctness."""
    g = gcd(gcd(abs(a), abs(b)), abs(c))
    if g == 0:
        g = 1
    a, b, c = a // g, b // g, c // g
    if a < 0 or (a == 0 and b < 0) or (a == 0 and b == 0 and c < 0):
        a, b, c = -a, -b, -c
    return (a, b, c)


def build_stdin(hx, hy, ux, uy, roads):
    lines = ["%d %d" % (hx, hy), "%d %d" % (ux, uy), str(len(roads))]
    for (a, b, c) in roads:
        lines.append("%d %d %d" % (a, b, c))
    return "\n".join(lines) + "\n"


def run_int(stdin, n):
    """Run candidate, enforce FORMAT (single integer token) and RANGE
    (0 <= answer <= n), return the parsed integer."""
    out = run_candidate(stdin)
    toks = out.split()
    assert len(toks) == 1, "expected a single integer token, got %r" % (out,)
    tok = toks[0]
    assert tok.lstrip("-").isdigit(), "output is not an integer: %r" % (out,)
    val = int(tok)
    assert 0 <= val <= n, "answer %d out of provable range [0, %d]" % (val, n)
    return val


def coord_strat():
    return st.one_of(
        st.sampled_from([-COORD, COORD, 0, 1, -1, COORD - 1, -COORD + 1]),
        st.integers(min_value=-COORD, max_value=COORD),
    )


def coef_strat():
    return st.one_of(
        st.sampled_from([-COORD, COORD, 0, 1, -1, COORD - 1, -COORD + 1]),
        st.integers(min_value=-COORD, max_value=COORD),
    )


def _add_fallback_road(hx, hy, ux, uy, roads, seen):
    """Guarantee at least one valid road (n >= 1)."""
    if roads:
        return
    for (a, b) in ((1, 0), (0, 1)):
        for cc in range(0, 8):
            if a * hx + b * hy + cc != 0 and a * ux + b * uy + cc != 0:
                k = norm_key(a, b, cc)
                if k not in seen:
                    seen.add(k)
                    roads.append((a, b, cc))
                    return


# ---------------------------------------------------------------------------
# General valid-input generator (full magnitudes + structural modes:
# random / all-parallel / all-concurrent).
# ---------------------------------------------------------------------------
@st.composite
def general_input(draw):
    hx, hy = draw(coord_strat()), draw(coord_strat())
    ux, uy = draw(coord_strat()), draw(coord_strat())
    n_target = draw(st.integers(min_value=1, max_value=40))
    mode = draw(st.sampled_from(["random", "random", "parallel", "concurrent"]))
    seen = set()
    roads = []

    if mode == "parallel":
        a0 = draw(st.integers(min_value=-COORD, max_value=COORD))
        b0 = draw(st.integers(min_value=-COORD, max_value=COORD))
        if a0 == 0 and b0 == 0:
            a0 = 1
        attempts = 0
        while len(roads) < n_target and attempts < n_target * 6 + 60:
            attempts += 1
            c = draw(coef_strat())
            if a0 * hx + b0 * hy + c == 0 or a0 * ux + b0 * uy + c == 0:
                continue
            k = norm_key(a0, b0, c)
            if k in seen:
                continue
            seen.add(k)
            roads.append((a0, b0, c))
    elif mode == "concurrent":
        # common point Q kept small so c stays within bounds
        qx = draw(st.integers(min_value=-500, max_value=500))
        qy = draw(st.integers(min_value=-500, max_value=500))
        attempts = 0
        while len(roads) < n_target and attempts < n_target * 6 + 60:
            attempts += 1
            a = draw(st.integers(min_value=-500, max_value=500))
            b = draw(st.integers(min_value=-500, max_value=500))
            if a == 0 and b == 0:
                continue
            c = -(a * qx + b * qy)
            if not (-COORD <= c <= COORD):
                continue
            if a * hx + b * hy + c == 0 or a * ux + b * uy + c == 0:
                continue
            k = norm_key(a, b, c)
            if k in seen:
                continue
            seen.add(k)
            roads.append((a, b, c))
    else:
        attempts = 0
        while len(roads) < n_target and attempts < n_target * 6 + 80:
            attempts += 1
            a, b, c = draw(coef_strat()), draw(coef_strat()), draw(coef_strat())
            if a == 0 and b == 0:
                continue
            if a * hx + b * hy + c == 0 or a * ux + b * uy + c == 0:
                continue
            k = norm_key(a, b, c)
            if k in seen:
                continue
            seen.add(k)
            roads.append((a, b, c))

    _add_fallback_road(hx, hy, ux, uy, roads, seen)
    return (hx, hy, ux, uy, roads)


# ---------------------------------------------------------------------------
# Generator for tests that must construct bounded lines with a KNOWN separation
# status: points restricted to [-P, P] with hx != ux AND hy != uy so the
# direction (dx, dy) has both components nonzero and |dx|^2+|dy|^2 >= 2.
# ---------------------------------------------------------------------------
@st.composite
def sep_add_input(draw):
    hx = draw(st.integers(min_value=-P, max_value=P))
    hy = draw(st.integers(min_value=-P, max_value=P))
    ux = draw(st.integers(min_value=-P, max_value=P))
    uy = draw(st.integers(min_value=-P, max_value=P))
    if ux == hx:
        ux = hx + 1 if hx < P else hx - 1
    if uy == hy:
        uy = hy + 1 if hy < P else hy - 1
    dx, dy = hx - ux, hy - uy  # both nonzero
    a, b = dx, dy
    d1 = a * hx + b * hy
    # c = -d1 + 1 => s1 = 1 (>0), s2 = 1 - D (<0)  -> SEPARATES
    Lsep = (a, b, -d1 + 1)
    # c = -d1 - 1 => s1 = -1 (<0), s2 = -1 - D (<0) -> DOES NOT SEPARATE
    Lnonsep = (a, b, -d1 - 1)

    seen = {norm_key(*Lsep), norm_key(*Lnonsep)}
    roads = []
    target = draw(st.integers(min_value=1, max_value=15))
    attempts = 0
    while len(roads) < target and attempts < target * 6 + 40:
        attempts += 1
        aa, bb, cc = draw(coef_strat()), draw(coef_strat()), draw(coef_strat())
        if aa == 0 and bb == 0:
            continue
        if aa * hx + bb * hy + cc == 0 or aa * ux + bb * uy + cc == 0:
            continue
        k = norm_key(aa, bb, cc)
        if k in seen:
            continue
        seen.add(k)
        roads.append((aa, bb, cc))
    _add_fallback_road(hx, hy, ux, uy, roads, seen)
    return (hx, hy, ux, uy, roads, Lsep, Lnonsep)


@st.composite
def batch_input(draw):
    hx = draw(st.integers(min_value=-P, max_value=P))
    hy = draw(st.integers(min_value=-P, max_value=P))
    ux = draw(st.integers(min_value=-P, max_value=P))
    uy = draw(st.integers(min_value=-P, max_value=P))
    if ux == hx:
        ux = hx + 1 if hx < P else hx - 1
    if uy == hy:
        uy = hy + 1 if hy < P else hy - 1
    dx, dy = hx - ux, hy - uy
    a, b = dx, dy
    d1 = a * hx + b * hy
    D = dx * dx + dy * dy  # >= 2

    k_max = min(4, D - 1)
    K = draw(st.integers(min_value=0, max_value=k_max))
    # M non-separating parallel lines; bias to hit the maximum road count.
    M = draw(st.one_of(
        st.integers(min_value=1, max_value=min(20, 300 - K)),
        st.just(300 - K),
    ))

    nonsep = [(a, b, -d1 - t) for t in range(1, M + 1)]      # all put both pts same side
    sep = [(a, b, -d1 + k) for k in range(1, K + 1)]          # each separates (k < D)
    return (hx, hy, ux, uy, nonsep, sep, K)


# ---------------------------------------------------------------------------
# TEST 1 - format / range invariants + endpoint-swap symmetry (metamorphic).
# Full magnitudes, structural modes.  2 candidate calls / example.
# ---------------------------------------------------------------------------
@given(general_input())
@settings(max_examples=25, deadline=None)
def test_format_range_symmetry(data):
    hx, hy, ux, uy, roads = data
    n = len(roads)
    ans = run_int(build_stdin(hx, hy, ux, uy, roads), n)
    # swapping home <-> university cannot change the minimum number of steps.
    ans_swapped = run_int(build_stdin(ux, uy, hx, hy, roads), n)
    assert ans == ans_swapped, "answer must be symmetric in the two endpoints: %d vs %d" % (
        ans, ans_swapped)


# ---------------------------------------------------------------------------
# TEST 2 - road reordering + coefficient negation leave the geometry (and thus
# the answer) unchanged (metamorphic).  2 candidate calls / example.
# ---------------------------------------------------------------------------
@given(general_input(), st.data())
@settings(max_examples=15, deadline=None)
def test_permutation_negation_invariance(data, extra):
    hx, hy, ux, uy, roads = data
    n = len(roads)
    ans = run_int(build_stdin(hx, hy, ux, uy, roads), n)

    perm = extra.draw(st.permutations(range(n)))
    flip = [extra.draw(st.booleans()) for _ in range(n)]
    transformed = []
    for i in perm:
        a, b, c = roads[i]
        if flip[i]:
            a, b, c = -a, -b, -c  # (-a,-b,-c) is the SAME road
        transformed.append((a, b, c))
    ans2 = run_int(build_stdin(hx, hy, ux, uy, transformed), n)
    assert ans == ans2, "reordering / negating road coefficients must not change the answer: %d vs %d" % (
        ans, ans2)


# ---------------------------------------------------------------------------
# TEST 3 - add ONE line of known separation status (certificate/metamorphic):
# adding a separating line increases the answer by exactly 1; adding a
# non-separating line leaves it unchanged.  3 candidate calls / example.
# ---------------------------------------------------------------------------
@given(sep_add_input())
@settings(max_examples=12, deadline=None)
def test_add_line_deltas(data):
    hx, hy, ux, uy, roads, Lsep, Lnonsep = data
    n = len(roads)
    base = run_int(build_stdin(hx, hy, ux, uy, roads), n)
    with_sep = run_int(build_stdin(hx, hy, ux, uy, roads + [Lsep]), n + 1)
    with_non = run_int(build_stdin(hx, hy, ux, uy, roads + [Lnonsep]), n + 1)
    assert with_sep == base + 1, "adding a separating line must add exactly 1 step: %d -> %d" % (
        base, with_sep)
    assert with_non == base, "adding a non-separating line must not change the answer: %d -> %d" % (
        base, with_non)


# ---------------------------------------------------------------------------
# TEST 4 - certificate (no separating line => same block => 0) + batch delta
# (adding K separating lines adds exactly K).  Exercises all-parallel geometry
# and road counts up to the maximum (n = 300).  2 candidate calls / example.
# ---------------------------------------------------------------------------
@given(batch_input())
@settings(max_examples=10, deadline=None)
def test_no_separation_and_batch(data):
    hx, hy, ux, uy, nonsep, sep, K = data
    M = len(nonsep)
    a0 = run_int(build_stdin(hx, hy, ux, uy, nonsep), M)
    assert a0 == 0, "no line separates the endpoints => they share a block => 0 steps, got %d" % a0
    a1 = run_int(build_stdin(hx, hy, ux, uy, nonsep + sep), M + K)
    assert a1 - a0 == K, "adding %d separating lines must add exactly %d steps: %d -> %d" % (
        K, K, a0, a1)


# ---------------------------------------------------------------------------
# TEST 5 - deterministic sweep of small hand-verified cases (min size n=1,
# parallel, concurrent, extreme magnitudes, and the provided examples).
# Each case has an answer computable by inspection of the sign pairs.
# 1 candidate call / case.
# ---------------------------------------------------------------------------
CASES = [
    # provided examples
    ("1 1\n-1 -1\n2\n0 1 0\n1 0 0\n", 2),
    ("1 1\n-1 -1\n3\n1 0 0\n0 1 0\n1 1 -3\n", 2),
    # n = 1, single separating line
    ("1 1\n-1 -1\n1\n1 0 0\n", 1),
    # n = 1, single non-separating line
    ("1 1\n2 2\n1\n1 1 -10\n", 0),
    # two parallel separating lines
    ("0 0\n10 10\n2\n1 0 -2\n1 0 -5\n", 2),
    # three concurrent (through origin) separating lines
    ("1 0\n-1 0\n3\n1 0 0\n1 -1 0\n1 1 0\n", 3),
    # extreme-magnitude endpoints, one separating line
    ("1000000 1000000\n-1000000 -1000000\n1\n1 0 0\n", 1),
    # extreme-magnitude coefficients, non-separating
    ("1 1\n2 2\n1\n1000000 1000000 -1000000\n", 0),
]


@given(st.just(0))
@settings(max_examples=1, deadline=None)
def test_known_micro_cases(_):
    for stdin, expected in CASES:
        n = int(stdin.split("\n")[2])
        val = run_int(stdin, n)
        assert val == expected, "case %r expected %d, got %d" % (stdin, expected, val)