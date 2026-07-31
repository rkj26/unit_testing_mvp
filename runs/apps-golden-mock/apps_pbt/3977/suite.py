import re
from collections import Counter

from hypothesis import given, strategies as st, settings
from harness import run_candidate  # run_candidate(stdin: str) -> stdout: str


# ---------------------------------------------------------------------------
# Problem 3977 (Hongcow / stable graph):
#   Graph on n nodes, m edges, k government nodes each in a DISTINCT connected
#   component (no path between any two governments). Add as many edges as
#   possible while keeping the graph simple and governments mutually
#   unreachable. Output the maximum number of edges addable.
#
#   Known facts a correct output MUST satisfy (used WITHOUT solving):
#     * output is a single non-negative integer.
#     * UPPER BOUND: any stable final graph partitions n nodes into >= k parts
#       (governments separated); sum of C(size,2) is maximised by one part of
#       size n-k+1 and k-1 singletons  =>  answer <= C(n-k+1, 2) - m.
#     * LOWER BOUND (certificate): clique-ifying every EXISTING connected
#       component in place is a valid stable configuration (adds no cross-
#       component edges, governments stay separated) =>
#       answer >= sum_over_components C(comp,2) - m.
#     * relabelling nodes (isomorphism) leaves the answer unchanged.
#     * adding a fresh ISOLATED GOVERNMENT node leaves the answer unchanged
#       (it forms a size-1 component contributing 0 and never becomes the
#       merge target for free nodes).
#     * adding a fresh ISOLATED FREE node raises the answer by exactly the size
#       S of the largest merged cluster, with 1 <= S <= n-k+1.
# ---------------------------------------------------------------------------


def c2(x):
    return x * (x - 1) // 2


def serialize(n, govs, edges):
    lines = ["{} {} {}".format(n, len(edges), len(govs))]
    lines.append(" ".join(str(g) for g in govs))
    for (u, v) in edges:
        lines.append("{} {}".format(u, v))
    return "\n".join(lines) + "\n"


def parse_int(out):
    toks = out.split()
    assert len(toks) == 1, "expected exactly one integer token, got {!r}".format(out)
    tok = toks[0]
    assert re.fullmatch(r"-?\d+", tok) is not None, "not an integer: {!r}".format(out)
    return int(tok)


def clique_in_place_lower_bound(n, govs, edges):
    """sum C(component,2) - m  -- a valid achievable stable configuration."""
    parent = list(range(n + 1))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (u, v) in edges:
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv
    size = Counter()
    for node in range(1, n + 1):
        size[find(node)] += 1
    total = sum(c2(c) for c in size.values())
    return total - len(edges)


def check_bounds(stdin, n, govs, edges):
    val = parse_int(run_candidate(stdin))
    k = len(govs)
    m = len(edges)
    assert val >= 0, "answer must be non-negative, got {}".format(val)
    lb = clique_in_place_lower_bound(n, govs, edges)
    ub = c2(n - k + 1) - m
    assert val >= lb, "answer {} below achievable lower bound {}".format(val, lb)
    assert val <= ub, "answer {} above provable upper bound {}".format(val, ub)


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------
@st.composite
def make_case(draw, max_n=40):
    """Valid stable graph built from disjoint 'groups'.

    Edges are only ever placed WITHIN a group and governments live in distinct
    groups, so no two governments are ever connected -> always stable. Groups
    may be internally disconnected (empty style), which turns their non-gov
    members into free components -> exercises the merge-into-largest logic.
    """
    n = draw(st.integers(min_value=1, max_value=max_n))
    k = draw(st.integers(min_value=1, max_value=n))
    max_fg = n - k
    fg = draw(st.integers(min_value=0, max_value=max_fg))
    num_groups = k + fg

    sizes = [1] * num_groups
    for _ in range(n - num_groups):
        sizes[draw(st.integers(min_value=0, max_value=num_groups - 1))] += 1

    labels = draw(st.permutations(list(range(1, n + 1))))
    groups = []
    pos = 0
    for s in sizes:
        groups.append(labels[pos:pos + s])
        pos += s

    govs = []
    edges = []
    for gi, grp in enumerate(groups):
        if gi < k:
            govs.append(grp[draw(st.integers(min_value=0, max_value=len(grp) - 1))])
        c = len(grp)
        if c >= 2:
            choices = ["empty", "path", "star", "clique"]
            if c <= 12:
                choices.append("random")
            style = draw(st.sampled_from(choices))
            if style == "path":
                for i in range(c - 1):
                    edges.append((grp[i], grp[i + 1]))
            elif style == "star":
                for i in range(1, c):
                    edges.append((grp[0], grp[i]))
            elif style == "clique":
                for i in range(c):
                    for j in range(i + 1, c):
                        edges.append((grp[i], grp[j]))
            elif style == "random":
                for i in range(c):
                    for j in range(i + 1, c):
                        if draw(st.booleans()):
                            edges.append((grp[i], grp[j]))
    return (n, govs, edges)


