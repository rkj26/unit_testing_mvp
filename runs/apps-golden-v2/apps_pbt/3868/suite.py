from hypothesis import given, strategies as st, settings, HealthCheck
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

MAXV = 10**6
_HC = [HealthCheck.too_slow, HealthCheck.data_too_large,
       HealthCheck.filter_too_much, HealthCheck.large_base_example]


# ----------------------------------------------------------------------------
# helpers (serialize / parse / analyze) -- NO optimum is ever recomputed here.
# ----------------------------------------------------------------------------
def _build(n, k, flights):
    out = ["%d %d %d" % (n, len(flights), k)]
    for (d, f, t, c) in flights:
        out.append("%d %d %d %d" % (d, f, t, c))
    return "\n".join(out) + "\n"


def _parse(stdin):
    lines = stdin.split("\n")
    n, m, k = (int(x) for x in lines[0].split())
    flights = []
    for i in range(1, 1 + m):
        d, f, t, c = (int(x) for x in lines[i].split())
        flights.append((d, f, t, c))
    return n, m, k, flights


def _analyze(n, k, flights):
    """Return (feasible, LB, UB).

    Feasibility is EXACT (decidable without solving the optimization):
    member i can arrive by day X iff earliestArr[i] <= X and depart no earlier
    than X+k+1 iff latestDep[i] >= X+k+1.  A common window exists iff
        max_i earliestArr[i] + k + 1 <= min_i latestDep[i]
    and every city has at least one arrival AND one departure flight.

    LB: sum of the globally-cheapest arrival + departure per city.  Any valid
        arrangement picks one arrival + one departure per city, so answer >= LB.
    UB: a concrete valid arrangement (threshold X = max earliestArr), so
        answer <= UB.  Hence LB <= answer <= UB, exactly pinned when each city
        has a single arrival/departure flight.
    """
    INF = float("inf")
    ea = {i: INF for i in range(1, n + 1)}   # earliest arrival day
    ld = {i: -1 for i in range(1, n + 1)}    # latest departure day
    minArr = {i: INF for i in range(1, n + 1)}
    minDep = {i: INF for i in range(1, n + 1)}
    for (d, f, t, c) in flights:
        if t == 0:                # arrival: home -> Metropolis
            city = f
            if 1 <= city <= n:
                if d < ea[city]:
                    ea[city] = d
                if c < minArr[city]:
                    minArr[city] = c
        else:                     # departure: Metropolis -> home
            city = t
            if 1 <= city <= n:
                if d > ld[city]:
                    ld[city] = d
                if c < minDep[city]:
                    minDep[city] = c

    feasible = True
    for i in range(1, n + 1):
        if ea[i] == INF or ld[i] == -1:
            feasible = False
            break
    if feasible:
        X = max(ea[i] for i in range(1, n + 1))
        minLD = min(ld[i] for i in range(1, n + 1))
        if X + k + 1 > minLD:
            feasible = False
    if not feasible:
        return False, None, None

    LB = sum(minArr[i] for i in range(1, n + 1)) + \
        sum(minDep[i] for i in range(1, n + 1))

    Y = X + k + 1
    ubA = {i: INF for i in range(1, n + 1)}
    ubD = {i: INF for i in range(1, n + 1)}
    for (d, f, t, c) in flights:
        if t == 0:
            city = f
            if 1 <= city <= n and d <= X and c < ubA[city]:
                ubA[city] = c
        else:
            city = t
            if 1 <= city <= n and d >= Y and c < ubD[city]:
                ubD[city] = c
    UB = sum(ubA[i] for i in range(1, n + 1)) + sum(ubD[i] for i in range(1, n + 1))
    return True, LB, UB


def _out_int(stdin):
    out = run_candidate(stdin)
    toks = out.split()
    assert len(toks) >= 1, "empty output for stdin=%r" % (stdin,)
    return int(toks[0])


