from hypothesis import given, strategies as st, settings, example
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

HI = 10 ** 9


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def to_stdin(n, m, grid):
    lines = ["{} {}".format(n, m)]
    for row in grid:
        lines.append(" ".join(str(v) for v in row))
    return "\n".join(lines) + "\n"


def parse_input_grid(stdin, n, m):
    lines = stdin.splitlines()
    grid = []
    for i in range(1, 1 + n):
        grid.append([int(x) for x in lines[i].split()])
    return grid


def parse_grid(stdout, n, m):
    """Parse an n x m grid of positive ints, tolerant of trailing whitespace."""
    lines = [ln for ln in stdout.splitlines() if ln.strip() != ""]
    assert len(lines) == n, "expected {} output lines, got {}: {!r}".format(n, len(lines), stdout)
    grid = []
    for ln in lines:
        toks = ln.split()
        assert len(toks) == m, "expected {} ints per line, got {}: {!r}".format(m, len(toks), ln)
        try:
            row = [int(t) for t in toks]
        except ValueError:
            raise AssertionError("non-integer output token in line {!r}".format(ln))
        grid.append(row)
    return grid


# ----------------------------------------------------------------------------
# Input generators (aggressively target the trigger regions)
# ----------------------------------------------------------------------------
@st.composite
def grid_strategy(draw, max_dim=8):
    n = draw(st.integers(min_value=1, max_value=max_dim))
    m = draw(st.integers(min_value=1, max_value=max_dim))
    mode = draw(st.sampled_from(
        ["equal", "distinct", "dup", "extreme", "sorted", "random", "random_big"]
    ))
    if mode == "equal":
        # all-equal: forces d_r = d_c = 1  => answer must be exactly 1 everywhere
        c = draw(st.one_of(st.just(1), st.just(HI), st.integers(1, HI)))
        grid = [[c] * m for _ in range(n)]
    elif mode == "distinct":
        vals = draw(st.lists(st.integers(1, HI), min_size=n * m, max_size=n * m, unique=True))
        grid = [vals[i * m:(i + 1) * m] for i in range(n)]
    elif mode == "dup":
        # heavy duplicates from a tiny pool (some pools mix min & max magnitudes)
        pool = draw(st.sampled_from([[1, 2], [1, 2, 3], [3, 7], [1, HI], [5, 5], [1, HI, 500]]))
        grid = [[draw(st.sampled_from(pool)) for _ in range(m)] for _ in range(n)]
    elif mode == "extreme":
        # extreme magnitudes 1 and 1e9 with heavy duplication combined in one input
        grid = [[draw(st.sampled_from([1, HI])) for _ in range(m)] for _ in range(n)]
    elif mode == "sorted":
        # strictly increasing (already-sorted) monotone structure
        start = draw(st.integers(1, 1000))
        grid = [[start + i * m + j for j in range(m)] for i in range(n)]
    elif mode == "random":
        top = draw(st.sampled_from([2, 3, 4, 5, 10]))
        grid = [[draw(st.integers(1, top)) for _ in range(m)] for _ in range(n)]
    else:  # random_big
        grid = [[draw(st.integers(1, HI)) for _ in range(m)] for _ in range(n)]
    return n, m, grid


@st.composite
def make_input(draw):
    n, m, grid = draw(grid_strategy(max_dim=8))
    return to_stdin(n, m, grid)


@st.composite
def grid_with_perms(draw, max_dim=6):
    n, m, grid = draw(grid_strategy(max_dim=max_dim))
    row_perm = draw(st.permutations(list(range(n))))
    col_perm = draw(st.permutations(list(range(m))))
    return n, m, grid, row_perm, col_perm


