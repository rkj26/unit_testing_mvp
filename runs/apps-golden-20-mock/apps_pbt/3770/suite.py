from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str  (the harness provides this)

# ----------------------------------------------------------------------------
# Problem 3770 recap (spec only):
#   Simple undirected graph, N vertices (A_i cost, B_i value), M edges.
#   Delete zero or more vertices (deleting i costs A_i, removes incident edges).
#   score = sum over connected components of |sum of B_i in the component|.
#   profit = score - (sum of A_i of deleted vertices).  Print max profit.
#
# Constraints: 1<=N<=300, 1<=M<=300, 1<=A_i<=1e6, -1e6<=B_i<=1e6,
#              1<=U_i,V_i<=N, simple graph (no self-loop / multi-edge).
#
# We NEVER recompute the optimum. We use:
#   * CERTIFICATE bounds: any concrete deletion set gives a valid LOWER bound;
#     the triangle inequality gives a valid UPPER bound (sum|B_i|).
#   * METAMORPHIC invariants: negate-B, vertex relabeling, positive scaling,
#     and adding an isolated value-0 vertex.
# ----------------------------------------------------------------------------


def build_input(n, A, B, edges):
    lines = [f"{n} {len(edges)}",
             " ".join(map(str, A)),
             " ".join(map(str, B))]
    lines += [f"{u} {v}" for (u, v) in edges]
    return "\n".join(lines) + "\n"


def parse_answer(stdout):
    t = (stdout or "").strip()
    try:
        return int(t)
    except Exception:
        raise AssertionError(f"output is not a single integer: {stdout!r}")


def parse_stdin(stdin):
    toks = stdin.split()
    idx = 0
    n = int(toks[idx]); idx += 1
    m = int(toks[idx]); idx += 1
    A = [int(toks[idx + i]) for i in range(n)]; idx += n
    B = [int(toks[idx + i]) for i in range(n)]; idx += n
    edges = []
    for _ in range(m):
        u = int(toks[idx]); v = int(toks[idx + 1]); idx += 2
        edges.append((u, v))
    return n, m, A, B, edges


def profit_of(n, A, B, edges, deleted):
    """Exact profit of ONE concrete deletion set (a valid lower bound)."""
    parent = list(range(n + 1))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for u, v in edges:
        if u in deleted or v in deleted:
            continue
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv
    sums = {}
    for i in range(1, n + 1):
        if i in deleted:
            continue
        r = find(i)
        sums[r] = sums.get(r, 0) + B[i - 1]
    score = sum(abs(s) for s in sums.values())
    cost = sum(A[i - 1] for i in deleted)
    return score - cost