# ----------------------------------------------------------------------------
# input generator -- deliberately manufactures the rare trigger regions.
# ----------------------------------------------------------------------------
@st.composite
def make_input(draw):
    def cost():
        return draw(st.one_of(st.just(1), st.just(MAXV),
                              st.integers(1, 1000), st.integers(1, MAXV)))

    def day():
        return draw(st.one_of(st.just(1), st.just(MAXV),
                              st.integers(1, 1000), st.integers(1, MAXV)))

    mode = draw(st.sampled_from([
        "unique", "unique", "tight", "tight", "multi", "multi",
        "random", "random", "missing", "bigk", "extreme"]))
    n = draw(st.integers(1, 5))
    flights = []

    if mode == "unique":
        # exactly one arrival + one departure per city -> LB == UB (pinned).
        k = draw(st.integers(1, 1000))
        X = draw(st.integers(1, 1000))
        Y = X + k + 1
        hi = min(MAXV, Y + 300)
        for city in range(1, n + 1):
            flights.append((draw(st.integers(1, X)), city, 0, cost()))
            flights.append((draw(st.integers(Y, hi)), 0, city, cost()))

    elif mode == "tight":
        # realise the gap boundary EXACTLY: maxArrival = X, minDeparture chosen
        # either at Y=X+k+1 (feasible, inclusive) or Y-1 (infeasible by one).
        k = draw(st.integers(1, 1000))
        X = draw(st.integers(1, 1000))
        Y = X + k + 1
        gap_ok = draw(st.booleans())
        floor = Y if gap_ok else (Y - 1)
        hi = min(MAXV, floor + 300)
        for city in range(1, n + 1):
            ad = X if city == 1 else draw(st.integers(1, X))
            flights.append((ad, city, 0, cost()))
        for city in range(1, n + 1):
            dd = floor if city == 1 else draw(st.integers(floor, hi))
            flights.append((dd, 0, city, cost()))

    elif mode == "multi":
        # several flights per city -> genuine cost/time trade-off (like ex.3).
        k = draw(st.integers(1, 1000))
        X = draw(st.integers(1, 1000))
        Y = X + k + 1
        hi = min(MAXV, Y + 300)
        for city in range(1, n + 1):
            for _ in range(draw(st.integers(1, 3))):
                flights.append((draw(st.integers(1, X)), city, 0, cost()))
            for _ in range(draw(st.integers(1, 3))):
                flights.append((draw(st.integers(Y, hi)), 0, city, cost()))

    elif mode == "random":
        # fully arbitrary structure (feasible or not), extreme magnitudes.
        k = draw(st.integers(1, MAXV))
        for _ in range(draw(st.integers(0, 15))):
            city = draw(st.integers(1, n))
            if draw(st.booleans()):
                flights.append((day(), city, 0, cost()))
            else:
                flights.append((day(), 0, city, cost()))

    elif mode == "missing":
        # a city lacks an arrival OR a departure -> guaranteed infeasible.
        k = draw(st.integers(1, 1000))
        X = draw(st.integers(1, 1000))
        Y = X + k + 1
        hi = min(MAXV, Y + 300)
        victim = draw(st.integers(1, n))
        side = draw(st.sampled_from(["arr", "dep"]))
        for city in range(1, n + 1):
            if not (city == victim and side == "arr"):
                flights.append((draw(st.integers(1, X)), city, 0, cost()))
            if not (city == victim and side == "dep"):
                flights.append((draw(st.integers(Y, hi)), 0, city, cost()))

    elif mode == "bigk":
        # k pinned near its maximum, days pushed toward 1e6 (feasible).
        k = draw(st.integers(MAXV - 60, MAXV - 2))
        Y = 1 + k + 1
        for city in range(1, n + 1):
            flights.append((1, city, 0, cost()))
            flights.append((draw(st.integers(Y, MAXV)), 0, city, cost()))

    else:  # extreme: max-day boundary combined with extreme costs.
        k = draw(st.integers(1, 100))
        X = MAXV - (k + 1)          # Y = X+k+1 = MAXV exactly (boundary)
        for city in range(1, n + 1):
            ad = draw(st.sampled_from([1, X]))
            flights.append((ad, city, 0, draw(st.sampled_from([1, MAXV]))))
            flights.append((MAXV, 0, city, draw(st.sampled_from([1, MAXV]))))

    return _build(n, k, flights)


