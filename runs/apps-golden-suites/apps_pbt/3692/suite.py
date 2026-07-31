from hypothesis import given, strategies as st, settings
from harness import run_candidate  # run_candidate(stdin: str) -> stdout: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse(stdin):
    lines = stdin.strip().split("\n")
    n = int(lines[0])
    circles = []
    for i in range(1, n + 1):
        x, y, r = map(int, lines[i].split())
        circles.append((x, y, r))
    return circles


def _build(circles):
    out = [str(len(circles))]
    for (x, y, r) in circles:
        out.append(f"{x} {y} {r}")
    return "\n".join(out) + "\n"


def _regions(stdin):
    out = run_candidate(stdin)
    toks = out.split()
    assert len(toks) == 1, f"expected a single integer, got {out!r}"
    return int(toks[0])


# ---------------------------------------------------------------------------
# Input strategies (all produce inputs that respect every stated constraint:
#   1<=n<=3, -10<=x,y<=10, 1<=r<=10, no two identical (x,y,r) triples)
# ---------------------------------------------------------------------------
@st.composite
def make_input(draw):
    mode = draw(st.integers(min_value=0, max_value=3))
    n = draw(st.integers(min_value=1, max_value=3))

    if mode == 1:
        # concentric: identical center, distinct radii (nested)
        cx = draw(st.integers(-10, 10))
        cy = draw(st.integers(-10, 10))
        radii = draw(st.lists(st.integers(1, 10), min_size=n, max_size=n, unique=True))
        circles = [(cx, cy, r) for r in radii]
    elif mode == 2:
        # externally-tangent chain along a horizontal line (small radii keep it
        # inside the coordinate box); tangency is a classic degenerate edge case
        radii = [draw(st.integers(1, 2)) for _ in range(n)]
        cy = draw(st.integers(-8, 8))
        circles = []
        for i, r in enumerate(radii):
            if i == 0:
                cx = -5
            else:
                cx = circles[-1][0] + circles[-1][2] + r
            circles.append((cx, cy, r))
    else:
        # uniform random: mode 0 uses the full box, mode 3 uses a tight box to
        # force many intersections / overlaps / nesting
        if mode == 0:
            lo, hi, rmax = -10, 10, 10
        else:
            lo, hi, rmax = -4, 4, 5
        circles = draw(
            st.lists(
                st.tuples(
                    st.integers(lo, hi),
                    st.integers(lo, hi),
                    st.integers(1, rmax),
                ),
                min_size=n,
                max_size=n,
                unique=True,
            )
        )
    return _build(circles)


@st.composite
def make_input_concentric(draw):
    n = draw(st.integers(1, 3))
    cx = draw(st.integers(-10, 10))
    cy = draw(st.integers(-10, 10))
    radii = draw(st.lists(st.integers(1, 10), min_size=n, max_size=n, unique=True))
    return _build([(cx, cy, r) for r in radii])


@st.composite
def make_input_disjoint(draw):
    # base circles confined to the left (rightmost point <= -3),
    # one extra circle confined to the right (leftmost point >= 3),
    # so the extra circle is provably disjoint & external to every base circle.
    n_base = draw(st.integers(1, 2))
    base = draw(
        st.lists(
            st.tuples(
                st.integers(-10, -6),
                st.integers(-10, 10),
                st.integers(1, 3),
            ),
            min_size=n_base,
            max_size=n_base,
            unique=True,
        )
    )
    extra = (
        draw(st.integers(6, 10)),
        draw(st.integers(-10, 10)),
        draw(st.integers(1, 3)),
    )
    return _build(base), _build(base + [extra])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@given(make_input())
@settings(max_examples=50, deadline=None)
def test_bounds_and_format(stdin):
    # Output is a single integer; every circle adds at least one region
    # (min = n+1, achieved by disjoint/nested circles) and at most creates
    # 2(k-1) new arcs when it is the k-th circle (max = n^2 - n + 2).
    circles = _parse(stdin)
    n = len(circles)
    val = _regions(stdin)
    assert val >= n + 1, f"regions {val} below minimum {n + 1} for n={n}"
    assert val <= n * n - n + 2, f"regions {val} above maximum {n * n - n + 2} for n={n}"


@given(make_input())
@settings(max_examples=50, deadline=None)
def test_permutation_invariance(stdin):
    # The answer depends only on the SET of circles, not their listing order.
    circles = _parse(stdin)
    base = _regions(stdin)
    rev = _regions(_build(list(reversed(circles))))
    assert rev == base, f"reversed order changed answer: {rev} != {base}"
    if len(circles) >= 2:
        rot = circles[1:] + circles[:1]
        got = _regions(_build(rot))
        assert got == base, f"rotated order changed answer: {got} != {base}"


@given(make_input())
@settings(max_examples=50, deadline=None)
def test_isometry_invariance(stdin):
    # Rigid motions (reflections, 90-degree rotation, translation) preserve the
    # geometry and therefore the region count. The [-10,10] box is symmetric, so
    # negations/swaps stay valid; translations are chosen to stay inside the box.
    circles = _parse(stdin)
    base = _regions(stdin)

    transforms = [
        lambda x, y: (x, -y),   # reflect across x-axis
        lambda x, y: (-x, y),   # reflect across y-axis
        lambda x, y: (-x, -y),  # 180-degree rotation
        lambda x, y: (y, x),    # reflect across y=x
        lambda x, y: (-y, x),   # 90-degree rotation
    ]
    for t in transforms:
        moved = [(t(x, y)[0], t(x, y)[1], r) for (x, y, r) in circles]
        got = _regions(_build(moved))
        assert got == base, f"isometry changed answer: {got} != {base}"

    xs = [x for x, y, r in circles]
    ys = [y for x, y, r in circles]
    for dx, dy in [(10 - max(xs), 10 - max(ys)), (-10 - min(xs), -10 - min(ys))]:
        shifted = [(x + dx, y + dy, r) for (x, y, r) in circles]
        got = _regions(_build(shifted))
        assert got == base, f"translation ({dx},{dy}) changed answer: {got} != {base}"


@given(make_input_disjoint())
@settings(max_examples=50, deadline=None)
def test_add_disjoint_circle(pair):
    # A circle that is external to and disjoint from every existing circle lies
    # in the unbounded region and splits it into exactly one new bounded piece,
    # so it must increase the region count by exactly 1.
    base_stdin, combined_stdin = pair
    rb = _regions(base_stdin)
    rc = _regions(combined_stdin)
    assert rc == rb + 1, f"adding a disjoint circle changed regions {rb} -> {rc} (expected +1)"


@given(make_input_concentric())
@settings(max_examples=50, deadline=None)
def test_concentric_exact(stdin):
    # Concentric circles with distinct radii are strictly nested; their
    # boundaries never intersect, so each adds exactly one region: total n+1.
    circles = _parse(stdin)
    n = len(circles)
    val = _regions(stdin)
    assert val == n + 1, f"{n} concentric circles must give {n + 1} regions, got {val}"
