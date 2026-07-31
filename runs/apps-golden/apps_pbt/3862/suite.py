import math
from hypothesis import given, strategies as st, settings
from harness import run_candidate  # run_candidate(stdin: str) -> stdout: str

# ---------------------------------------------------------------------------
# PROBLEM MODEL (no solving of the optimum, only sound invariants)
#
# We use c_i >= 0 integer liters of coke type i (unlimited supply). With
# b_i = a_i - n, the target concentration n/1000 is reached iff
#     sum(b_i * c_i) == 0   and   sum(c_i) >= 1.
# We must output the minimal sum(c_i), or -1 if impossible.
#
# Sound facts used below (NONE require computing the optimum):
#  * Feasible  <=>  min(a) <= n <= max(a).
#      - if n < min(a): every b_i > 0, positive sum can never be 0.
#      - if n > max(a): every b_i < 0, negative sum can never be 0.
#      - otherwise either some a_i == n, or there is a_i < n < a_j and a
#        balancing mixture exists.
#  * answer == 1  <=>  some a_i == n  (one liter yields exactly a_i).
#  * feasible and no a_i == n  =>  answer >= 2 (need >=1 above and >=1 below).
#  * For any positive excess x=a_i-n>0 and deficit y=n-a_j>0, using y/g liters
#    of type i and x/g liters of type j (g=gcd(x,y)) balances exactly, so
#    answer <= (x+y)/g. Min over any set of such pairs is a valid UPPER bound.
#    (It is only an upper bound: 3-value combos, e.g. +7,-3,-4 -> 3 liters,
#    can beat every pair, so we NEVER use it as a lower bound.)
# ---------------------------------------------------------------------------


def build(n, a):
    return f"{n} {len(a)}\n" + " ".join(str(int(x)) for x in a) + "\n"


def parse_stdin(stdin):
    lines = stdin.split("\n")
    n, _k = map(int, lines[0].split())
    a = list(map(int, lines[1].split()))
    return n, a


def parse_answer(stdout):
    s = stdout.strip()
    assert s != "", f"empty output: {stdout!r}"
    parts = s.split()
    assert len(parts) == 1, f"expected a single integer, got {stdout!r}"
    try:
        v = int(parts[0])
    except ValueError:
        raise AssertionError(f"non-integer output: {stdout!r}")
    assert v == -1 or v >= 1, f"answer must be -1 or a positive integer, got {v}"
    return v


def pair_upper_bound(n, a, cap=500):
    # A SOUND upper bound on the optimum built from achievable 2-type mixtures.
    # Capping the value lists only drops candidate pairs; the min over the
    # remaining pairs is still an achievable (hence >= optimum) bound.
    pos = sorted({x - n for x in a if x > n})[:cap]
    neg = sorted({n - x for x in a if x < n})[:cap]
    best = None
    for x in pos:
        for y in neg:
            t = (x + y) // math.gcd(x, y)
            if best is None or t < best:
                best = t
    return best


def check_full(n, a, stdout):
    v = parse_answer(stdout)
    lo, hi = min(a), max(a)
    feasible = lo <= n <= hi
    exact = any(x == n for x in a)
    if not feasible:
        assert v == -1, f"n={n} outside [{lo},{hi}] is infeasible; must print -1, got {v}"
        return v
    assert v != -1, f"feasible input (n={n} in [{lo},{hi}]) must not return -1"
    if exact:
        assert v == 1, f"a type has concentration n={n}; answer must be 1, got {v}"
    else:
        assert v >= 2, f"no type equals n={n}; answer must be >=2, got {v}"
        ub = pair_upper_bound(n, a)
        if ub is not None:
            assert v <= ub, f"answer {v} exceeds achievable upper bound {ub} (n={n})"
    return v


def _clamp(x):
    return max(0, min(1000, x))


# ---------------------------------------------------------------------------
# GENERATOR: deliberately manufactures the rare trigger regions.
# ---------------------------------------------------------------------------
@st.composite
def make_input(draw):
    mode = draw(st.integers(0, 8))
    n = draw(st.one_of(
        st.sampled_from([0, 1, 2, 499, 500, 501, 998, 999, 1000]),
        st.integers(0, 1000),
    ))

    def edge_val():
        return draw(st.one_of(
            st.integers(0, 1000),
            st.sampled_from([0, 1, 2, 999, 1000]),
            st.sampled_from([_clamp(n - 1), n, _clamp(n + 1)]),
        ))

    if mode == 0:  # general small mixture, edge-biased values
        k = draw(st.integers(2, 20))
        a = [edge_val() for _ in range(k)]
    elif mode == 1:  # guarantee an exact match => answer must be 1
        k = draw(st.integers(1, 15))
        a = [edge_val() for _ in range(k)] + [n]
    elif mode == 2:  # infeasible: every type strictly above n
        n = draw(st.integers(0, 999))
        k = draw(st.integers(1, 15))
        a = [draw(st.integers(n + 1, 1000)) for _ in range(k)]
    elif mode == 3:  # infeasible: every type strictly below n
        n = draw(st.integers(1, 1000))
        k = draw(st.integers(1, 15))
        a = [draw(st.integers(0, n - 1)) for _ in range(k)]
    elif mode == 4:  # three-value structure: optimum 3, pair bound much larger
        n = draw(st.integers(40, 960))
        q = draw(st.integers(1, 20))
        r = draw(st.integers(1, 20))
        a = [n + q + r, n - q, n - r]
        for _ in range(draw(st.integers(0, 5))):  # noise positives, still feasible
            a.append(draw(st.integers(n + 1, 1000)))
    elif mode == 5:  # extremes: 0 and 1000 always present + noise
        a = [0, 1000] + [edge_val() for _ in range(draw(st.integers(0, 10)))]
    elif mode == 6:  # all-equal: feasible (ans 1) only if n equals the value
        c = draw(st.integers(0, 1000))
        a = [c] * draw(st.integers(1, 15))
    elif mode == 7:  # near-threshold: values at n-1 / n+1 straddling n
        choices = [_clamp(n - 1), _clamp(n + 1)]
        a = [draw(st.sampled_from(choices)) for _ in range(draw(st.integers(1, 10)))]
        if draw(st.booleans()):
            a.append(n)
    else:  # mode 8: pure 2-value pair (optimum == pair bound exactly)
        n = draw(st.integers(1, 999))
        x = draw(st.integers(1, min(80, 1000 - n)))
        y = draw(st.integers(1, min(80, n)))
        a = [n + x, n - y]

    return build(n, a)