# ---------------------------------------------------------------------------
# Graph generator: mixes structural edges (path/star/cycle/complete/matching/
# random) with extreme + boundary A/B magnitudes to manufacture rare regions.
# ---------------------------------------------------------------------------
@st.composite
def graph_data(draw, max_n=12, amax=10 ** 6, bmax=10 ** 6):
    n = draw(st.integers(min_value=2, max_value=max_n))
    all_edges = [(u, v) for u in range(1, n + 1) for v in range(u + 1, n + 1)]
    structure = draw(st.sampled_from(
        ["random", "complete", "path", "star", "cycle", "matching"]))
    if structure == "complete":
        edges = list(all_edges)
    elif structure == "path":
        edges = [(i, i + 1) for i in range(1, n)]
    elif structure == "star":
        edges = [(1, i) for i in range(2, n + 1)]
    elif structure == "cycle":
        edges = [(i, i + 1) for i in range(1, n)] + ([(1, n)] if n >= 3 else [])
    elif structure == "matching":
        edges = [(2 * i - 1, 2 * i) for i in range(1, n // 2 + 1)]
    else:
        edges = draw(st.lists(st.sampled_from(all_edges),
                              min_size=1, max_size=len(all_edges), unique=True))
    edges = sorted(set((min(u, v), max(u, v)) for (u, v) in edges))
    if not edges:
        edges = [(1, 2)]
    # A: min (1), max (amax), and uniform.  B: 0, +/-bmax, and uniform.
    A = [draw(st.one_of(st.just(1), st.just(amax), st.integers(1, amax)))
         for _ in range(n)]
    B = [draw(st.one_of(st.just(0), st.just(bmax), st.just(-bmax),
                        st.integers(-bmax, bmax)))
         for _ in range(n)]
    return (n, A, B, edges)


@st.composite
def make_input(draw):
    n, A, B, edges = draw(graph_data(max_n=12))
    return build_input(n, A, B, edges)


@st.composite
def perm_data(draw, max_n=10):
    n, A, B, edges = draw(graph_data(max_n=max_n))
    perm = draw(st.permutations(list(range(1, n + 1))))
    return (n, A, B, edges, tuple(perm))


@st.composite
def scale_data(draw):
    c = draw(st.integers(min_value=2, max_value=4))
    lim = 10 ** 6 // c
    n, A, B, edges = draw(graph_data(max_n=8, amax=lim, bmax=lim))
    return (c, n, A, B, edges)


@st.composite
def isolated_data(draw):
    n, A, B, edges = draw(graph_data(max_n=11))
    extra_a = draw(st.integers(min_value=1, max_value=10 ** 6))
    return (n, A, B, edges, extra_a)


# ---------------------------------------------------------------------------
# 1) CERTIFICATE bounds: score(empty or single deletion) <= answer <= sum|B|.
# ---------------------------------------------------------------------------
@given(make_input())
@settings(max_examples=45, deadline=None)
def test_bounds(stdin):
    ans = parse_answer(run_candidate(stdin))
    n, m, A, B, edges = parse_stdin(stdin)

    # Concrete deletion sets -> valid lower bounds (never recompute the optimum).
    candidates = [set()] + [{v} for v in range(1, n + 1)]
    lb = max(profit_of(n, A, B, edges, d) for d in candidates)
    ub = sum(abs(b) for b in B)  # triangle inequality; costs are non-negative

    assert ans >= lb, f"answer {ans} below achievable profit {lb}"
    assert ans <= ub, f"answer {ans} exceeds sum|B| upper bound {ub}"
    assert ans >= 0, f"answer {ans} negative (empty deletion gives >=0)"


# ---------------------------------------------------------------------------
# 2) METAMORPHIC: score uses |sum B|, so negating every B is invariant.
# ---------------------------------------------------------------------------
@given(graph_data(max_n=10))
@settings(max_examples=15, deadline=None)
def test_negate_b_invariant(data):
    n, A, B, edges = data
    a1 = parse_answer(run_candidate(build_input(n, A, B, edges)))
    a2 = parse_answer(run_candidate(build_input(n, A, [-b for b in B], edges)))
    assert a1 == a2, f"negating all B changed answer: {a1} vs {a2}"


# ---------------------------------------------------------------------------
# 3) METAMORPHIC: relabeling vertices (isomorphic graph) is invariant.
# ---------------------------------------------------------------------------
@given(perm_data(max_n=10))
@settings(max_examples=15, deadline=None)
def test_relabel_invariant(data):
    n, A, B, edges, perm = data
    newA = [0] * n
    newB = [0] * n
    for old in range(1, n + 1):
        nl = perm[old - 1]
        newA[nl - 1] = A[old - 1]
        newB[nl - 1] = B[old - 1]
    newedges = [(perm[u - 1], perm[v - 1]) for (u, v) in edges]
    a1 = parse_answer(run_candidate(build_input(n, A, B, edges)))
    a2 = parse_answer(run_candidate(build_input(n, newA, newB, newedges)))
    assert a1 == a2, f"vertex relabeling changed answer: {a1} vs {a2}"


# ---------------------------------------------------------------------------
# 4) METAMORPHIC: scaling A and B by c>0 scales profit by exactly c.
# ---------------------------------------------------------------------------
@given(scale_data())
@settings(max_examples=15, deadline=None)
def test_scale_invariant(data):
    c, n, A, B, edges = data
    a1 = parse_answer(run_candidate(build_input(n, A, B, edges)))
    a2 = parse_answer(run_candidate(
        build_input(n, [a * c for a in A], [b * c for b in B], edges)))
    assert a2 == c * a1, f"scaling by {c}: expected {c * a1}, got {a2}"


# ---------------------------------------------------------------------------
# 5) METAMORPHIC: adding an isolated vertex with B=0 (never worth deleting)
#    leaves the maximum profit unchanged.
# ---------------------------------------------------------------------------
@given(isolated_data())
@settings(max_examples=15, deadline=None)
def test_isolated_zero_vertex_invariant(data):
    n, A, B, edges, extra_a = data
    a1 = parse_answer(run_candidate(build_input(n, A, B, edges)))
    a2 = parse_answer(run_candidate(
        build_input(n + 1, A + [extra_a], B + [0], edges)))
    assert a1 == a2, f"adding isolated B=0 vertex changed answer: {a1} vs {a2}"