from hypothesis import given, strategies as st, settings
from harness import run_candidate  # run_candidate(stdin: str) -> stdout: str
from collections import deque


# ----------------------------------------------------------------------------
# Problem 3926 (CF "Labyrinth"): n x m maze, start (r,c), move up/down freely,
# move left at most x times, right at most y times. Count reachable free cells.
#
# Key SOUND facts used below (no full solver is reimplemented):
#  * The start cell is always reachable  -> answer >= 1.
#  * Reachable cells are a subset of the 4-connectivity flood component of '.'
#    around the start (ignoring x,y is only more permissive) -> answer <= flood.
#  * With x=0,y=0 no horizontal move is allowed, so exactly the vertical '.'
#    segment through column c is reachable -> answer == vseg.
#  * The vertical segment is reachable for ANY x,y>=0 -> answer >= vseg.
#  * For ANY reachable cell in column j: net horizontal = j-c = R-L with
#    L<=x, R<=y, so  c-x <= j <= c+y. -> answer <= |flood cells in that band|.
#  * A fewest-steps path visits < n*m cells, so min left/right moves to reach
#    any component cell are < n*m. Hence x>=n*m and y>=n*m => answer == flood.
#  * Monotone: raising x or y can only add reachable cells.
#  * Metamorphic symmetries: horizontal mirror + swap(x,y) preserves the count;
#    vertical flip preserves the count.
# ----------------------------------------------------------------------------


def parse_input(stdin):
    lines = stdin.split('\n')
    n, m = map(int, lines[0].split())
    r, c = map(int, lines[1].split())
    x, y = map(int, lines[2].split())
    grid = [lines[3 + i] for i in range(n)]
    return n, m, r, c, x, y, grid


def build_stdin(n, m, r, c, x, y, grid):
    out = [f"{n} {m}", f"{r} {c}", f"{x} {y}"]
    out.extend(grid)
    return "\n".join(out) + "\n"


def parse_answer(stdout):
    toks = stdout.split()
    assert len(toks) == 1, f"expected exactly one integer, got {stdout!r}"
    t = toks[0]
    assert t.isdigit(), f"expected a non-negative integer, got {t!r}"
    return int(t)


def free_count(grid):
    return sum(row.count('.') for row in grid)


def vseg(grid, n, r, c):
    """Length of the maximal vertical '.' run in column c through row r."""
    j = c - 1
    cnt = 1
    i = r - 2
    while i >= 0 and grid[i][j] == '.':
        cnt += 1
        i -= 1
    i = r
    while i < n and grid[i][j] == '.':
        cnt += 1
        i += 1
    return cnt


def flood_cells(grid, n, m, r, c):
    """All '.' cells 4-connected to the start (unconstrained reachability)."""
    seen = [[False] * m for _ in range(n)]
    si, sj = r - 1, c - 1
    seen[si][sj] = True
    dq = deque([(si, sj)])
    cells = []
    while dq:
        i, j = dq.popleft()
        cells.append((i, j))
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if 0 <= ni < n and 0 <= nj < m and not seen[ni][nj] and grid[ni][nj] == '.':
                seen[ni][nj] = True
                dq.append((ni, nj))
    return cells


def _draw_grid(draw, n, m):
    # Obstacle density out of 10: 0 => all free; 8 => very dense.
    thr = draw(st.sampled_from([0, 0, 1, 2, 3, 4, 6, 8]))
    rows = []
    for _ in range(n):
        rows.append(['*' if draw(st.integers(0, 9)) < thr else '.' for _ in range(m)])
    return rows


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------
@st.composite
def make_input(draw):
    # Mix small and boundary shapes, incl single row / single column / 1x1.
    n = draw(st.integers(1, 14))
    m = draw(st.integers(1, 14))
    grid = _draw_grid(draw, n, m)
    r = draw(st.integers(1, n))
    c = draw(st.integers(1, m))
    grid[r - 1][c - 1] = '.'
    rows = ["".join(row) for row in grid]
    big = 10 ** 9
    # Budgets: extremes (0, 1e9), tiny, and exact thresholds tied to columns.
    x = draw(st.one_of(
        st.sampled_from([0, 1, 2, 3, max(0, c - 1), max(0, m - 1), big]),
        st.integers(0, big),
    ))
    y = draw(st.one_of(
        st.sampled_from([0, 1, 2, 3, max(0, m - c), max(0, m - 1), big]),
        st.integers(0, big),
    ))
    return build_stdin(n, m, r, c, x, y, rows)


@st.composite
def make_input_zero(draw):
    # Force x=y=0: reachability collapses to the vertical column segment.
    n = draw(st.integers(1, 16))
    m = draw(st.integers(1, 16))
    grid = _draw_grid(draw, n, m)
    r = draw(st.integers(1, n))
    c = draw(st.integers(1, m))
    grid[r - 1][c - 1] = '.'
    rows = ["".join(row) for row in grid]
    return build_stdin(n, m, r, c, 0, 0, rows)