# Deterministic sweep of tightly-bounded structured cases so a magic-value
# guard cannot slip through gaps between random samples.
CASES = [
    (0, (0,)),
    (0, (1,)),
    (0, (0, 1000)),
    (0, (5, 7, 9)),
    (0, (0, 0, 0)),
    (1000, (1000,)),
    (1000, (999,)),
    (1000, (0, 1000)),
    (1000, (1, 2, 3)),
    (1000, (1000, 1000)),
    (500, (1000, 5, 5)),          # -> 199
    (400, (100, 300, 450, 500)),  # -> 2
    (50, (100, 25)),              # -> 3
    (100, (107, 97, 96)),         # 3-value optimum 3, pair bound 10
    (500, (500,)),                # -> 1
    (500, (499, 501)),            # -> 2
    (2, (1, 4)),                  # -> 3
    (1, (0, 1000)),               # -> 1000
    (500, (600, 700, 800)),       # infeasible
    (500, (100, 200, 300)),       # infeasible
    (500, (400, 400, 400)),       # infeasible
    (500, (400, 600)),            # -> 2
    (500, (0, 1000)),             # -> 2
    (3, (2, 5)),                  # -> 3
    (999, (1000, 1)),             # -> 999
    (1, (2, 0)),                  # -> 2
]


@st.composite
def make_edge_input(draw):
    n, a = draw(st.sampled_from(CASES))
    return build(n, list(a))


# ---------------------------------------------------------------------------
# TESTS
# ---------------------------------------------------------------------------
@given(make_input())
@settings(max_examples=60, deadline=None)
def test_bounds_and_feasibility(stdin):
    n, a = parse_stdin(stdin)
    check_full(n, a, run_candidate(stdin))


@given(make_edge_input())
@settings(max_examples=60, deadline=None)
def test_deterministic_edges(stdin):
    n, a = parse_stdin(stdin)
    check_full(n, a, run_candidate(stdin))


@given(make_input())
@settings(max_examples=25, deadline=None)
def test_permutation_and_duplicate_invariance(stdin):
    # Answer depends only on the SET of distinct concentrations, not order or
    # multiplicity (supply is unlimited). Reverse (a permutation) and duplicate
    # an existing value -> answer must be identical.
    n, a = parse_stdin(stdin)
    v1 = check_full(n, a, run_candidate(stdin))
    a2 = list(reversed(a)) + [a[0]]
    v2 = parse_answer(run_candidate(build(n, a2)))
    assert v1 == v2, f"reordering/duplicating types changed answer: {v1} vs {v2}"


@given(make_input())
@settings(max_examples=25, deadline=None)
def test_concentration_symmetry(stdin):
    # b_i -> -b_i under a_i -> 1000-a_i, n -> 1000-n. Reaching sum 0 is
    # symmetric under negation, so the minimum is invariant.
    n, a = parse_stdin(stdin)
    v1 = check_full(n, a, run_candidate(stdin))
    n2 = 1000 - n
    a2 = [1000 - x for x in a]
    v2 = check_full(n2, a2, run_candidate(build(n2, a2)))
    assert v1 == v2, f"complement symmetry violated: {v1} vs {v2}"


@given(make_input())
@settings(max_examples=20, deadline=None)
def test_add_type_relations(stdin):
    n, a = parse_stdin(stdin)
    v1 = check_full(n, a, run_candidate(stdin))
    # Adding a type whose concentration equals n forces the answer to be 1.
    v_match = parse_answer(run_candidate(build(n, a + [n])))
    assert v_match == 1, f"adding a type equal to n must give answer 1, got {v_match}"
    # Adding any type cannot break feasibility nor increase the minimum.
    if v1 != -1:
        e = (n + 137) % 1001
        v_more = parse_answer(run_candidate(build(n, a + [e])))
        assert v_more != -1, "adding a type turned a feasible instance infeasible"
        assert v_more <= v1, f"adding a type increased the minimum: {v1} -> {v_more}"