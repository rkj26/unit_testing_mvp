import string
from collections import defaultdict

from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

LETTERS = string.ascii_letters  # 52 case-sensitive letters, per spec


# ----------------------------------------------------------------------------
# helpers (compute base trip costs -- this is a deterministic function of the
# input, NOT the optimisation; it lets us bracket / certify the answer without
# reimplementing the top-k card-selection solver).
# ----------------------------------------------------------------------------
def _build(n, a, b, k, f, trips):
    lines = ["%d %d %d %d %d" % (n, a, b, k, f)]
    for (s, t) in trips:
        lines.append("%s %s" % (s, t))
    return "\n".join(lines) + "\n"


def _parse_raw(stdin):
    lines = stdin.split("\n")
    n, a, b, k, f = map(int, lines[0].split())
    trips = []
    for i in range(1, 1 + n):
        parts = lines[i].split()
        trips.append((parts[0], parts[1]))
    return n, a, b, k, f, trips


def _base_costs(a, b, trips):
    """Return (total_base_cost, {route: base_cost_on_that_route})."""
    route = defaultdict(int)
    total = 0
    prev = None
    for i, (s, t) in enumerate(trips):
        base = a if i == 0 else (b if s == prev else a)
        total += base
        route[tuple(sorted((s, t)))] += base
        prev = t
    return total, route


def _out(stdout):
    s = stdout.strip()
    try:
        return int(s)
    except Exception:
        raise AssertionError("output is not a single integer: %r" % (stdout,))


# ----------------------------------------------------------------------------
# input generation -- biased hard toward exact thresholds, degenerate
# structures and extreme magnitudes.
# ----------------------------------------------------------------------------
@st.composite
def _params(draw):
    n = draw(st.one_of(st.sampled_from([1, 2, 3, 300]), st.integers(1, 300)))
    a = draw(st.one_of(st.sampled_from([2, 3, 50, 99, 100]), st.integers(2, 100)))
    b = draw(st.one_of(st.just(1), st.just(a - 1), st.integers(1, a - 1)))
    k = draw(st.one_of(st.sampled_from([0, 1, 2, 300]), st.integers(0, 300)))
    f = draw(st.one_of(st.sampled_from([1, 2, 1000]), st.integers(1, 1000)))

    name_max = draw(st.sampled_from([1, 2, 3, 20]))
    pool = draw(st.lists(
        st.text(alphabet=LETTERS, min_size=1, max_size=name_max),
        min_size=2, max_size=8, unique=True,
    ))

    mode = draw(st.sampled_from(["random", "all_trans", "no_trans", "same_route"]))
    trips = []
    prev = None
    if mode == "same_route":
        # heavy-duplicate structural edge: every trip on ONE route, all
        # transshipments after the first -> one big c_r for card thresholds.
        u, v = pool[0], pool[1]
        for i in range(n):
            trips.append((u, v) if i % 2 == 0 else (v, u))
    else:
        for i in range(n):
            if i == 0:
                s = draw(st.sampled_from(pool))
            elif mode == "all_trans":            # every step transships
                s = prev
            elif mode == "no_trans":             # no step transships
                s = draw(st.sampled_from([x for x in pool if x != prev]))
            else:                                # random mixture
                if draw(st.booleans()):
                    s = prev
                else:
                    s = draw(st.sampled_from(pool))
            t = draw(st.sampled_from([x for x in pool if x != s]))
            trips.append((s, t))
            prev = t
    return n, a, b, k, f, trips


@st.composite
def make_input(draw):
    n, a, b, k, f, trips = draw(_params())
    return _build(n, a, b, k, f, trips)


@st.composite
def make_input_k0(draw):
    n, a, b, k, f, trips = draw(_params())
    return _build(n, a, b, 0, f, trips)          # no cards allowed


@st.composite
def make_input_unlimited(draw):
    n, a, b, k, f, trips = draw(_params())
    _, route = _base_costs(a, b, trips)
    nr = len(route)
    choice = draw(st.sampled_from(["exact", "plus1", "max"]))
    if choice == "exact":
        k = nr                                   # boundary: k == #routes
    elif choice == "plus1":
        k = min(300, nr + 1)
    else:
        k = 300
    return _build(n, a, b, k, f, trips)


# ----------------------------------------------------------------------------
# tests
# ----------------------------------------------------------------------------
@given(make_input())
@settings(max_examples=50, deadline=None)
def test_format_and_bounds(stdin):
    # output must be a single non-negative integer
    ans = _out(run_candidate(stdin))
    assert ans >= 0, "answer must be non-negative, got %d" % ans

    n, a, b, k, f, trips = _parse_raw(stdin)
    total, route = _base_costs(a, b, trips)
    # upper bound: buying 0 cards is always feasible (k >= 0)
    upper = total
    # lower bound: cost with UNLIMITED cards is a relaxation of the k-limited
    # problem, so it can only be cheaper -> valid lower bound for any k.
    lower = sum(min(c, f) for c in route.values())
    assert ans <= upper, "answer %d exceeds no-card cost %d" % (ans, upper)
    assert ans >= lower, "answer %d below unlimited-card cost %d" % (ans, lower)


@given(make_input_k0())
@settings(max_examples=35, deadline=None)
def test_k_zero_is_full_base_cost(stdin):
    # k == 0 -> no cards allowed -> answer is exactly the sum of base costs.
    ans = _out(run_candidate(stdin))
    _, a, b, _, _, trips = _parse_raw(stdin)
    total, _ = _base_costs(a, b, trips)
    assert ans == total, "k=0 answer %d != base total %d" % (ans, total)


@given(make_input_unlimited())
@settings(max_examples=35, deadline=None)
def test_unlimited_cards_exact(stdin):
    # k >= #routes -> each route is decided independently: pay min(c_r, f).
    ans = _out(run_candidate(stdin))
    _, a, b, _, f, trips = _parse_raw(stdin)
    _, route = _base_costs(a, b, trips)
    expected = sum(min(c, f) for c in route.values())
    assert ans == expected, "unlimited-card answer %d != %d" % (ans, expected)


@given(make_input())
@settings(max_examples=18, deadline=None)
def test_monotone_in_k(stdin):
    # more travel cards allowed can never increase the cost.
    n, a, b, k, f, trips = _parse_raw(stdin)
    v_lo = _out(run_candidate(_build(n, a, b, 0, f, trips)))
    v_hi = _out(run_candidate(_build(n, a, b, 300, f, trips)))
    assert v_hi <= v_lo, "cost rose with more cards: k=300 %d > k=0 %d" % (v_hi, v_lo)


@given(make_input())
@settings(max_examples=18, deadline=None)
def test_monotone_in_f(stdin):
    # a more expensive card price can never decrease the cost.
    n, a, b, k, f, trips = _parse_raw(stdin)
    v_cheap = _out(run_candidate(_build(n, a, b, k, 1, trips)))
    v_dear = _out(run_candidate(_build(n, a, b, k, 1000, trips)))
    assert v_dear >= v_cheap, "cost fell with pricier cards: f=1000 %d < f=1 %d" % (v_dear, v_cheap)