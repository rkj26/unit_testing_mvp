from hypothesis import given, strategies as st, settings, example
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

# ---------------------------------------------------------------------------
# PROBLEM MODEL (derived from spec only)
# ---------------------------------------------------------------------------
# n rooms (state r_i in {0,1}, 1 = unlocked), m switches. Each room is controlled
# by EXACTLY TWO switches. Toggling a switch flips every room it controls.
# We may toggle any subset of switches; let s_j in {0,1} = "switch j toggled".
# Final state of room i = r_i XOR s_a XOR s_b  (a,b = the two switches on room i).
# We need every room unlocked: r_i XOR s_a XOR s_b = 1  <=>  s_a XOR s_b = 1 - r_i.
# So this is a system of GF(2) parity constraints on the "switch graph"
# (nodes = switches, one edge per room with weight c_i = 1 - r_i between its two
# controlling switches). Answer is "YES" iff that system is consistent
# (no cycle whose weight-sum is odd), else "NO".
#
# We NEVER solve the general instance in the suite. Instead we:
#   * construct instances with a KNOWN satisfying assignment  -> must be YES
#   * construct instances with a built-in contradiction        -> must be NO
#   * exploit relabeling invariance (isomorphism)              -> metamorphic
#   * sweep tiny hand-verified cases                           -> deterministic
# All of these are certificates / invariants, not recomputation of the optimum.
# ---------------------------------------------------------------------------


def to_stdin(n, m, r_list, pairs):
    """Build a valid STDIN string.

    pairs[i] = (a, b): the two DISTINCT (1-based) switches controlling room i+1.
    Guarantees the spec invariant: every room appears in exactly two switch
    lists, and each switch lists distinct room numbers.
    """
    switch_rooms = [[] for _ in range(m)]
    for idx, (a, b) in enumerate(pairs):
        room = idx + 1
        switch_rooms[a - 1].append(room)
        switch_rooms[b - 1].append(room)
    out = [("%d %d" % (n, m)), (" ".join(str(x) for x in r_list))]
    for rooms in switch_rooms:
        if rooms:
            out.append(str(len(rooms)) + " " + " ".join(str(x) for x in rooms))
        else:
            out.append("0")
    return "\n".join(out) + "\n"


def draw_pairs(draw, n, m, cluster):
    """Draw n (a,b) switch pairs with a != b, both in [1, hi].

    When cluster=True the switches are drawn from a tiny pool so that parallel
    edges / cycles (where the consistency logic actually matters) appear often.
    """
    if cluster:
        hi = draw(st.integers(2, min(m, 6)))
    else:
        hi = m
    pairs = []
    for _ in range(n):
        a = draw(st.integers(1, hi))
        off = draw(st.integers(1, hi - 1))
        b = ((a - 1 + off) % hi) + 1
        pairs.append((a, b))
    return pairs


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
@st.composite
def gen_random(draw):
    n = draw(st.integers(2, 120))
    m = draw(st.integers(2, 120))
    r_list = [draw(st.integers(0, 1)) for _ in range(n)]
    pairs = draw_pairs(draw, n, m, draw(st.booleans()))
    return (n, m, r_list, pairs)


@st.composite
def gen_yes(draw):
    # Pick an arbitrary switch-toggle assignment s, then DERIVE r so that s is a
    # valid solution => the instance is guaranteed satisfiable => YES.
    n = draw(st.integers(2, 200))
    m = draw(st.integers(2, 200))
    s = [draw(st.integers(0, 1)) for _ in range(m)]
    pairs = draw_pairs(draw, n, m, draw(st.booleans()))
    r_list = [1 ^ s[a - 1] ^ s[b - 1] for (a, b) in pairs]
    return (n, m, r_list, pairs)


@st.composite
def gen_no(draw):
    # Embed a hard contradiction: rooms 0 and 1 are BOTH on switch pair (1,2) but
    # with different states -> s_1 XOR s_2 would have to equal both 0 and 1.
    # A single contradictory constraint forces the whole instance to be NO,
    # regardless of everything else.
    n = draw(st.integers(2, 200))
    m = draw(st.integers(2, 200))
    r_list = [draw(st.integers(0, 1)) for _ in range(n)]
    pairs = draw_pairs(draw, n, m, draw(st.booleans()))
    pairs[0] = (1, 2)
    pairs[1] = (1, 2)
    r_list[0] = 0
    r_list[1] = 1
    return (n, m, r_list, pairs)


@st.composite
def gen_metamorphic(draw):
    n = draw(st.integers(2, 100))
    m = draw(st.integers(2, 100))
    r_list = [draw(st.integers(0, 1)) for _ in range(n)]
    pairs = draw_pairs(draw, n, m, draw(st.booleans()))
    switch_perm = draw(st.permutations(list(range(1, m + 1))))
    room_perm = draw(st.permutations(list(range(1, n + 1))))
    return (n, m, r_list, pairs, switch_perm, room_perm)


