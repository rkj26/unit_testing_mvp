# APPS/3692 GOLDEN PBT SUITE (Opus, blind/spec-only)

from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

# =====================================================================
# Problem: count the number of regions (faces, INCLUDING the single
# infinite one) into which n circles (1 <= n <= 3) divide the plane.
# Coords x,y in [-10,10], radius r in [1,10], all integers; no two
# circles identical.
#
# Sound facts used below (none of them require solving the problem):
#   * A single circle -> exactly 2 regions.
#   * For n circles:  n+1 <= R <= n*n - n + 2  (min = all separate,
#     max = general position; both are classical bounds).
#   * The region count is invariant under any rigid motion (translation,
#     reflection, 90-deg rotation) and under any similarity scaling, and
#     under reordering the circles.
#   * Adding a circle whose boundary does NOT touch/cross any existing
#     circle boundary (fully separate OR strictly nested w.r.t. each)
#     increases the region count by EXACTLY 1 (Euler: dV=1,dE=1,dC=1).
#   * n concentric circles, or n pairwise-far-apart circles, give n+1.
# =====================================================================

MAXC = 10   # |x|,|y| <= 10 and r <= 10


# ---------------------------------------------------------------- helpers
def _fmt(circles):
    lines = [str(len(circles))]
    for (x, y, r) in circles:
        lines.append("{} {} {}".format(x, y, r))
    return "\n".join(lines) + "\n"


def _parse(stdin):
    rows = stdin.strip().split("\n")
    n = int(rows[0])
    out = []
    for i in range(1, n + 1):
        x, y, r = map(int, rows[i].split())
        out.append((x, y, r))
    return out


def _out_int(stdout):
    toks = stdout.split()
    assert toks, "empty output: %r" % (stdout,)
    tok = toks[0]
    try:
        return int(tok)
    except ValueError:
        raise AssertionError("output is not an integer: %r" % (stdout,))


def _distinct_radii(draw, n, rmax):
    rs, used = [], set()
    for _ in range(60):
        if len(rs) >= n:
            break
        r = draw(st.integers(1, rmax))
        if r not in used:
            used.add(r)
            rs.append(r)
    r = 1
    while len(rs) < n:
        if r not in used:
            used.add(r)
            rs.append(r)
        r += 1
    return rs[:n]


def _fix(circles, n, cmax, rmax):
    """Clamp to bounds, dedupe, and guarantee EXACTLY n distinct valid circles."""
    out, used = [], set()
    for (x, y, r) in circles:
        x = max(-cmax, min(cmax, int(x)))
        y = max(-cmax, min(cmax, int(y)))
        r = max(1, min(rmax, int(r)))
        c = (x, y, r)
        if c not in used and len(out) < n:
            used.add(c)
            out.append(c)
    if len(out) < n:
        for x in range(-cmax, cmax + 1):
            for y in range(-cmax, cmax + 1):
                for r in range(1, rmax + 1):
                    if len(out) >= n:
                        break
                    c = (x, y, r)
                    if c not in used:
                        used.add(c)
                        out.append(c)
                if len(out) >= n:
                    break
            if len(out) >= n:
                break
    return out[:n]


