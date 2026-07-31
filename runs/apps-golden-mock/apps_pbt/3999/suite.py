import math
from hypothesis import given, strategies as st, settings, assume
from harness import run_candidate  # run_candidate(stdin: str) -> stdout: str

# ---------------------------------------------------------------------------
# Problem: count distinct cubes (up to 3D rotation, tiles distinguishable by
# number, each tile usable in 4 rotational directions) buildable from 6 of the
# N given 4-corner-colored tiles, such that every cube vertex has its 3 meeting
# corners equal in color.
#
# Known constant: for 6 DISTINCT tiles whose colors allow ALL arrangements to
# be valid, the number of distinct cubes up to rotation is
#     6! * 4^6 / 24 = 720 * 4096 / 24 = 122880
# (the 24-element cube-rotation group acts freely because the 6 tiles are
# distinguishable by number). This is confirmed by the provided example
# (N=6, all-zero tiles -> 122880).
# ---------------------------------------------------------------------------

FULL_CUBES_PER_SUBSET = 720 * 4096 // 24  # == 122880


def _ser(tiles):
    """Serialize a list of 4-tuples into the problem's exact stdin format."""
    lines = [str(len(tiles))]
    lines += ["{} {} {} {}".format(a, b, c, d) for (a, b, c, d) in tiles]
    return "\n".join(lines) + "\n"


def _run_int(stdin):
    """Run candidate, enforce single-integer non-negative output, return it."""
    out = run_candidate(stdin)
    toks = out.split()
    assert len(toks) == 1, "expected a single integer on stdout, got {!r}".format(out)
    try:
        val = int(toks[0])
    except ValueError:
        raise AssertionError("stdout is not an integer: {!r}".format(out))
    assert val >= 0, "count must be non-negative, got {}".format(val)
    return val


# ------------------------------- generators --------------------------------

@st.composite
def _tiles_colorful(draw, min_n=6, max_n=14):
    """Valid tiles biased toward small palettes (so real cubes actually form),
    plus extreme-magnitude palettes {0,999} and the full 0..999 range."""
    n = draw(st.integers(min_n, max_n))
    kind = draw(st.sampled_from(
        ["p0", "p01", "p0999", "p012", "p0123", "psmall", "pfull"]))
    if kind == "pfull":
        tiles = [tuple(draw(st.integers(0, 999)) for _ in range(4))
                 for _ in range(n)]
        return tiles
    if kind == "p0":
        pal = [0]
    elif kind == "p01":
        pal = [0, 1]
    elif kind == "p0999":
        pal = [0, 999]           # extreme magnitudes combined with structure
    elif kind == "p012":
        pal = [0, 1, 2]
    elif kind == "p0123":
        pal = [0, 1, 2, 3]
    else:  # psmall: small random palette (may include extremes)
        k = draw(st.integers(2, 5))
        pal = draw(st.lists(st.integers(0, 999),
                            min_size=k, max_size=k, unique=True))
    tiles = [tuple(draw(st.sampled_from(pal)) for _ in range(4))
             for _ in range(n)]
    return tiles


@st.composite
def _tiles_monochrome(draw):
    """Every tile is monochrome (all 4 corners one color). For monochrome tiles
    a valid cube requires all 6 chosen tiles to share the same color (the face
    adjacency graph of the cube is connected), so the EXACT answer is
        sum_over_colors  C(count_of_that_color, 6) * 122880.
    Returns (tiles, expected_answer)."""
    g = draw(st.integers(1, 4))
    sizes = [draw(st.integers(1, 8)) for _ in range(g)]
    if draw(st.booleans()):
        sizes[0] = draw(st.integers(6, 9))   # bias toward a nonzero group
    while sum(sizes) < 6:
        sizes[0] += 1
    colors = draw(st.lists(st.integers(0, 999),
                           min_size=g, max_size=g, unique=True))
    tiles = []
    for c, s in zip(colors, sizes):
        for _ in range(s):
            tiles.append((c, c, c, c))
    perm = draw(st.permutations(list(range(len(tiles)))))
    tiles = [tiles[i] for i in perm]
    expected = sum(math.comb(s, 6) * FULL_CUBES_PER_SUBSET for s in sizes)
    return tiles, expected


# --------------------------------- tests -----------------------------------

@given(_tiles_colorful())
@settings(max_examples=30, deadline=None)
def test_format_and_upper_bound(tiles):
    # Every valid cube corresponds to choosing 6 tiles and an arrangement up to
    # rotation; there are at most C(N,6)*122880 arrangements total (color
    # constraints only remove cubes). So the answer is bounded.
    n = len(tiles)
    val = _run_int(_ser(tiles))
    upper = math.comb(n, 6) * FULL_CUBES_PER_SUBSET
    assert val <= upper, "count {} exceeds provable upper bound {}".format(val, upper)


@given(_tiles_monochrome())
@settings(max_examples=25, deadline=None)
def test_monochrome_exact_certificate(payload):
    # Exact certificate for the monochrome family (derivable without solving the
    # general problem). Confirmed against provided example (N=6 all-zero -> 122880).
    tiles, expected = payload
    val = _run_int(_ser(tiles))
    assert val == expected, \
        "monochrome case: expected {}, got {}".format(expected, val)


@given(_tiles_colorful())
@settings(max_examples=15, deadline=None)
def test_row_permutation_invariant(tiles):
    # The answer depends only on the collection of tiles, not on the order in
    # which they are listed (renumbering tiles is a bijection on cubes).
    base = _run_int(_ser(tiles))
    rev = list(reversed(tiles))
    # rotate by one to also exercise a non-reversal permutation
    perm = tiles[1:] + tiles[:1] if len(tiles) > 1 else tiles
    a = _run_int(_ser(rev))
    assert a == base, "reversing tile order changed count: {} vs {}".format(a, base)
    b = _run_int(_ser(perm))
    assert b == base, "rotating tile order changed count: {} vs {}".format(b, base)


@given(_tiles_colorful(), st.integers(1, 999))
@settings(max_examples=15, deadline=None)
def test_color_relabel_invariant(tiles, k):
    # Applying a color bijection c -> (c+k) mod 1000 preserves all color
    # equalities, hence the set of valid cubes and the count are unchanged.
    base = _run_int(_ser(tiles))
    shifted = [tuple((v + k) % 1000 for v in t) for t in tiles]
    val = _run_int(_ser(shifted))
    assert val == base, \
        "color shift by {} changed count: {} vs {}".format(k, val, base)


@given(_tiles_colorful(min_n=6, max_n=12))
@settings(max_examples=10, deadline=None)
def test_add_tile_isolated_and_monotone(tiles):
    base = _run_int(_ser(tiles))

    # Adding a tile with a globally-unique color cannot create any new valid
    # cube (each of its corners is a cube vertex needing two other tiles with
    # that color), so the count is unchanged.
    used = set()
    for t in tiles:
        used.update(t)
    free = next((c for c in range(1000) if c not in used), None)
    assume(free is not None)
    iso = tiles + [(free, free, free, free)]
    val_iso = _run_int(_ser(iso))
    assert val_iso == base, \
        "adding an isolated tile changed count: {} vs {}".format(val_iso, base)

    # Adding an arbitrary tile can only keep or increase the count (all previous
    # cubes remain constructible).
    extra = tiles + [tiles[0]]
    val_more = _run_int(_ser(extra))
    assert val_more >= base, \
        "adding a tile decreased count: {} < {}".format(val_more, base)