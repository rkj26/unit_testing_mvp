from itertools import product
from collections import deque

from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str


# ---------------------------------------------------------------------------
# Problem recap (Codeforces "Monopole Magnets"):
#   n x m grid of '#'/'.'.  Output = min number of north magnets, or -1.
# Sound, spec-entailed facts used below (NO exact-answer recomputation):
#   * A single north magnet's reachable set is 4-connected and all-black, and
#     every black cell must be reachable -> answer >= #(4-connected '#' comps).
#     (LOWER BOUND certificate; never the exact value from above.)
#   * answer, when finite, cannot exceed the number of black cells.
#   * NECESSARY conditions for a placement to exist (else answer == -1):
#       (a) in every row and every column the '#' cells are contiguous;
#       (b) (an all-white row exists) IFF (an all-white column exists).
#     Both are necessary; together they are also sufficient (an explicit
#     placement with one north per component exists), so their negation
#     guarantees answer != -1.
#   * All-white grid -> 0.
#   * The problem is invariant under transpose and under horizontal/vertical
#     flips (row/column roles and contiguity/empties are all symmetric).
# These are one-sided certificates + metamorphic relations, not a solver.
# ---------------------------------------------------------------------------


def _grid_to_stdin(rows):
    n = len(rows)
    m = len(rows[0]) if n else 0
    return "{} {}\n".format(n, m) + "\n".join(rows) + "\n"


def _parse_stdin(stdin):
    lines = stdin.split("\n")
    a, b = lines[0].split()
    n, m = int(a), int(b)
    rows = [lines[1 + i] for i in range(n)]
    return n, m, rows


def _has_gap(rows, n, m):
    for i in range(n):
        idx = [j for j in range(m) if rows[i][j] == '#']
        if idx and (idx[-1] - idx[0] + 1) != len(idx):
            return True
    for j in range(m):
        idx = [i for i in range(n) if rows[i][j] == '#']
        if idx and (idx[-1] - idx[0] + 1) != len(idx):
            return True
    return False


def _empty_flags(rows, n, m):
    empty_row = any(all(c == '.' for c in rows[i]) for i in range(n))
    empty_col = any(all(rows[i][j] == '.' for i in range(n)) for j in range(m))
    return empty_row, empty_col


def _count_components(rows, n, m):
    seen = [[False] * m for _ in range(n)]
    comps = 0
    for si in range(n):
        for sj in range(m):
            if rows[si][sj] == '#' and not seen[si][sj]:
                comps += 1
                seen[si][sj] = True
                dq = deque([(si, sj)])
                while dq:
                    x, y = dq.popleft()
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < n and 0 <= ny < m and \
                                rows[nx][ny] == '#' and not seen[nx][ny]:
                            seen[nx][ny] = True
                            dq.append((nx, ny))
    return comps


def _verify(stdin, stdout):
    n, m, rows = _parse_stdin(stdin)
    toks = stdout.split()
    assert len(toks) == 1, "expected a single integer, got %r" % (stdout,)
    out = int(toks[0])
    num_black = sum(r.count('#') for r in rows)

    # format / range invariants
    assert out == -1 or out >= 0, "answer must be -1 or non-negative, got %d" % out
    assert out <= num_black, \
        "answer %d cannot exceed #black cells %d" % (out, num_black)

    gap = _has_gap(rows, n, m)
    er, ec = _empty_flags(rows, n, m)
    mismatch = (er != ec)

    if num_black == 0:
        assert out == 0, "all-white grid must yield 0, got %d" % out

    if gap or mismatch:
        # necessary condition violated -> no valid placement exists
        assert out == -1, \
            "config violates a necessary condition and must yield -1, got %d" % out
    else:
        # necessary conditions all hold -> a valid placement provably exists
        assert out != -1, "config satisfies all necessary conditions; -1 is wrong"
        comps = _count_components(rows, n, m)
        assert out >= comps, \
            "answer %d is below the #components lower bound %d" % (out, comps)
        if num_black > 0:
            assert out >= 1, "non-empty valid grid needs >= 1 north, got %d" % out
    return out