@st.composite
def line_strategy(draw, max_len=40):
    """A single row (1 x k) or single column (k x 1): the crossing street then
    consists of just the intersection cell, so the answer is fully determined."""
    length = draw(st.integers(min_value=1, max_value=max_len))
    orient = draw(st.sampled_from(["row", "col"]))
    mode = draw(st.sampled_from(["equal", "distinct", "dup", "extreme", "random"]))
    if mode == "equal":
        c = draw(st.sampled_from([1, 7, HI]))
        vals = [c] * length
    elif mode == "distinct":
        vals = draw(st.lists(st.integers(1, HI), min_size=length, max_size=length, unique=True))
    elif mode == "dup":
        pool = draw(st.sampled_from([[1, 2], [1, 2, 3], [1, HI], [5, 5], [1, HI, 500]]))
        vals = [draw(st.sampled_from(pool)) for _ in range(length)]
    elif mode == "extreme":
        vals = [draw(st.sampled_from([1, HI])) for _ in range(length)]
    else:
        top = draw(st.sampled_from([2, 3, 5, HI]))
        vals = [draw(st.integers(1, top)) for _ in range(length)]
    if orient == "row":
        return 1, length, [vals]
    return length, 1, [[v] for v in vals]


# ----------------------------------------------------------------------------
# Test 1: format / shape / range + certificate bounds per cell.
#   For every cell (i,j):  max(d_r, d_c) <= x <= d_r + d_c - 1
#   where d_r = #distinct in row i, d_c = #distinct in column j.
#   Lower: each street's distinct values need distinct increasing labels, so the
#          max used is >= that street's distinct count.
#   Upper: stacking row-below/above and column-below/above on separate levels
#          (sharing only the intersection) is a valid assignment => optimum
#          <= d_r + d_c - 1.
# These bounds are derived from the input WITHOUT solving the optimisation.
# ----------------------------------------------------------------------------
@given(make_input())
@settings(max_examples=40, deadline=None)
# --- deterministic sweep of the small bounded box (magic-value guards) ---
@example("1 1\n1\n")
@example("1 1\n1000000000\n")
@example("1 2\n1 1\n")
@example("1 2\n1 2\n")
@example("2 1\n1\n2\n")
@example("2 2\n1 1\n1 1\n")
@example("2 2\n1 1\n1 2\n")
@example("2 2\n1 1\n2 1\n")
@example("2 2\n1 1\n2 2\n")
@example("2 2\n1 2\n1 1\n")
@example("2 2\n1 2\n1 2\n")
@example("2 2\n1 2\n2 1\n")
@example("2 2\n1 2\n2 2\n")
@example("2 2\n2 1\n1 1\n")
@example("2 2\n2 1\n1 2\n")
@example("2 2\n2 1\n2 1\n")
@example("2 2\n2 1\n2 2\n")
@example("2 2\n2 2\n1 1\n")
@example("2 2\n2 2\n1 2\n")
@example("2 2\n2 2\n2 1\n")
@example("2 2\n2 2\n2 2\n")
@example("2 2\n1 1000000000\n1000000000 1\n")
@example("3 3\n5 5 5\n5 5 5\n5 5 5\n")
@example("2 3\n1 2 1\n2 1 2\n")
@example("2 2\n1 2\n3 4\n")
def test_format_bounds(stdin):
    first = stdin.split("\n", 1)[0].split()
    n, m = int(first[0]), int(first[1])
    grid = parse_input_grid(stdin, n, m)
    ans = parse_grid(run_candidate(stdin), n, m)

    row_d = [len(set(grid[i])) for i in range(n)]
    col_d = [len(set(grid[i][j] for i in range(n))) for j in range(m)]

    for i in range(n):
        for j in range(m):
            x = ans[i][j]
            assert x >= 1, "answer must be a positive height, got {} at {}".format(x, (i, j))
            lo = max(row_d[i], col_d[j])
            hi = row_d[i] + col_d[j] - 1
            assert lo <= x <= hi, \
                "cell {} value {} outside sound bound [{}, {}]".format((i, j), x, lo, hi)


