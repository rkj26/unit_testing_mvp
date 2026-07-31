from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str
from collections import defaultdict


# ----------------------------------------------------------------------------
# Helpers (parsing / formatting / provable bounds)
# ----------------------------------------------------------------------------
def _parse_input(stdin):
    lines = stdin.strip().split('\n')
    n, m = map(int, lines[0].split())
    candies = []
    for i in range(1, 1 + m):
        a, b = map(int, lines[i].split())
        candies.append((a, b))
    return n, m, candies


def _parse_output(stdout):
    return list(map(int, stdout.split()))


def _format_input(n, candies):
    parts = ["{} {}".format(n, len(candies))]
    for a, b in candies:
        parts.append("{} {}".format(a, b))
    return "\n".join(parts) + "\n"


def _bounds(n, candies):
    # For each station a with candies:
    #   cost_a = (c_a - 1) * n + minDist_a
    # LOWER bound (necessary): the train must visit a at least c_a times, and
    # consecutive visits are >= n apart (a full circular loop), with the first
    # visit no earlier than dist(s,a); the last-picked candy at a then still
    # travels at least minDist_a.  => ans[s] >= dist(s,a) + cost_a for each a.
    # UPPER bound (feasible schedule): the train keeps circling, picking one
    # candy per visit and delivering the minimum-distance candy last; this
    # concrete schedule finishes station a at exactly dist(s,a) + cost_a, so the
    # optimum is <= max over a of that value.  Lower == upper == the answer.
    cnt = defaultdict(int)
    mind = {}
    for a, b in candies:
        d = (b - a) % n
        cnt[a] += 1
        if a not in mind or d < mind[a]:
            mind[a] = d
    cost = {a: (cnt[a] - 1) * n + mind[a] for a in cnt}
    res = []
    for s in range(1, n + 1):
        best = 0
        for a, c in cost.items():
            v = ((a - s) % n) + c
            if v > best:
                best = v
        res.append(best)
    return res


# ----------------------------------------------------------------------------
# Deterministic small-case sweep (whole distance/wrap logic lives in a tiny box)
# ----------------------------------------------------------------------------
def _small_cases():
    cases = []
    # every single-candy (a,b) with a!=b for small n -> exercises (b-a)%n
    # including all wrap-around (b<a) and adjacent (n->1, 1->n) situations.
    for n in range(2, 6):
        for a in range(1, n + 1):
            for b in range(1, n + 1):
                if a != b:
                    cases.append(_format_input(n, [(a, b)]))
    # heavy-duplicate origins -> exercises the (c_a - 1)*n term with large c_a
    for n in (2, 3, 4):
        for a in range(1, n + 1):
            b = (a % n) + 1
            for k in (2, 3, 5):
                cases.append(_format_input(n, [(a, b)] * k))
    # a single station holding both a min-distance (1) and a max-distance (n-1)
    # candy -> exercises minDist selection / last-picked choice.
    for n in (3, 4, 5):
        cases.append(_format_input(n, [(1, 2), (1, n)]))
    return cases


SMALL_CASES = _small_cases()


# ----------------------------------------------------------------------------
# Input generator: mixes uniform draws with manufactured trigger regions.
# ----------------------------------------------------------------------------
def _rand_dest(draw, n, a):
    # uniform over [1..n] \ {a}
    b = draw(st.integers(min_value=1, max_value=n - 1))
    if b >= a:
        b += 1
    return b


@st.composite
def make_input(draw):
    mode = draw(st.integers(min_value=0, max_value=7))

    if mode == 0:
        # generic random
        n = draw(st.integers(2, 100))
        m = draw(st.integers(1, 200))
        candies = [(a, _rand_dest(draw, n, a))
                   for a in (draw(st.integers(1, n)) for _ in range(m))]

    elif mode == 1:
        # single hub origin, many candies -> very large c_a
        n = draw(st.integers(2, 100))
        m = draw(st.integers(1, 200))
        a0 = draw(st.integers(1, n))
        candies = [(a0, _rand_dest(draw, n, a0)) for _ in range(m)]

    elif mode == 2:
        # all identical candies
        n = draw(st.integers(2, 100))
        m = draw(st.integers(1, 200))
        a = draw(st.integers(1, n))
        b = _rand_dest(draw, n, a)
        candies = [(a, b)] * m

    elif mode == 3:
        # extreme magnitude: max n and max m
        n = 100
        m = 200
        candies = [(a, _rand_dest(draw, n, a))
                   for a in (draw(st.integers(1, n)) for _ in range(m))]

    elif mode == 4:
        # minimum n=2 (tiny bounded domain), possibly heavy m
        n = 2
        m = draw(st.integers(1, 200))
        candies = []
        for _ in range(m):
            a = draw(st.integers(1, 2))
            candies.append((a, 3 - a))

    elif mode == 5:
        # wrap-heavy: destinations strictly behind origin (b < a)
        n = draw(st.integers(3, 100))
        m = draw(st.integers(1, 200))
        candies = []
        for _ in range(m):
            a = draw(st.integers(2, n))
            b = draw(st.integers(1, a - 1))
            candies.append((a, b))

    elif mode == 6:
        # one hub with BOTH distance-1 and distance-(n-1) candies present
        n = draw(st.integers(3, 100))
        a0 = draw(st.integers(1, n))
        near = (a0 % n) + 1              # distance 1
        far = ((a0 - 2) % n) + 1        # distance n-1
        m = draw(st.integers(2, 200))
        candies = [(a0, near if draw(st.booleans()) else far) for _ in range(m)]
        candies[0] = (a0, near)
        candies[-1] = (a0, far)

    else:
        # few hubs on a large ring -> many empty stations (adjacency test bites)
        n = draw(st.integers(5, 100))
        m = draw(st.integers(1, 200))
        hubs = draw(st.lists(st.integers(1, n), min_size=1, max_size=2,
                             unique=True))
        candies = []
        for _ in range(m):
            a = draw(st.sampled_from(hubs))
            candies.append((a, _rand_dest(draw, n, a)))

    return _format_input(n, candies)


# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------
@given(make_input())
@settings(max_examples=35, deadline=None)
def test_shape_and_range(stdin):
    n, m, candies = _parse_input(stdin)
    out = _parse_output(run_candidate(stdin))
    # exactly n answers
    assert len(out) == n, "expected {} integers, got {}".format(n, len(out))
    # loose but provable global bounds: every answer >= 1 (at least one candy,
    # each needs >=1 sec of travel) and <= (m+1)*n (dist<=n-1, (c-1)n<=(m-1)n,
    # minDist<=n-1).
    upper = (m + 1) * n
    for v in out:
        assert v >= 1, "time must be >= 1, got {}".format(v)
        assert v <= upper, "time {} exceeds provable upper bound {}".format(v, upper)


@given(make_input())
@settings(max_examples=45, deadline=None)
def test_certificate_bounds(stdin):
    n, m, candies = _parse_input(stdin)
    out = _parse_output(run_candidate(stdin))
    assert len(out) == n, "expected {} integers, got {}".format(n, len(out))
    exp = _bounds(n, candies)
    for s in range(n):
        # necessary lower bound (visit count * loop + minimum travel)
        assert out[s] >= exp[s], \
            "start {}: {} below necessary lower bound {}".format(s + 1, out[s], exp[s])
        # feasible circling schedule achieves this value
        assert out[s] <= exp[s], \
            "start {}: {} above achievable schedule cost {}".format(s + 1, out[s], exp[s])


@given(make_input(), st.integers(min_value=1, max_value=99))
@settings(max_examples=18, deadline=None)
def test_rotation_metamorphic(stdin, delta):
    n, m, candies = _parse_input(stdin)
    d = delta % n
    if d == 0:
        return
    # relabel every station x -> ((x-1+d) % n)+1; problem is rotationally
    # symmetric, so the answer array must be cyclically shifted by d.
    rotated = [(((a - 1 + d) % n) + 1, ((b - 1 + d) % n) + 1) for a, b in candies]
    base = _parse_output(run_candidate(stdin))
    rot = _parse_output(run_candidate(_format_input(n, rotated)))
    assert len(base) == n and len(rot) == n
    for j in range(1, n + 1):
        src = ((j - 1 - d) % n) + 1
        assert rot[j - 1] == base[src - 1], \
            "rotate by {}: rot[{}]={} != base[{}]={}".format(
                d, j, rot[j - 1], src, base[src - 1])


@given(make_input())
@settings(max_examples=35, deadline=None)
def test_adjacent_empty_station_consistency(stdin):
    n, m, candies = _parse_input(stdin)
    out = _parse_output(run_candidate(stdin))
    assert len(out) == n
    # If start station s holds no candy, moving the start to the next station
    # decreases every station's distance by exactly 1 (no term wraps), so the
    # answer must drop by exactly 1.
    S = set(a for a, b in candies)
    for s in range(1, n + 1):
        if s not in S:
            nxt = s + 1 if s < n else 1
            assert out[nxt - 1] == out[s - 1] - 1, \
                "empty start {}: out[{}]={} != out[{}]-1={}".format(
                    s, nxt, out[nxt - 1], s, out[s - 1] - 1)


@given(st.sampled_from(SMALL_CASES))
@settings(max_examples=min(len(SMALL_CASES), 55), deadline=None)
def test_small_cases_sweep(stdin):
    n, m, candies = _parse_input(stdin)
    out = _parse_output(run_candidate(stdin))
    assert len(out) == n
    exp = _bounds(n, candies)
    for s in range(n):
        assert out[s] == exp[s], \
            "small case start {}: got {}, want {}".format(s + 1, out[s], exp[s])