def _check(stdin):
    return _verify(stdin, run_candidate(stdin))


# ---- transforms used by metamorphic tests --------------------------------

def _transpose_stdin(stdin):
    n, m, rows = _parse_stdin(stdin)
    trows = ["".join(rows[i][j] for i in range(n)) for j in range(m)]
    return _grid_to_stdin(trows)


def _flipv_stdin(stdin):
    n, m, rows = _parse_stdin(stdin)
    return _grid_to_stdin(list(reversed(rows)))


def _fliph_stdin(stdin):
    n, m, rows = _parse_stdin(stdin)
    return _grid_to_stdin([r[::-1] for r in rows])


# ---- generators ----------------------------------------------------------

@st.composite
def _g_random(draw):
    n = draw(st.integers(min_value=1, max_value=10))
    m = draw(st.integers(min_value=1, max_value=10))
    palette = draw(st.sampled_from([
        list("#."), list("#..."), list("#....."),
        list("##."), list("###."), list("#"), list("."),
    ]))
    rows = ["".join(draw(st.sampled_from(palette)) for _ in range(m))
            for _ in range(n)]
    return _grid_to_stdin(rows)


@st.composite
def _g_row_contig(draw):
    # every row is contiguous or empty; columns may or may not be contiguous
    n = draw(st.integers(min_value=1, max_value=10))
    m = draw(st.integers(min_value=1, max_value=10))
    rows = []
    for _ in range(n):
        if draw(st.booleans()):
            rows.append("." * m)
        else:
            l = draw(st.integers(min_value=0, max_value=m - 1))
            r = draw(st.integers(min_value=l, max_value=m - 1))
            rows.append("." * l + "#" * (r - l + 1) + "." * (m - 1 - r))
    return _grid_to_stdin(rows)


def _rect_grid(n, m, r1, r2, c1, c2):
    rows = []
    for i in range(n):
        if r1 <= i <= r2:
            rows.append("." * c1 + "#" * (c2 - c1 + 1) + "." * (m - 1 - c2))
        else:
            rows.append("." * m)
    return _grid_to_stdin(rows)


@st.composite
def _g_rect(draw):
    # a single solid rectangle -> targets the empty-row/empty-col XOR boundary
    n = draw(st.integers(min_value=1, max_value=10))
    m = draw(st.integers(min_value=1, max_value=10))
    r1 = draw(st.integers(min_value=0, max_value=n - 1))
    r2 = draw(st.integers(min_value=r1, max_value=n - 1))
    c1 = draw(st.integers(min_value=0, max_value=m - 1))
    c2 = draw(st.integers(min_value=c1, max_value=m - 1))
    return _rect_grid(n, m, r1, r2, c1, c2)


@st.composite
def _g_diag(draw):
    # isolated cells on the main diagonal -> always valid, #comps == #picks,
    # empties balanced by construction; exercises the component lower bound
    N = draw(st.integers(min_value=1, max_value=10))
    picks = [draw(st.booleans()) for _ in range(N)]
    rows = []
    for i in range(N):
        row = ["."] * N
        if picks[i]:
            row[i] = "#"
        rows.append("".join(row))
    return _grid_to_stdin(rows)


def _all_grids(n, m):
    out = []
    for bits in product(".#", repeat=n * m):
        rows = ["".join(bits[i * m:(i + 1) * m]) for i in range(n)]
        out.append(_grid_to_stdin(rows))
    return out


# Exhaustive small domains where magic-value guards hide, plus crafted edges.
_CURATED_SMALL = []
for (nn, mm) in [(1, 1), (1, 2), (2, 1), (2, 2), (1, 3), (3, 1)]:
    _CURATED_SMALL += _all_grids(nn, mm)
