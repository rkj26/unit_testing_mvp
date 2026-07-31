import re
from hypothesis import given, strategies as st, settings

from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str


# ----------------------------------------------------------------------------
# Problem recap (for reasoning about SOUND properties only):
#   Grid H x W. Exactly one S, one T, cells in {'.', 'o', 'S', 'T'}.
#   Frog on S jumps between leaves sharing a row or column. Remove the minimum
#   number of 'o' leaves (never S or T) so S cannot reach T. Print that minimum,
#   or -1 if impossible.
#
# SOUND facts used (no need to solve the optimisation):
#   * Answer is -1  <=>  S and T share a row OR share a column.
#       - If they share, frog jumps S->T directly and S/T can't be removed => -1.
#       - If they don't share, removing every 'o' leaf in S's row and column
#         isolates S (T is elsewhere) => always achievable, so answer >= 0.
#   * A valid disconnecting set exists of size (#o in S's row + #o in S's col),
#     and another of size (#o in T's row + #o in T's col). Hence
#         0 <= answer <= min(S_cut, T_cut).
#     (Row and column meet only at S/T, which are never 'o', so no double count.)
#   * The answer is INVARIANT under: transpose, any row permutation, any column
#     permutation, swapping the S<->T labels, and adding an all-'.' row/column
#     (each preserves the row/column-sharing connectivity structure).
# ----------------------------------------------------------------------------


# ---------------------------- helpers ---------------------------------------

def build_stdin(rows):
    H = len(rows)
    W = len(rows[0])
    return "{} {}\n".format(H, W) + "\n".join(rows) + "\n"


def parse_grid(stdin):
    parts = stdin.split("\n")
    H, W = map(int, parts[0].split())
    rows = parts[1:1 + H]
    return H, W, rows


def find_char(rows, ch):
    for i, r in enumerate(rows):
        j = r.find(ch)
        if j != -1:
            return i, j
    raise AssertionError("expected char {!r} not present".format(ch))


def parse_output(stdout):
    s = stdout.strip()
    assert s != "", "empty output: {!r}".format(stdout)
    assert re.fullmatch(r"-?\d+", s), "output not a single integer: {!r}".format(stdout)
    return int(s)


def upper_bound(rows):
    H = len(rows)
    W = len(rows[0])
    rs, cs = find_char(rows, "S")
    rt, ct = find_char(rows, "T")
    o_row = lambda i: sum(1 for j in range(W) if rows[i][j] == "o")
    o_col = lambda j: sum(1 for i in range(H) if rows[i][j] == "o")
    s_cut = o_row(rs) + o_col(cs)
    t_cut = o_row(rt) + o_col(ct)
    return min(s_cut, t_cut)


# ---------------------------- generators ------------------------------------

TEMPLATES = [
    ["S.o", ".o.", "o.T"],          # sample 1  -> 2
    ["S...", ".oo.", "...T"],       # sample 2  -> 0
    [".S.", ".o.", ".o.", ".T."],  # sample 3  -> -1 (same column)
    ["ST", ".."],                   # same row  -> -1
    ["S.", "T."],                   # same col  -> -1
    ["S.", ".T"],                   # diagonal, no leaves -> 0
    ["So", "oT"],                   # 2x2 full  -> 2
    ["Soo", "ooo", "ooT"],          # 3x3 all leaves diagonal endpoints
    ["S..", ".o.", "..T"],          # unreachable centre leaf -> 0
    ["S.o", ".oo", "o.T"],          # mixed
    ["oS.", ".o.", ".To"],          # S/T not at corners
    ["S..o", "o..o", "o..o", "o..T"],  # two parallel columns of leaves
]


@st.composite
def _rand_grid(draw, max_dim=9):
    H = draw(st.integers(min_value=2, max_value=max_dim))
    W = draw(st.integers(min_value=2, max_value=max_dim))
    dens = draw(st.sampled_from([0, 15, 40, 70, 100]))
    cells = [["o" if draw(st.integers(0, 99)) < dens else "." for _ in range(W)]
             for _ in range(H)]

    mode = draw(st.sampled_from(["same_row", "same_col", "diff", "diff"]))
    rs = draw(st.integers(0, H - 1))
    cs = draw(st.integers(0, W - 1))
    if mode == "same_row":
        rt = rs
        ct = draw(st.sampled_from([c for c in range(W) if c != cs]))
    elif mode == "same_col":
        ct = cs
        rt = draw(st.sampled_from([r for r in range(H) if r != rs]))
    else:  # diff: different row AND different column
        rt = draw(st.sampled_from([r for r in range(H) if r != rs]))
        ct = draw(st.sampled_from([c for c in range(W) if c != cs]))

    cells[rs][cs] = "S"
    cells[rt][ct] = "T"
    return build_stdin(["".join(r) for r in cells])


