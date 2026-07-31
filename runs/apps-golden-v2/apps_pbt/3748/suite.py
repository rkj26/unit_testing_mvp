from collections import Counter

from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build(H, W, rows):
    return "{} {}\n".format(H, W) + "\n".join(rows) + "\n"


def _parse(stdin):
    lines = stdin.split("\n")
    H, W = map(int, lines[0].split())
    rows = lines[1:1 + H]
    return H, W, rows


def _norm(out):
    return out.strip()


def _parity_forbids(H, W, rows):
    """Necessary condition for symmetry (letter multiset is invariant under
    row/col swaps; a point-symmetric grid pairs every cell except the single
    center cell which exists iff both H and W are odd).
      - H*W even  -> EVERY letter count must be even.
      - H*W odd   -> EXACTLY one letter count may be odd.
    Returns True when symmetry is provably impossible (=> answer must be NO)."""
    cnt = Counter()
    for r in rows:
        cnt.update(r)
    odd = sum(1 for v in cnt.values() if v % 2 == 1)
    if (H * W) % 2 == 0:
        return odd > 0
    else:
        return odd != 1


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------
def _dim():
    # bias toward extremes / small sizes while still covering the whole box
    return st.one_of(st.just(1), st.just(2), st.just(11), st.just(12),
                     st.integers(min_value=1, max_value=12))


@st.composite
def any_input(draw):
    """Arbitrary valid grid; small alphabets create heavy duplicates /
    all-equal structure, full alphabet gives all-distinct-ish rows."""
    H = draw(_dim())
    W = draw(_dim())
    alpha = draw(st.sampled_from(
        ["a", "ab", "abc", "abcd", "abcdefghijklmnopqrstuvwxyz"]))
    rows = ["".join(draw(st.sampled_from(alpha)) for _ in range(W))
            for _ in range(H)]
    return _build(H, W, rows)


@st.composite
def sym_input(draw):
    """A point-symmetric grid (answer must be YES), then rows and columns are
    randomly permuted -- still YES, since the operations are exactly row/col
    swaps and are reversible.  Exercises the region where the candidate must
    actually FIND an arrangement rather than see an obvious symmetric grid."""
    H = draw(_dim())
    W = draw(_dim())
    alpha = draw(st.sampled_from(["a", "ab", "abc",
                                  "abcdefghijklmnopqrstuvwxyz"]))
    g = [[None] * W for _ in range(H)]
    for i in range(H):
        for j in range(W):
            if g[i][j] is None:
                c = draw(st.sampled_from(alpha))
                g[i][j] = c
                g[H - 1 - i][W - 1 - j] = c
    rows = ["".join(r) for r in g]
    row_perm = draw(st.permutations(range(H)))
    col_perm = draw(st.permutations(range(W)))
    rows = [rows[p] for p in row_perm]
    rows = ["".join(r[c] for c in col_perm) for r in rows]
    return _build(H, W, rows)


@st.composite
def no_input(draw):
    """A grid that violates the letter-count parity condition, so symmetry is
    provably impossible (answer must be NO)."""
    H = draw(_dim())
    W = draw(_dim())
    if H * W == 1:               # 1x1 is always YES; bump so we can force NO
        W = 2
    total = H * W
    g = [["a"] * W for _ in range(H)]
    if total % 2 == 0:
        # one 'b' -> two letters have odd count -> forbidden for even total
        g[0][0] = "b"
    else:
        # both dims odd, total >= 3 -> three letters odd -> forbidden (need 1)
        if W >= 2:
            g[0][0] = "b"
            g[0][1] = "c"
        else:
            g[0][0] = "b"
            g[1][0] = "c"
    rows = ["".join(r) for r in g]
    return _build(H, W, rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@given(any_input())
@settings(max_examples=60, deadline=None)
def test_format_and_parity_certificate(stdin):
    out = _norm(run_candidate(stdin))
    assert out in ("YES", "NO"), "output must be YES or NO, got %r" % out
    H, W, rows = _parse(stdin)
    if _parity_forbids(H, W, rows):
        assert out == "NO", (
            "letter-count parity makes symmetry impossible, expected NO")


@given(sym_input())
@settings(max_examples=50, deadline=None)
def test_symmetric_is_yes(stdin):
    out = _norm(run_candidate(stdin))
    assert out == "YES", "grid is (a permutation of) a symmetric grid -> YES"


@given(no_input())
@settings(max_examples=50, deadline=None)
def test_parity_violation_is_no(stdin):
    out = _norm(run_candidate(stdin))
    assert out == "NO", "parity-violating grid can never be made symmetric"


@given(any_input())
@settings(max_examples=25, deadline=None)
def test_metamorphic_perm_relabel(stdin):
    # reversing row order, reversing each row, and shifting every letter by one
    # are (row perm) + (col perm) + (alphabet bijection): all answer-preserving
    H, W, rows = _parse(stdin)
    o1 = _norm(run_candidate(stdin))
    assert o1 in ("YES", "NO")

    def shift(c):
        return chr((ord(c) - 97 + 1) % 26 + 97)

    new_rows = ["".join(shift(ch) for ch in r[::-1]) for r in rows[::-1]]
    o2 = _norm(run_candidate(_build(H, W, new_rows)))
    assert o2 in ("YES", "NO")
    assert o1 == o2, "row/col permutation + relabel must not change the answer"


@given(any_input())
@settings(max_examples=25, deadline=None)
def test_metamorphic_transpose(stdin):
    # transposing the grid preserves solvability (row<->col swaps and the
    # central-symmetry condition are both symmetric under transpose)
    H, W, rows = _parse(stdin)
    o1 = _norm(run_candidate(stdin))
    trows = ["".join(rows[i][j] for i in range(H)) for j in range(W)]
    o2 = _norm(run_candidate(_build(W, H, trows)))
    assert o1 in ("YES", "NO") and o2 in ("YES", "NO")
    assert o1 == o2, "transpose must not change the answer"