def big_yes(n=100000):
    # Single even cycle 1-2-...-n-1; s all 0 => r all 1 is a valid solution.
    # Hits the MAX bound n=m=100000 exactly (each switch controls exactly 2 rooms).
    m = n
    pairs = [(i, i + 1 if i < n else 1) for i in range(1, n + 1)]
    r_list = [1] * n
    return (n, m, r_list, pairs)


def big_no(n=100000):
    # MAX n with MIN m=2: every room on pair (1,2); rooms 0,1 differ -> NO.
    m = 2
    pairs = [(1, 2)] * n
    r_list = [0] * n
    r_list[1] = 1
    return (n, m, r_list, pairs)


# ---------------------------------------------------------------------------
# Deterministic sweep of tiny, fully hand-verified instances.
# ---------------------------------------------------------------------------
SMALL_CASES = [
    # n=2,m=2: both rooms forced onto pair (1,2). YES iff the two states match.
    (2, 2, [0, 0], [(1, 2), (1, 2)], "YES"),
    (2, 2, [1, 1], [(1, 2), (1, 2)], "YES"),
    (2, 2, [0, 1], [(1, 2), (1, 2)], "NO"),
    (2, 2, [1, 0], [(1, 2), (1, 2)], "NO"),
    # n=3,m=2: all three rooms on pair (1,2). YES iff all states equal.
    (3, 2, [0, 0, 0], [(1, 2), (1, 2), (1, 2)], "YES"),
    (3, 2, [1, 1, 1], [(1, 2), (1, 2), (1, 2)], "YES"),
    (3, 2, [1, 0, 1], [(1, 2), (1, 2), (1, 2)], "NO"),
    (3, 2, [1, 1, 0], [(1, 2), (1, 2), (1, 2)], "NO"),
    # Triangle (odd cycle). Consistent iff sum(r) is odd.
    (3, 3, [1, 0, 0], [(1, 2), (2, 3), (1, 3)], "YES"),
    (3, 3, [1, 1, 1], [(1, 2), (2, 3), (1, 3)], "YES"),
    (3, 3, [0, 0, 0], [(1, 2), (2, 3), (1, 3)], "NO"),
    (3, 3, [1, 1, 0], [(1, 2), (2, 3), (1, 3)], "NO"),
    # Acyclic (tree) constraint graph -> always consistent -> YES for any r.
    (2, 3, [0, 0], [(1, 2), (1, 3)], "YES"),
    (2, 3, [1, 0], [(1, 2), (1, 3)], "YES"),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@given(gen_random())
@settings(max_examples=40, deadline=None)
def test_format_and_range(data):
    n, m, r_list, pairs = data
    out = run_candidate(to_stdin(n, m, r_list, pairs))
    ans = out.strip()
    assert ans in ("YES", "NO"), "output must be exactly YES or NO, got %r" % (out,)


@given(gen_yes())
@example(big_yes())
@settings(max_examples=50, deadline=None)
def test_yes_certificate(data):
    n, m, r_list, pairs = data
    out = run_candidate(to_stdin(n, m, r_list, pairs)).strip()
    assert out == "YES", (
        "instance has a known satisfying toggle-set (solvable by construction) "
        "so answer must be YES, got %r" % (out,)
    )


@given(gen_no())
@example(big_no())
@settings(max_examples=50, deadline=None)
def test_no_certificate(data):
    n, m, r_list, pairs = data
    out = run_candidate(to_stdin(n, m, r_list, pairs)).strip()
    assert out == "NO", (
        "instance contains two rooms on the same switch pair with opposite "
        "states (unsatisfiable by construction) so answer must be NO, got %r"
        % (out,)
    )


@given(st.just(0))
@settings(max_examples=1, deadline=None)
def test_small_deterministic_sweep(_):
    for (n, m, r_list, pairs, expected) in SMALL_CASES:
        out = run_candidate(to_stdin(n, m, r_list, pairs)).strip()
        assert out == expected, (
            "hand-verified case n=%d m=%d r=%r pairs=%r expected %s got %r"
            % (n, m, r_list, pairs, expected, out)
        )


@given(gen_metamorphic())
@settings(max_examples=18, deadline=None)
def test_metamorphic_relabel(data):
    n, m, r_list, pairs, switch_perm, room_perm = data
    base = run_candidate(to_stdin(n, m, r_list, pairs)).strip()
    # Relabel BOTH switches and rooms (a graph isomorphism); the answer, which
    # depends only on the constraint graph up to isomorphism, must be unchanged.
    r2 = [0] * n
    pairs2 = [None] * n
    for i in range(n):
        a, b = pairs[i]
        na, nb = switch_perm[a - 1], switch_perm[b - 1]
        new_room = room_perm[i]  # 1-based new label for old room i+1
        r2[new_room - 1] = r_list[i]
        pairs2[new_room - 1] = (na, nb)
    other = run_candidate(to_stdin(n, m, r2, pairs2)).strip()
    assert base in ("YES", "NO"), "base output not YES/NO: %r" % (base,)
    assert other == base, (
        "relabeling switches and rooms (isomorphic instance) changed the "
        "answer: base=%r relabeled=%r" % (base, other)
    )