@st.composite
def _offset_grid(draw):
    # Sweep the -1 boundary: place T at controlled offsets from S, including
    # same-row (dr==0), same-col (dc==0), diagonal-adjacent, and farther.
    H = draw(st.integers(4, 7))
    W = draw(st.integers(4, 7))
    rs = draw(st.integers(1, H - 2))
    cs = draw(st.integers(1, W - 2))
    dr = draw(st.sampled_from([-2, -1, 0, 1, 2, 3]))
    dc = draw(st.sampled_from([-2, -1, 0, 1, 2, 3]))
    rt = min(max(rs + dr, 0), H - 1)
    ct = min(max(cs + dc, 0), W - 1)
    if (rt, ct) == (rs, cs):
        ct = cs + 1 if cs + 1 <= W - 1 else cs - 1

    fill = draw(st.sampled_from(["dot", "o", "mix"]))
    cells = []
    for i in range(H):
        row = []
        for j in range(W):
            if fill == "dot":
                c = "."
            elif fill == "o":
                c = "o"
            else:
                c = "o" if draw(st.integers(0, 1)) else "."
            row.append(c)
        cells.append(row)
    cells[rs][cs] = "S"
    cells[rt][ct] = "T"
    return build_stdin(["".join(r) for r in cells])


@st.composite
def _big_grid(draw):
    # Extreme dimension magnitudes (up to the 100 bound) kept sparse so a
    # correct solver stays fast, plus a "many disjoint paths" large-answer case.
    kind = draw(st.sampled_from(["tall", "wide", "huge", "line"]))
    if kind == "tall":
        H, W = 100, draw(st.sampled_from([2, 3, 4]))
        # a column of leaves in S's column; only the bottom one touches T's row.
        rows = ["".join(("S" if (i == 0 and j == 0) else
                          ("o" if j == 0 else ".")) for j in range(W))
                for i in range(H)]
        rows[H - 1] = rows[H - 1][:W - 1] + "T"
        return build_stdin(rows)
    if kind == "wide":
        H, W = draw(st.sampled_from([2, 3, 4])), 100
        rows = ["".join(("S" if (i == 0 and j == 0) else
                          ("o" if i == 0 else ".")) for j in range(W))
                for i in range(H)]
        rows[H - 1] = rows[H - 1][:W - 1] + "T"
        return build_stdin(rows)
    if kind == "huge":
        H = W = 100
        rows = ["." * W for _ in range(H)]
        rows[0] = "S" + rows[0][1:]
        rows[H - 1] = rows[H - 1][:W - 1] + "T"
        return build_stdin(rows)
    # line: 2 x W, many vertex-disjoint S->T paths (large answer, small grid)
    W = draw(st.integers(10, 30))
    row0 = "S" + "o" * (W - 1)
    row1 = "o" * (W - 1) + "T"
    return build_stdin([row0, row1])


_templates = st.sampled_from([build_stdin(t) for t in TEMPLATES])

_primary = st.one_of(_rand_grid(), _offset_grid(), _templates, _big_grid())
_small = st.one_of(_rand_grid(max_dim=6), _offset_grid(), _templates)


# ------------------------------- tests --------------------------------------

@given(_primary)
@settings(max_examples=45, deadline=None)
def test_format_certificate_range(stdin):
    ans = parse_output(run_candidate(stdin))
    H, W, rows = parse_grid(stdin)
    rs, cs = find_char(rows, "S")
    rt, ct = find_char(rows, "T")
    shares = (rs == rt) or (cs == ct)

    # Negative values other than -1 are never valid.
    assert ans == -1 or ans >= 0, "invalid answer {}".format(ans)

    if shares:
        # S and T share a row/column: frog jumps directly, impossible to block.
        assert ans == -1, "S,T share row/col -> must be -1, got {}".format(ans)
    else:
        # Achievable: a finite, non-negative answer bounded by a known cut.
        assert ans != -1, "S,T do not share row/col -> answer must be finite"
        ub = upper_bound(rows)
        assert 0 <= ans <= ub, \
            "answer {} outside [0, {}] (valid cut size)".format(ans, ub)


@given(_small)
@settings(max_examples=22, deadline=None)
def test_transpose_invariant(stdin):
    H, W, rows = parse_grid(stdin)
    trows = ["".join(rows[i][j] for i in range(H)) for j in range(W)]
    a = parse_output(run_candidate(stdin))
    b = parse_output(run_candidate(build_stdin(trows)))
    assert a == b, "transpose changed answer: {} vs {}".format(a, b)


@st.composite
def _perm_pair(draw):
    stdin = draw(_small)
    H, W, rows = parse_grid(stdin)
    pr = draw(st.permutations(list(range(H))))
    pc = draw(st.permutations(list(range(W))))
    nrows = ["".join(rows[i][j] for j in pc) for i in pr]
    return stdin, build_stdin(nrows)


@given(_perm_pair())
@settings(max_examples=22, deadline=None)
def test_permutation_invariant(pair):
    base, perm = pair
    a = parse_output(run_candidate(base))
    b = parse_output(run_candidate(perm))
    assert a == b, "row/col permutation changed answer: {} vs {}".format(a, b)


@st.composite
def _swap_pair(draw):
    stdin = draw(_small)
    H, W, rows = parse_grid(stdin)
    swapped = []
    for r in rows:
        swapped.append(r.replace("S", "\0").replace("T", "S").replace("\0", "T"))
    if draw(st.booleans()):
        swapped = swapped + ["." * W]        # neutral empty row
    if draw(st.booleans()):
        swapped = [r + "." for r in swapped]  # neutral empty column
    return stdin, build_stdin(swapped)


@given(_swap_pair())
@settings(max_examples=22, deadline=None)
def test_swap_and_padding_invariant(pair):
    base, transformed = pair
    a = parse_output(run_candidate(base))
    b = parse_output(run_candidate(transformed))
    assert a == b, "S/T swap + empty padding changed answer: {} vs {}".format(a, b)