# ----------------------------------------------------------------------------
# 1) format + EXACT feasibility (-1 iff infeasible) + [LB, UB] bracket.
# ----------------------------------------------------------------------------
@given(make_input())
@settings(max_examples=45, deadline=None, suppress_health_check=_HC)
def test_format_feasibility_bounds(stdin):
    n, m, k, flights = _parse(stdin)
    feasible, LB, UB = _analyze(n, k, flights)
    out = run_candidate(stdin)
    toks = out.split()
    assert len(toks) == 1, "output must be a single integer, got %r" % (out,)
    val = int(toks[0])
    if not feasible:
        assert val == -1, "infeasible input must yield -1, got %d" % val
    else:
        assert val != -1, "feasible input must not yield -1"
        assert LB <= val <= UB, \
            "answer %d outside sound bracket [%d, %d]" % (val, LB, UB)


# ----------------------------------------------------------------------------
# 2) metamorphic: scaling every cost by c scales the optimum by c (feasibility
#    is cost-independent, so -1 stays -1).
# ----------------------------------------------------------------------------
@given(make_input())
@settings(max_examples=15, deadline=None, suppress_health_check=_HC)
def test_cost_scaling(stdin):
    n, m, k, flights = _parse(stdin)
    if m == 0:
        return
    maxc = max(c for (_, _, _, c) in flights)
    c = 1
    for cand in (997, 131, 13, 7, 3, 2):
        if cand * maxc <= MAXV:
            c = cand
            break
    if c == 1:
        return
    scaled = [(d, f, t, cc * c) for (d, f, t, cc) in flights]
    v1 = _out_int(stdin)
    v2 = _out_int(_build(n, k, scaled))
    if v1 == -1:
        assert v2 == -1, "scaling must not change feasibility"
    else:
        assert v2 == v1 * c, "scaled answer %d != %d * %d" % (v2, v1, c)


# ----------------------------------------------------------------------------
# 3) metamorphic: shifting all days by a constant and reordering the flight
#    lines leaves the answer unchanged (relative schedule + set are invariant).
# ----------------------------------------------------------------------------
@given(make_input())
@settings(max_examples=15, deadline=None, suppress_health_check=_HC)
def test_shift_and_reorder_invariant(stdin):
    n, m, k, flights = _parse(stdin)
    if m == 0:
        return
    maxday = max(d for (d, _, _, _) in flights)
    delta = MAXV - maxday          # push schedule to the high end, stays valid
    shifted = [(d + delta, f, t, c) for (d, f, t, c) in flights]
    shifted.reverse()              # also permute line order
    v1 = _out_int(stdin)
    v2 = _out_int(_build(n, k, shifted))
    assert v1 == v2, "day-shift + reorder changed answer: %d vs %d" % (v1, v2)


# ----------------------------------------------------------------------------
# 4) metamorphic: adding flights can only widen the option set, so a feasible
#    instance stays feasible and its cost cannot increase.
# ----------------------------------------------------------------------------
@given(make_input())
@settings(max_examples=15, deadline=None, suppress_health_check=_HC)
def test_add_flight_monotone(stdin):
    n, m, k, flights = _parse(stdin)
    extra = flights + [(1, 1, 0, 1), (MAXV, 0, 1, 1)]  # cheap arr+dep for city 1
    v1 = _out_int(stdin)
    v2 = _out_int(_build(n, k, extra))
    if v1 != -1:
        assert v2 != -1, "adding flights must not break feasibility"
        assert v2 <= v1, "adding flights raised the cost: %d -> %d" % (v1, v2)


# ----------------------------------------------------------------------------
# 5) metamorphic: relabelling cities (a bijection on 1..n) is a symmetry;
#    the answer must be identical.
# ----------------------------------------------------------------------------
@given(make_input())
@settings(max_examples=15, deadline=None, suppress_health_check=_HC)
def test_relabel_cities_invariant(stdin):
    n, m, k, flights = _parse(stdin)
    if m == 0:
        return

    def rel(x):
        return 0 if x == 0 else (n + 1 - x)

    relabeled = [(d, rel(f), rel(t), c) for (d, f, t, c) in flights]
    v1 = _out_int(stdin)
    v2 = _out_int(_build(n, k, relabeled))
    assert v1 == v2, "relabelling cities changed answer: %d vs %d" % (v1, v2)
