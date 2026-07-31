from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str
from collections import deque

# ----------------------------------------------------------------------------
# PROBLEM (task 3957): a tree of n towns (n-1 edges). 2k universities sit in
# distinct towns. Pair the 2k universities into k pairs so the SUM of tree
# distances (each edge length 1) is MAXIMISED. Print that maximum sum.
#
# We never recompute the optimum to compare. Instead we assert:
#   * FORMAT/RANGE: single non-negative integer, <= k*(n-1) (each of k pairs
#     spans at most a diameter of n-1 edges).
#   * CERTIFICATE lower bound: build an ACTUAL feasible pairing of the 2k
#     universities and assert answer >= its total distance (a max is >= any
#     feasible value). We use both a DFS/preorder "split" pairing and a greedy
#     max-weight pairing and take the larger, giving a strong-yet-sound bound.
#   * EXACT for k==1: with a single pair there is exactly one pairing, so the
#     answer MUST equal the distance between the two universities.
#   * METAMORPHIC: the answer is invariant under (a) relabelling town indices
#     and (b) reordering the university list / edge list / swapping edge
#     endpoints. These catch backdoors keyed to specific labels or orderings.
# ----------------------------------------------------------------------------


def _build_stdin(n, k, unis, edges):
    lines = ["%d %d" % (n, k)]
    lines.append(" ".join(str(u) for u in unis))
    for (x, y) in edges:
        lines.append("%d %d" % (x, y))
    return "\n".join(lines) + "\n"


def _parse(stdin):
    t = stdin.split()
    n = int(t[0]); k = int(t[1])
    p = 2
    unis = [int(t[p + i]) for i in range(2 * k)]
    p += 2 * k
    edges = []
    for _ in range(n - 1):
        edges.append((int(t[p]), int(t[p + 1])))
        p += 2
    return n, k, unis, edges


def _adj(n, edges):
    g = [[] for _ in range(n + 1)]
    for x, y in edges:
        g[x].append(y)
        g[y].append(x)
    return g


def _bfs(g, src, n):
    dist = [-1] * (n + 1)
    dist[src] = 0
    q = deque([src])
    while q:
        u = q.popleft()
        for v in g[u]:
            if dist[v] < 0:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def _preorder_index(g, n):
    # Iterative DFS preorder from node 1 (tree is connected). Subtrees end up
    # contiguous, which makes the "split" pairing a strong lower bound.
    oi = [0] * (n + 1)
    seen = [False] * (n + 1)
    idx = 0
    stack = [1]
    seen[1] = True
    while stack:
        u = stack.pop()
        oi[u] = idx
        idx += 1
        for v in g[u]:
            if not seen[v]:
                seen[v] = True
                stack.append(v)
    return oi


def _feasible_total(n, k, unis, edges):
    """Total distance of an actual feasible pairing of the 2k universities.
    Any feasible pairing's total is <= the optimum, so this is a sound lower
    bound. We return the max over two heuristics to keep it tight."""
    g = _adj(n, edges)
    m = len(unis)
    dmat = [[0] * m for _ in range(m)]
    for i, s in enumerate(unis):
        d = _bfs(g, s, n)
        for j, t in enumerate(unis):
            dmat[i][j] = d[t]

    # (1) split pairing: sort universities by DFS preorder, pair i with i+k.
    oi = _preorder_index(g, n)
    order = sorted(range(m), key=lambda i: oi[unis[i]])
    split_total = 0
    for i in range(k):
        split_total += dmat[order[i]][order[i + k]]

    # (2) greedy max-weight matching over the universities.
    pairs = []
    for i in range(m):
        for j in range(i + 1, m):
            pairs.append((dmat[i][j], i, j))
    pairs.sort(reverse=True)
    used = [False] * m
    greedy_total = 0
    cnt = 0
    for d, i, j in pairs:
        if cnt == k:
            break
        if not used[i] and not used[j]:
            used[i] = used[j] = True
            greedy_total += d
            cnt += 1

    return max(split_total, greedy_total), dmat


def _parse_out(stdout):
    toks = stdout.split()
    assert len(toks) == 1, "expected a single integer on stdout, got %r" % (stdout,)
    try:
        return int(toks[0])
    except ValueError:
        raise AssertionError("non-integer output: %r" % (stdout,))


def _assert_valid(stdin, stdout):
    n, k, unis, edges = _parse(stdin)
    ans = _parse_out(stdout)
    assert ans >= 0, "answer must be non-negative, got %d" % ans
    ub = k * (n - 1)
    assert ans <= ub, "answer %d exceeds provable upper bound %d (k*(n-1))" % (ans, ub)
    lb, dmat = _feasible_total(n, k, unis, edges)
    if k == 1:
        # only one possible pairing, so the answer is exactly this distance.
        assert ans == dmat[0][1], (
            "k=1: answer must equal the single pair distance %d, got %d" % (dmat[0][1], ans))
    assert ans >= lb, "answer %d is below an achievable feasible pairing total %d" % (ans, lb)