def _config(draw, cmax, rmax, nfix=None):
    """Rich generator biased toward degenerate / boundary geometry."""
    n = nfix if nfix is not None else draw(st.integers(1, 3))
    mode = draw(st.sampled_from(
        ["dense", "wide", "concentric", "collinear", "common", "tangent"]))

    if mode == "dense":                       # small box -> many crossings/tangencies
        c = min(4, cmax)
        rr = min(4, rmax)
        circles = [(draw(st.integers(-c, c)),
                    draw(st.integers(-c, c)),
                    draw(st.integers(1, rr))) for _ in range(n)]
    elif mode == "wide":                      # extremes at the coordinate/radius bounds
        circles = [(draw(st.sampled_from([-cmax, -cmax + 1, 0, cmax - 1, cmax])),
                    draw(st.sampled_from([-cmax, -cmax + 1, 0, cmax - 1, cmax])),
                    draw(st.sampled_from([1, 2, rmax - 1, rmax]))) for _ in range(n)]
    elif mode == "concentric":                # same centre, distinct radii (nested)
        cx = draw(st.integers(-cmax, cmax))
        cy = draw(st.integers(-cmax, cmax))
        circles = [(cx, cy, r) for r in _distinct_radii(draw, n, rmax)]
    elif mode == "collinear":                 # like the examples: equal r on a line
        r = draw(st.integers(1, min(4, rmax)))
        d = draw(st.sampled_from([r, 2 * r, max(1, 2 * r - 1), 2 * r + 1]))
        start = draw(st.integers(-cmax, 0))
        circles = [(start + i * d, 0, r) for i in range(n)]
    elif mode == "common":                    # all pass through the origin (concurrent)
        r = draw(st.integers(1, min(cmax, rmax)))
        menu = [(0, r, r), (r, 0, r), (0, -r, r), (-r, 0, r)]
        idxs = list(draw(st.permutations(range(4))))
        circles = [menu[i] for i in idxs[:n]]
    else:                                     # explicit tangency (exact threshold)
        r1 = draw(st.integers(1, rmax))
        r2 = draw(st.integers(1, rmax))
        d = (r1 + r2) if draw(st.booleans()) else abs(r1 - r2)   # ext / int tangent
        if d <= 2 * cmax:
            ax = draw(st.integers(-cmax, cmax - d))
            circles = [(ax, 0, r1), (ax + d, 0, r2)]
        else:
            circles = [(0, 0, r1)]
        if n >= 3:
            circles.append((draw(st.integers(-cmax, cmax)),
                            draw(st.integers(-cmax, cmax)),
                            draw(st.integers(1, rmax))))

    return _fix(circles, n, cmax, rmax)


# ---------------------------------------------------------------- strategies
@st.composite
def gen_config(draw):
    return _fmt(_config(draw, MAXC, MAXC))


@st.composite
def gen_config_small(draw):                   # small so we can scale up in bounds
    return _fmt(_config(draw, 3, 3))


@st.composite
def gen_for_add(draw):                         # base of 1 or 2 circles
    return _fmt(_config(draw, MAXC, MAXC, nfix=draw(st.integers(1, 2))))


@st.composite
def gen_separated(draw):
    kind = draw(st.sampled_from(["single", "concentric", "disjoint"]))
    if kind == "single":
        return _fmt([(draw(st.integers(-MAXC, MAXC)),
                      draw(st.integers(-MAXC, MAXC)),
                      draw(st.integers(1, MAXC)))])
    n = draw(st.integers(1, 3))
    if kind == "concentric":
        cx = draw(st.integers(-MAXC, MAXC))
        cy = draw(st.integers(-MAXC, MAXC))
        return _fmt([(cx, cy, r) for r in _distinct_radii(draw, n, MAXC)])
    # disjoint: far-apart anchors (min pairwise centre distance 9) with tiny radii
    anchors = [(-9, -9), (9, 9), (9, -9), (-9, 9),
               (0, 9), (0, -9), (9, 0), (-9, 0)]
    idxs = list(draw(st.permutations(range(len(anchors)))))[:n]
    circles = [(anchors[i][0], anchors[i][1], draw(st.integers(1, 3))) for i in idxs]
    return _fmt(circles)


# ---------------------------------------------------------------- tests
@given(gen_config())
@settings(max_examples=45, deadline=None)
def test_format_and_bounds(stdin):
    circles = _parse(stdin)
    n = len(circles)
    out = run_candidate(stdin)
    val = _out_int(out)
    lo, hi = n + 1, n * n - n + 2
    assert lo <= val <= hi, (
        "region count %d outside sound range [%d,%d] for n=%d\ninput=%r out=%r"
        % (val, lo, hi, n, stdin, out))


@given(gen_separated())
@settings(max_examples=30, deadline=None)
def test_separated_certificate(stdin):
    # single circle, concentric circles, or pairwise-far-apart circles:
    # a correct answer MUST be exactly n+1.
    circles = _parse(stdin)
    n = len(circles)
    val = _out_int(run_candidate(stdin))
    assert val == n + 1, (
        "clearly-separated %d circle(s) must give %d regions, got %d\ninput=%r"
        % (n, n + 1, val, stdin))