# ----------------------------------------------------------------------------
# Test 2: monotone invariance (metamorphic).
#   The answer depends ONLY on within-street comparisons, so any strictly
#   order-and-equality-preserving remap of the heights must leave the whole
#   output unchanged. We remap distinct values to a spread reaching ~1e9.
# ----------------------------------------------------------------------------
@given(grid_strategy(max_dim=6))
@settings(max_examples=15, deadline=None)
def test_monotone_invariance(case):
    n, m, grid = case
    stdin1 = to_stdin(n, m, grid)

    allvals = sorted(set(v for row in grid for v in row))
    D = len(allvals)
    if D == 1:
        targets = [HI]
    else:
        step = (HI - 1) // (D - 1)   # >= 1 since D is tiny
        targets = [1 + k * step for k in range(D)]  # strictly increasing, in [1, 1e9]
    mp = {allvals[k]: targets[k] for k in range(D)}
    grid2 = [[mp[v] for v in row] for row in grid]
    stdin2 = to_stdin(n, m, grid2)

    a1 = parse_grid(run_candidate(stdin1), n, m)
    a2 = parse_grid(run_candidate(stdin2), n, m)
    assert a1 == a2, "monotone remap changed the output"


# ----------------------------------------------------------------------------
# Test 3: transpose symmetry (metamorphic).
#   Rows and columns play perfectly symmetric roles: cell (i,j) uses row i and
#   column j; in the transpose, cell (j,i) uses the very same two streets, so
#   answer_T[j][i] == answer[i][j].
# ----------------------------------------------------------------------------
@given(grid_strategy(max_dim=6))
@settings(max_examples=15, deadline=None)
def test_transpose_symmetry(case):
    n, m, grid = case
    stdin1 = to_stdin(n, m, grid)
    gridT = [[grid[i][j] for i in range(n)] for j in range(m)]  # m x n
    stdin2 = to_stdin(m, n, gridT)

    a1 = parse_grid(run_candidate(stdin1), n, m)
    a2 = parse_grid(run_candidate(stdin2), m, n)
    for i in range(n):
        for j in range(m):
            assert a2[j][i] == a1[i][j], \
                "transpose mismatch at {}: {} vs {}".format((i, j), a1[i][j], a2[j][i])


# ----------------------------------------------------------------------------
# Test 4: row/column permutation invariance (metamorphic).
#   A cell's answer depends only on the MULTISET of its row and of its column
#   (and its rank within each), which are permutation-invariant. Permuting rows
#   and columns just relocates each cell's answer.
# ----------------------------------------------------------------------------
@given(grid_with_perms(max_dim=6))
@settings(max_examples=15, deadline=None)
def test_row_col_permutation(case):
    n, m, grid, rp, cp = case
    stdin1 = to_stdin(n, m, grid)
    newgrid = [[grid[rp[p]][cp[q]] for q in range(m)] for p in range(n)]
    stdin2 = to_stdin(n, m, newgrid)

    a1 = parse_grid(run_candidate(stdin1), n, m)
    a2 = parse_grid(run_candidate(stdin2), n, m)
    for p in range(n):
        for q in range(m):
            assert a2[p][q] == a1[rp[p]][cp[q]], \
                "permutation mismatch at new cell {}".format((p, q))


# ----------------------------------------------------------------------------
# Test 5: single-line exact certificate.
#   If n == 1 (single Eastern street) then for every intersection the Southern
#   street holds only the intersection skyscraper itself, so the sub-problem is
#   just relabelling the one row while preserving its order: the minimum max is
#   exactly the number of DISTINCT heights in that row -- identical for every
#   column. Symmetrically for m == 1. This is fully determined by the spec and
#   requires no optimisation, yet pins the exact answer for all degenerate lines.
# ----------------------------------------------------------------------------
@given(line_strategy(max_len=40))
@settings(max_examples=40, deadline=None)
@example((1, 1, [[1]]))
@example((1, 1, [[10 ** 9]]))
@example((1, 4, [[1, 2, 2, 1]]))
@example((5, 1, [[3], [3], [1], [7], [7]]))
def test_single_line_exact(case):
    n, m, grid = case
    stdin = to_stdin(n, m, grid)
    ans = parse_grid(run_candidate(stdin), n, m)
    if n == 1:
        d = len(set(grid[0]))
        for j in range(m):
            assert ans[0][j] == d, \
                "single-row cell {} must equal distinct count {}, got {}".format(j, d, ans[0][j])
    if m == 1:
        d = len(set(grid[i][0] for i in range(n)))
        for i in range(n):
            assert ans[i][0] == d, \
                "single-col cell {} must equal distinct count {}, got {}".format(i, d, ans[i][0])