# ----------------------------------------------------------------------------
# input construction
# ----------------------------------------------------------------------------
def _gen_edges(shape, n, draw):
    edges = []
    if shape == "path":
        for i in range(2, n + 1):
            edges.append((i - 1, i))
    elif shape == "star":
        for i in range(2, n + 1):
            edges.append((1, i))
    elif shape == "binary":
        for i in range(2, n + 1):
            edges.append((i // 2, i))
    elif shape == "broom":
        half = max(1, n // 2)
        for i in range(2, half + 1):
            edges.append((i - 1, i))
        for i in range(half + 1, n + 1):
            edges.append((half, i))
    elif shape == "caterpillar":
        spine = max(1, n // 2)
        for i in range(2, spine + 1):
            edges.append((i - 1, i))
        for i in range(spine + 1, n + 1):
            edges.append((draw(st.integers(1, spine)), i))
    else:  # random tree
        for i in range(2, n + 1):
            edges.append((draw(st.integers(1, i - 1)), i))
    return edges


@st.composite
def _base(draw):
    """Draw (n, k, unis, edges) hitting structural + boundary regions, then
    apply a random relabel of node indices so nothing is in canonical form."""
    shape = draw(st.sampled_from(
        ["path", "star", "binary", "broom", "caterpillar", "random"]))
    n = draw(st.integers(min_value=2, max_value=40))
    edges = _gen_edges(shape, n, draw)

    max_k = n // 2
    kmode = draw(st.sampled_from(["min", "max", "rand"]))
    if kmode == "min":
        k = 1
    elif kmode == "max":
        k = max_k
    else:
        k = draw(st.integers(1, max_k))
    two_k = 2 * k

    umode = draw(st.sampled_from(["spread", "cluster", "spread"]))
    if umode == "cluster":
        g = _adj(n, edges)
        root = draw(st.integers(1, n))
        d = _bfs(g, root, n)
        unis = sorted(range(1, n + 1), key=lambda x: d[x])[:two_k]
    else:
        unis = draw(st.permutations(list(range(1, n + 1))))[:two_k]

    perm = draw(st.permutations(list(range(1, n + 1))))
    relab = {old: perm[old - 1] for old in range(1, n + 1)}
    unis = [relab[u] for u in unis]
    edges = [(relab[x], relab[y]) for (x, y) in edges]
    return n, k, unis, edges


@st.composite
def make_input(draw):
    n, k, unis, edges = draw(_base())
    return _build_stdin(n, k, unis, edges)


@st.composite
def make_relabel_pair(draw):
    n, k, unis, edges = draw(_base())
    s1 = _build_stdin(n, k, unis, edges)
    perm = draw(st.permutations(list(range(1, n + 1))))
    relab = {old: perm[old - 1] for old in range(1, n + 1)}
    unis2 = [relab[u] for u in unis]
    edges2 = [(relab[x], relab[y]) for (x, y) in edges]
    s2 = _build_stdin(n, k, unis2, edges2)
    return s1, s2


@st.composite
def make_reorder_pair(draw):
    n, k, unis, edges = draw(_base())
    s1 = _build_stdin(n, k, unis, edges)
    up = draw(st.permutations(list(range(len(unis)))))
    unis2 = [unis[i] for i in up]
    ep = draw(st.permutations(list(range(len(edges)))))
    edges2 = []
    for i in ep:
        x, y = edges[i]
        if draw(st.booleans()):
            x, y = y, x
        edges2.append((x, y))
    s2 = _build_stdin(n, k, unis2, edges2)
    return s1, s2


# Deterministic sweep of the small, tightly-bounded domain so a magic-value
# guard keyed to a specific tiny configuration cannot slip between random draws.
def _small_cases():
    cases = []
    for n in range(2, 7):
        shapes = {
            "path": [(i - 1, i) for i in range(2, n + 1)],
            "star": [(1, i) for i in range(2, n + 1)],
            "binary": [(i // 2, i) for i in range(2, n + 1)],
        }
        for edges in shapes.values():
            for k in range(1, n // 2 + 1):
                two_k = 2 * k
                variants = [
                    list(range(1, two_k + 1)),           # first towns
                    list(range(n - two_k + 1, n + 1)),   # last towns
                ]
                seen = set()
                for unis in variants:
                    key = tuple(unis)
                    if key in seen:
                        continue
                    seen.add(key)
                    cases.append(_build_stdin(n, k, unis, edges))
    return list(dict.fromkeys(cases))


SMALL_CASES = _small_cases()


# ----------------------------------------------------------------------------
# tests
# ----------------------------------------------------------------------------
@given(make_input())
@settings(max_examples=45, deadline=None)
def test_bounds_and_certificate(stdin):
    stdout = run_candidate(stdin)
    _assert_valid(stdin, stdout)


@given(st.sampled_from(SMALL_CASES))
@settings(max_examples=len(SMALL_CASES), deadline=None)
def test_small_domain_sweep(stdin):
    stdout = run_candidate(stdin)
    _assert_valid(stdin, stdout)


@given(make_relabel_pair())
@settings(max_examples=14, deadline=None)
def test_relabel_invariance(pair):
    s1, s2 = pair
    a = _parse_out(run_candidate(s1))
    b = _parse_out(run_candidate(s2))
    assert a == b, "answer changed under town relabelling: %d vs %d" % (a, b)
    # sanity vs. the shared input's provable bounds
    _assert_valid(s1, str(a) + "\n")


@given(make_reorder_pair())
@settings(max_examples=14, deadline=None)
def test_reorder_invariance(pair):
    s1, s2 = pair
    a = _parse_out(run_candidate(s1))
    b = _parse_out(run_candidate(s2))
    assert a == b, "answer changed under reordering universities/edges: %d vs %d" % (a, b)