@st.composite
def make_case_large(draw):
    """Extreme magnitudes: one big government clique (m near its 1e5 cap),
    a few singleton governments, many isolated free nodes, n up to ~1000."""
    s = draw(st.sampled_from([1, 2, 3, 50, 150, 300, 447]))  # C(447,2)=99681 <= 1e5
    remaining = 1000 - s
    eg = draw(st.integers(min_value=0, max_value=min(remaining, 20)))
    remaining -= eg
    f = draw(st.integers(min_value=0, max_value=remaining))
    n = s + eg + f
    govs = [1] + list(range(s + 1, s + 1 + eg))
    edges = [(i, j) for i in range(1, s + 1) for j in range(i + 1, s + 1)]
    return (n, govs, edges)


@st.composite
def make_iso(draw):
    n, govs, edges = draw(make_case())
    perm = draw(st.permutations(list(range(1, n + 1))))
    gov_order = draw(st.permutations(list(range(len(govs)))))
    edge_order = draw(st.permutations(list(range(len(edges)))))
    return (n, govs, edges, perm, gov_order, edge_order)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@given(make_case())
@settings(max_examples=50, deadline=None)
def test_format_and_bounds(case):
    n, govs, edges = case
    check_bounds(serialize(n, govs, edges), n, govs, edges)


@given(make_case_large())
@settings(max_examples=8, deadline=None)
def test_bounds_extreme(case):
    n, govs, edges = case
    check_bounds(serialize(n, govs, edges), n, govs, edges)


@given(make_iso())
@settings(max_examples=20, deadline=None)
def test_isomorphism_invariance(data):
    n, govs, edges, perm, gov_order, edge_order = data
    a1 = parse_int(run_candidate(serialize(n, govs, edges)))

    def relabel(x):
        return perm[x - 1]

    new_govs = [relabel(govs[i]) for i in gov_order]
    new_edges = [ (relabel(edges[i][0]), relabel(edges[i][1])) for i in edge_order ]
    a2 = parse_int(run_candidate(serialize(n, new_govs, new_edges)))
    assert a1 == a2, "relabelling changed answer: {} vs {}".format(a1, a2)


@given(make_case())
@settings(max_examples=20, deadline=None)
def test_add_isolated_government(case):
    n, govs, edges = case
    a1 = parse_int(run_candidate(serialize(n, govs, edges)))
    # fresh isolated government node n+1 -> size-1 component, answer unchanged
    a2 = parse_int(run_candidate(serialize(n + 1, govs + [n + 1], edges)))
    assert a1 == a2, "isolated new government changed answer: {} vs {}".format(a1, a2)


@given(make_case())
@settings(max_examples=20, deadline=None)
def test_add_isolated_free_node(case):
    n, govs, edges = case
    k = len(govs)
    a1 = parse_int(run_candidate(serialize(n, govs, edges)))
    # fresh isolated free node n+1 -> merges into largest cluster of size S
    a2 = parse_int(run_candidate(serialize(n + 1, govs, edges)))
    delta = a2 - a1
    assert delta >= 1, "adding a free node must raise answer by >=1, got {}".format(delta)
    assert delta <= (n - k + 1), "delta {} exceeds max cluster size {}".format(delta, n - k + 1)