@st.composite
def make_input_full(draw):
    # Force x,y >= n*m: reachability equals the whole flood component.
    n = draw(st.integers(1, 16))
    m = draw(st.integers(1, 16))
    grid = _draw_grid(draw, n, m)
    r = draw(st.integers(1, n))
    c = draw(st.integers(1, m))
    grid[r - 1][c - 1] = '.'
    rows = ["".join(row) for row in grid]
    nm = n * m
    x = draw(st.sampled_from([nm, nm + 5, 10 ** 9]))
    y = draw(st.sampled_from([nm, nm + 5, 10 ** 9]))
    return build_stdin(n, m, r, c, x, y, rows)


@st.composite
def make_input_small(draw):
    # Small grids + mixed budgets for the metamorphic (multi-call) tests.
    n = draw(st.integers(1, 9))
    m = draw(st.integers(1, 9))
    grid = _draw_grid(draw, n, m)
    r = draw(st.integers(1, n))
    c = draw(st.integers(1, m))
    grid[r - 1][c - 1] = '.'
    rows = ["".join(row) for row in grid]
    big = 10 ** 9
    x = draw(st.one_of(st.sampled_from([0, 1, 2, 3, big]), st.integers(0, big)))
    y = draw(st.one_of(st.sampled_from([0, 1, 2, 3, big]), st.integers(0, big)))
    return build_stdin(n, m, r, c, x, y, rows)


@st.composite
def make_input_budget(draw):
    # Bias to tiny budgets: the genuinely constrained regime.
    n = draw(st.integers(1, 10))
    m = draw(st.integers(1, 10))
    grid = _draw_grid(draw, n, m)
    r = draw(st.integers(1, n))
    c = draw(st.integers(1, m))
    grid[r - 1][c - 1] = '.'
    rows = ["".join(row) for row in grid]
    x = draw(st.sampled_from([0, 1, 2, 3, 4, 5]))
    y = draw(st.sampled_from([0, 1, 2, 3, 4, 5]))
    return build_stdin(n, m, r, c, x, y, rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@given(make_input())
@settings(max_examples=50, deadline=None)
def test_bounds_and_certificates(stdin):
    n, m, r, c, x, y, grid = parse_input(stdin)
    ans = parse_answer(run_candidate(stdin))

    # Range / format: start is always reachable, never exceed free cells.
    assert ans >= 1, "start cell is always reachable"
    assert ans <= free_count(grid), "cannot exceed number of free cells"

    comp = flood_cells(grid, n, m, r, c)
    assert ans <= len(comp), "reachable subset of 4-connected component"

    vs = vseg(grid, n, r, c)
    assert ans >= vs, "the vertical column segment is always reachable"

    # Column-band certificate: every reachable cell j has c-x <= j <= c+y.
    lo, hi = c - x, c + y
    band = sum(1 for (_, j) in comp if lo <= (j + 1) <= hi)
    assert ans <= band, "reachable cells lie within columns [c-x, c+y]"

    # Exact regimes.
    if x == 0 and y == 0:
        assert ans == vs, "with no horizontal budget only the column segment is reachable"
    if x >= n * m and y >= n * m:
        assert ans == len(comp), "with huge budget every component cell is reachable"


@given(make_input_zero())
@settings(max_examples=35, deadline=None)
def test_zero_budget_exact(stdin):
    n, m, r, c, x, y, grid = parse_input(stdin)
    ans = parse_answer(run_candidate(stdin))
    assert ans == vseg(grid, n, r, c)


@given(make_input_full())
@settings(max_examples=35, deadline=None)
def test_full_budget_exact(stdin):
    n, m, r, c, x, y, grid = parse_input(stdin)
    ans = parse_answer(run_candidate(stdin))
    comp = flood_cells(grid, n, m, r, c)
    assert ans == len(comp)


@given(make_input_small())
@settings(max_examples=20, deadline=None)
def test_symmetry_metamorphic(stdin):
    n, m, r, c, x, y, grid = parse_input(stdin)
    a = parse_answer(run_candidate(stdin))

    # Horizontal mirror: reverse columns, swap left/right budgets, c -> m+1-c.
    mgrid = [row[::-1] for row in grid]
    b = parse_answer(run_candidate(build_stdin(n, m, r, m + 1 - c, y, x, mgrid)))
    assert a == b, "horizontal mirror + swap(x,y) must preserve the count"

    # Vertical flip: reverse rows, r -> n+1-r; up/down are unrestricted.
    fgrid = grid[::-1]
    d = parse_answer(run_candidate(build_stdin(n, m, n + 1 - r, c, x, y, fgrid)))
    assert a == d, "vertical flip must preserve the count"


@given(make_input_budget())
@settings(max_examples=25, deadline=None)
def test_monotone_budget(stdin):
    n, m, r, c, x, y, grid = parse_input(stdin)
    a = parse_answer(run_candidate(stdin))

    big = 10 ** 9
    b = parse_answer(run_candidate(build_stdin(n, m, r, c, big, big, grid)))
    assert b >= a, "raising budgets cannot decrease the reachable count"
    assert b == len(flood_cells(grid, n, m, r, c)), "full budget reaches whole component"

    # Bumping x by exactly one stays within [a, b].
    e = parse_answer(run_candidate(build_stdin(n, m, r, c, x + 1, y, grid)))
    assert a <= e <= b, "raising x by one stays between base and full-budget counts"