_CURATED_SMALL += [
    _grid_to_stdin([".#.", "###", "##."]),                  # example 1 -> 1
    _grid_to_stdin(["##", ".#", ".#", "##"]),               # example 2 -> -1
    _grid_to_stdin(["....#", "####.", ".###.", ".#..."]),   # example 3 -> 2
    _grid_to_stdin([".", "#"]),                              # example 4 -> -1
    _grid_to_stdin(["....."] * 3),                           # example 5 -> 0
    _grid_to_stdin(["#.#", "...", "#.#"]),                   # row gaps -> -1
    _grid_to_stdin(["#..", ".#.", "..#"]),                   # diag comps=3
    _grid_to_stdin(["...", ".#.", "..."]),                   # interior -> 1
    _grid_to_stdin(["###", "###", "###"]),                   # full -> 1
    _grid_to_stdin(["#...", "....", "...#", "...."]),        # 2 comps, valid
    _grid_to_stdin(["#..#", "....", "....", "#..#"]),        # corners, valid
    _grid_to_stdin(["#.#."]),                                # 1x4 gap -> -1
    _grid_to_stdin([".##.", ".##."]),                        # block -> valid 1
]

# Large / extreme-magnitude single-shot cases (used only in single-call tests).
_BIG = [
    _grid_to_stdin(["#" * 1000]),                    # 1x1000 all black -> 1
    _grid_to_stdin(["." * 1000]),                    # 1x1000 all white -> 0
    _grid_to_stdin(["#" * 500 + "." + "#" * 499]),   # 1x1000 gap -> -1
    _grid_to_stdin(["#"] * 1000),                    # 1000x1 all black -> 1
    _grid_to_stdin(["."] * 1000),                    # 1000x1 all white -> 0
    _rect_grid(50, 50, 0, 49, 0, 49),                # 50x50 full -> 1
    _rect_grid(40, 60, 10, 30, 5, 40),               # interior block -> valid
    _rect_grid(30, 40, 0, 29, 5, 20),                # full height, partial width -> -1
    _rect_grid(30, 40, 5, 20, 0, 39),                # full width, partial height -> -1
    _grid_to_stdin(["".join("#" if (i + j) % 2 == 0 else "."
                            for j in range(30)) for i in range(30)]),  # checker -> -1
    _grid_to_stdin(["".join("#" if i == j else "." for j in range(40))
                    for i in range(40)]),            # 40x40 identity -> comps=40
]

_SMALL_BASE = st.one_of(
    _g_random(), _g_row_contig(), _g_rect(), _g_diag(),
    st.sampled_from(_CURATED_SMALL),
)
_ANY_BASE = st.one_of(_SMALL_BASE, st.sampled_from(_BIG))


# ---- tests ---------------------------------------------------------------

@given(_ANY_BASE)
@settings(max_examples=55, deadline=None)
def test_certificate(stdin):
    _check(stdin)


@given(st.sampled_from(_CURATED_SMALL))
@settings(max_examples=90, deadline=None)
def test_small_domain_sweep(stdin):
    _check(stdin)


@given(_SMALL_BASE)
@settings(max_examples=22, deadline=None)
def test_transpose_metamorphic(stdin):
    t = _transpose_stdin(stdin)
    a = _verify(stdin, run_candidate(stdin))
    b = _verify(t, run_candidate(t))
    assert a == b, "transpose must preserve the answer: %d vs %d" % (a, b)


@given(_SMALL_BASE)
@settings(max_examples=14, deadline=None)
def test_flip_metamorphic(stdin):
    v = _flipv_stdin(stdin)
    h = _fliph_stdin(stdin)
    a = _verify(stdin, run_candidate(stdin))
    b = _verify(v, run_candidate(v))
    c = _verify(h, run_candidate(h))
    assert a == b == c, \
        "flips must preserve the answer: base=%d flipv=%d fliph=%d" % (a, b, c)