@given(gen_config())
@settings(max_examples=18, deadline=None)
def test_isometry_invariance(stdin):
    # Region count is invariant under reflection / 90-deg rotation,
    # a bounds-safe translation, and reordering the circles.
    circles = _parse(stdin)
    n = len(circles)
    base = _out_int(run_candidate(stdin))
    assert (n + 1) <= base <= (n * n - n + 2)

    isos = [
        lambda x, y: (x, y),
        lambda x, y: (-x, y),
        lambda x, y: (x, -y),
        lambda x, y: (-x, -y),
        lambda x, y: (-y, x),
        lambda x, y: (y, -x),
        lambda x, y: (y, x),
        lambda x, y: (-y, -x),
    ]
    key = sum(abs(x) + abs(y) + r for (x, y, r) in circles)
    iso = isos[key % len(isos)]
    tc = [iso(x, y) + (r,) for (x, y, r) in circles]

    xs = [c[0] for c in tc]
    ys = [c[1] for c in tc]
    dx = (MAXC - max(xs)) if key % 2 == 0 else (-MAXC - min(xs))
    dy = (MAXC - max(ys)) if (key // 2) % 2 == 0 else (-MAXC - min(ys))
    tc = [(x + dx, y + dy, r) for (x, y, r) in tc]
    tc = list(reversed(tc))                     # also exercises order-invariance

    timg = _out_int(run_candidate(_fmt(tc)))
    assert timg == base, (
        "rigid motion + reorder changed region count: base=%d image=%d\n"
        "base_in=%r\nimg_in=%r" % (base, timg, stdin, _fmt(tc)))


@given(gen_config_small())
@settings(max_examples=16, deadline=None)
def test_scaling_invariance(stdin):
    # Similarity scaling preserves the whole arrangement's topology,
    # hence the region count is unchanged.
    circles = _parse(stdin)
    n = len(circles)
    base = _out_int(run_candidate(stdin))
    assert (n + 1) <= base <= (n * n - n + 2)

    m = max(max(abs(x), abs(y), r) for (x, y, r) in circles)
    kmax = MAXC // m
    if kmax < 2:
        return
    key = sum(abs(x) + abs(y) + r for (x, y, r) in circles)
    k = 3 if (kmax >= 3 and key % 2 == 1) else 2
    scaled = [(x * k, y * k, r * k) for (x, y, r) in circles]
    simg = _out_int(run_candidate(_fmt(scaled)))
    assert simg == base, (
        "scaling by %d changed region count: base=%d image=%d\n"
        "base_in=%r\nscaled_in=%r" % (k, base, simg, stdin, _fmt(scaled)))


@given(gen_for_add())
@settings(max_examples=18, deadline=None)
def test_add_boundary_disjoint_adds_one(stdin):
    # Adding a circle whose boundary neither touches nor crosses ANY existing
    # circle (fully separate OR strictly nested w.r.t. each) must add exactly
    # one region.  We verify the geometric precondition with exact integer
    # arithmetic before asserting.
    base = _parse(stdin)
    n = len(base)
    r0 = _out_int(run_candidate(stdin))
    assert (n + 1) <= r0 <= (n * n - n + 2)

    used = set(base)
    candidates = [(9, 9, 1), (-9, -9, 1), (9, -9, 1), (-9, 9, 1),
                  (0, 9, 1), (9, 0, 1), (-9, 0, 1), (0, -9, 1),
                  (10, 10, 1), (-10, -10, 1), (10, -10, 1), (-10, 10, 1),
                  (9, 9, 2), (-9, -9, 2)]
    new = None
    for (xn, yn, rn) in candidates:
        if (xn, yn, rn) in used:
            continue
        ok = True
        for (xi, yi, ri) in base:
            d2 = (xn - xi) ** 2 + (yn - yi) ** 2
            separate = d2 > (rn + ri) ** 2
            nested = d2 < (rn - ri) ** 2
            if not (separate or nested):
                ok = False
                break
        if ok:
            new = (xn, yn, rn)
            break
    if new is None:
        return   # could not place a safe extra circle; skip this example

    r1 = _out_int(run_candidate(_fmt(base + [new])))
    assert r1 == r0 + 1, (
        "adding a boundary-disjoint circle must add exactly 1 region: "
        "r0=%d r1=%d\nbase=%r new=%r" % (r0, r1, stdin, new))
