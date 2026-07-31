import random
import itertools
import heapq

from hypothesis import given, strategies as st, settings, HealthCheck
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str


# ---------------------------------------------------------------------------
# Problem: tree with n nodes, edges start at 0. An operation picks two DISTINCT
# leaves and adds a real x to every edge on the simple path between them.
# Question: can EVERY real edge-configuration be achieved?
#
# The reachable set is the linear span of all leaf-to-leaf path vectors.
# THEOREM (provable, O(n) to check): answer is "YES" iff the tree has NO vertex
# of degree exactly 2, otherwise "NO".
#   - A degree-2 vertex v (edges e1,e2) is never a path endpoint (not a leaf),
#     so every leaf-path contains BOTH e1,e2 or neither => value(e1)==value(e2)
#     in every reachable config => configs with e1!=e2 are unreachable => "NO".
#   - No degree-2 vertex => the path vectors span R^(n-1) => "YES".
# Matches all four provided examples. This is a closed-form characterization
# (a linear-time certificate, not a heuristic solver), so asserting the exact
# answer is SOUND and is the strongest possible check for this decision problem.
# ---------------------------------------------------------------------------


def _edges_to_stdin(n, edges):
    lines = [str(n)]
    for u, v in edges:
        lines.append("{} {}".format(u, v))
    return "\n".join(lines) + "\n"


def _expected(n, edges):
    deg = [0] * (n + 1)
    for u, v in edges:
        deg[u] += 1
        deg[v] += 1
    for i in range(1, n + 1):
        if deg[i] == 2:
            return "NO"
    return "YES"


def _norm(out):
    return out.strip().upper()


def _parse(stdin):
    toks = stdin.split()
    n = int(toks[0])
    rest = toks[1:]
    edges = []
    for i in range(0, len(rest) - 1, 2):
        edges.append((int(rest[i]), int(rest[i + 1])))
    return n, edges


def _finalize(n, edges, rng, relabel_prob=0.7):
    """Optionally relabel node ids and shuffle edge / endpoint order."""
    edges = [tuple(e) for e in edges]
    if rng.random() < relabel_prob:
        perm = list(range(1, n + 1))
        rng.shuffle(perm)
        edges = [(perm[u - 1], perm[v - 1]) for (u, v) in edges]
    rng.shuffle(edges)
    edges = [((v, u) if rng.random() < 0.5 else (u, v)) for (u, v) in edges]
    return _edges_to_stdin(n, edges)


# ---------------- structural builders (edge lists over 1..n) ----------------

def _path(n):
    return [(i, i + 1) for i in range(1, n)]


def _star(n):
    # center=1; n=2 -> single edge (YES), n=3 -> center deg 2 (NO), n>=4 -> YES
    return [(1, i) for i in range(2, n + 1)]


def _cubic(k, rng):
    # start with edge 1-2 (both leaves); each expansion turns a leaf into a
    # degree-3 internal vertex with two fresh leaves -> no vertex is ever of
    # degree exactly 2 => answer YES (min internal degree exactly 3: boundary).
    edges = [(1, 2)]
    leaves = [1, 2]
    nxt = 3
    for _ in range(k):
        leaf = leaves.pop(rng.randrange(len(leaves)))
        c1, c2 = nxt, nxt + 1
        nxt += 2
        edges.append((leaf, c1))
        edges.append((leaf, c2))
        leaves.append(c1)
        leaves.append(c2)
    return nxt - 1, edges


def _subdivided_star(n0, rng):
    # star (center deg n0-1 >= 3, i.e. YES) with ONE edge subdivided -> exactly
    # one degree-2 vertex introduced => must be NO (boundary just past YES/NO).
    edges = [(1, i) for i in range(2, n0 + 1)]
    j = rng.randrange(len(edges))
    u, v = edges.pop(j)
    w = n0 + 1
    edges.append((u, w))
    edges.append((w, v))
    return n0 + 1, edges


def _spider(legs, leglen):
    edges = []
    nxt = 2
    for _ in range(legs):
        prev = 1
        for _ in range(leglen):
            edges.append((prev, nxt))
            prev = nxt
            nxt += 1
    return nxt - 1, edges


def _binary(n):
    # parent(i)=i//2; root has degree 2 when it has 2 children -> exercises a
    # single deep degree-2 vertex among many degree-3 vertices.
    return [(i // 2, i) for i in range(2, n + 1)]


def _random_tree(n, rng):
    mode = rng.choice(["uniform", "path", "star", "mixed"])
    edges = []
    for i in range(2, n + 1):
        if mode == "path":
            p = i - 1
        elif mode == "star":
            p = 1
        elif mode == "uniform":
            p = rng.randint(1, i - 1)
        else:
            p = i - 1 if rng.random() < 0.5 else rng.randint(1, i - 1)
        edges.append((p, i))
    return edges


@st.composite
def make_input(draw):
    seed = draw(st.integers(min_value=0, max_value=2 ** 31 - 1))
    rng = random.Random(seed)
    kind = draw(st.sampled_from([
        "n2", "star3", "path", "star", "cubic",
        "subdiv_star", "spider", "binary", "random",
    ]))

    if kind == "n2":
        n, edges = 2, [(1, 2)]
    elif kind == "star3":
        n, edges = 3, [(1, 2), (1, 3)]
    elif kind == "path":
        n = draw(st.integers(min_value=2, max_value=400))
        edges = _path(n)
    elif kind == "star":
        n = draw(st.integers(min_value=2, max_value=400))
        edges = _star(n)
    elif kind == "cubic":
        k = draw(st.integers(min_value=0, max_value=200))
        n, edges = _cubic(k, rng)
    elif kind == "subdiv_star":
        n0 = draw(st.integers(min_value=4, max_value=300))
        n, edges = _subdivided_star(n0, rng)
    elif kind == "spider":
        legs = draw(st.integers(min_value=2, max_value=6))
        leglen = draw(st.integers(min_value=1, max_value=5))
        n, edges = _spider(legs, leglen)
    elif kind == "binary":
        n = draw(st.integers(min_value=2, max_value=400))
        edges = _binary(n)
    else:  # random
        n = draw(st.integers(min_value=2, max_value=400))
        edges = _random_tree(n, rng)

    return _finalize(n, edges, rng)


# ---------------------------------------------------------------------------
# Test 1: FORMAT / SHAPE -- output is exactly one YES/NO token, plus the exact
# CERTIFICATE (answer is YES iff no vertex has degree 2). The certificate check
# validates the answer against the input in O(n) via a complete, provably
# correct structural characterization.
# ---------------------------------------------------------------------------
@given(make_input())
@settings(max_examples=45, deadline=None)
def test_format_and_certificate(stdin):
    out = _norm(run_candidate(stdin))
    assert out in ("YES", "NO"), "output must be YES/NO, got {!r}".format(out)
    n, edges = _parse(stdin)
    assert len(edges) == n - 1, "input must contain n-1 edges"
    assert out == _expected(n, edges), "answer mismatch on:\n{}".format(stdin)


# ---------------------------------------------------------------------------
# Test 2: METAMORPHIC -- relabeling node ids and reordering edges / endpoints
# must not change the YES/NO answer. Independent of any answer theory.
# ---------------------------------------------------------------------------
@given(make_input())
@settings(max_examples=20, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
def test_metamorphic_relabel(stdin):
    out1 = _norm(run_candidate(stdin))
    n, edges = _parse(stdin)
    rng = random.Random(hash(stdin) & 0x7FFFFFFF)
    perm = list(range(1, n + 1))
    rng.shuffle(perm)
    e2 = [(perm[u - 1], perm[v - 1]) for (u, v) in edges]
    rng.shuffle(e2)
    e2 = [((v, u) if rng.random() < 0.5 else (u, v)) for (u, v) in e2]
    out2 = _norm(run_candidate(_edges_to_stdin(n, e2)))
    assert out1 in ("YES", "NO") and out2 in ("YES", "NO")
    assert out1 == out2, "answer not invariant under relabel/reorder: {} vs {}".format(out1, out2)


# ---------------------------------------------------------------------------
# Test 3: METAMORPHIC / CERTIFICATE -- subdividing any edge inserts a vertex of
# degree exactly 2, so the resulting tree is ALWAYS "NO". Relies only on the
# rigorously proven necessity direction (a degree-2 vertex => unreachable).
# ---------------------------------------------------------------------------
@given(make_input())
@settings(max_examples=25, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
def test_subdivision_forces_no(stdin):
    n, edges = _parse(stdin)
    rng = random.Random((hash(stdin) ^ 0x5DEECE66D) & 0x7FFFFFFF)
    j = rng.randrange(len(edges))
    u, v = edges[j]
    w = n + 1
    new_edges = list(edges)
    new_edges.pop(j)
    new_edges.append((u, w))
    new_edges.append((w, v))
    out = _norm(run_candidate(_edges_to_stdin(n + 1, new_edges)))
    assert out == "NO", "subdivided edge creates a degree-2 vertex; expected NO, got {}".format(out)


# ---------------------------------------------------------------------------
# Test 4: DETERMINISTIC exhaustive sweep of ALL labeled trees on n=2..4 nodes
# (via Prufer sequences) plus curated n=5..7 shapes straddling the YES/NO
# threshold -- catches magic-value guards keyed to specific small structures,
# deterministically covering the whole small bounded domain.
# ---------------------------------------------------------------------------
def _prufer_to_edges(seq, n):
    deg = [1] * (n + 1)
    for x in seq:
        deg[x] += 1
    leaves = [i for i in range(1, n + 1) if deg[i] == 1]
    heapq.heapify(leaves)
    edges = []
    for x in seq:
        leaf = heapq.heappop(leaves)
        edges.append((leaf, x))
        deg[leaf] -= 1
        deg[x] -= 1
        if deg[x] == 1:
            heapq.heappush(leaves, x)
    a = heapq.heappop(leaves)
    b = heapq.heappop(leaves)
    edges.append((a, b))
    return edges


_CURATED = [
    (5, [(1, 2), (2, 3), (3, 4), (4, 5)]),          # path -> NO
    (5, [(1, 2), (1, 3), (1, 4), (1, 5)]),          # star (deg 4) -> YES
    (5, [(1, 2), (1, 3), (1, 4), (2, 5)]),          # example 3 -> NO (deg-2 at 2)
    (6, [(1, 2), (1, 3), (1, 4), (2, 5), (2, 6)]),  # example 4 -> YES
    (6, [(1, 2), (2, 3), (2, 4), (2, 5), (2, 6)]),  # one deg-2 leaf-side -> NO
    (7, [(1, 2), (1, 3), (1, 4), (4, 5), (4, 6), (4, 7)]),   # double star -> YES
    (7, [(1, 2), (2, 3), (1, 4), (4, 5), (1, 6), (6, 7)]),   # spider legs len2 -> NO
    (7, [(1, 2), (1, 3), (1, 4), (4, 5), (5, 6), (5, 7)]),   # subdivided arm -> NO
]


@given(st.just(0))
@settings(max_examples=1, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
def test_small_exhaustive_sweep(_dummy):
    cases = []
    for n in range(2, 5):
        for seq in itertools.product(range(1, n + 1), repeat=n - 2):
            cases.append((n, _prufer_to_edges(list(seq), n)))
    cases.extend(_CURATED)
    for n, edges in cases:
        stdin = _edges_to_stdin(n, edges)
        out = _norm(run_candidate(stdin))
        assert out in ("YES", "NO")
        assert out == _expected(n, edges), \
            "small-sweep mismatch on n={}, edges={}".format(n, edges)


# ---------------------------------------------------------------------------
# Test 5: EXTREME magnitudes combined with degenerate structure (n up to 1e5).
# ---------------------------------------------------------------------------
@given(st.sampled_from([
    ("path", 2), ("path", 3), ("path", 100000),
    ("star", 2), ("star", 4), ("star", 100000),
    ("binary", 100000),
    ("cubic", 99999),
    ("subdiv", 100000),
]))
@settings(max_examples=9, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
def test_extremes(spec):
    kind, N = spec
    rng = random.Random(20260730)
    if kind == "path":
        n, edges = N, _path(N)
    elif kind == "star":
        n, edges = N, _star(N)
    elif kind == "binary":
        n, edges = N, _binary(N)
    elif kind == "cubic":
        n, edges = _cubic((N - 2) // 2, rng)
    else:  # subdiv: huge star with exactly one degree-2 vertex -> NO
        n, edges = _subdivided_star(N - 1, rng)
    stdin = _edges_to_stdin(n, edges)
    out = _norm(run_candidate(stdin))
    assert out in ("YES", "NO"), "output must be YES/NO, got {!r}".format(out)
    assert out == _expected(n, edges), "answer mismatch on extreme n={}".format(n)
