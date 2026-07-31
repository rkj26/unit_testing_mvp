from hypothesis import given, strategies as st, settings, assume
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str  (the harness provides this)

# ----------------------------------------------------------------------------
# Problem recap (derived from the SPEC only):
#   c[i][j] = a[i] * b[j].  A subrectangle spanning h consecutive rows and w
#   consecutive columns has sum = (sum of that a-window) * (sum of that b-window).
#   For fixed dimensions (h, w) the MINIMUM possible rectangle sum is
#       A_h * B_w
#   where A_h is the minimum sum over all contiguous windows of length h in a
#   (and B_w analogously for b), because both factors are positive and are
#   minimised independently.  Therefore:
#       area h*w is achievable  <==>  A_h * B_w <= x.
#   The answer is the largest achievable area, or 0 if none.
#
# These facts let us write SOUND certificate checks: we exhibit real feasible
# rectangles (lower bound) and require the returned value to itself be a
# realisable area (no over-claim).  We never trust a black-box "solver output".
# ----------------------------------------------------------------------------

LIM = 2_000_000_000


def min_window_sums(arr):
    """res[L] = minimum sum of a contiguous window of length L, for L in 1..len(arr)."""
    n = len(arr)
    pref = [0] * (n + 1)
    for i, v in enumerate(arr):
        pref[i + 1] = pref[i] + v
    res = [0] * (n + 1)
    for L in range(1, n + 1):
        best = None
        for s in range(0, n - L + 1):
            cur = pref[s + L] - pref[s]
            if best is None or cur < best:
                best = cur
        res[L] = best
    return res


def fmt(n, m, a, b, x):
    return f"{n} {m}\n{' '.join(map(str, a))}\n{' '.join(map(str, b))}\n{x}\n"


def parse_stdin(s):
    lines = s.split("\n")
    n, m = map(int, lines[0].split())
    a = list(map(int, lines[1].split()))
    b = list(map(int, lines[2].split()))
    x = int(lines[3])
    return n, m, a, b, x


def safe_int(stdout):
    try:
        return int(stdout.split()[0])
    except Exception:
        raise AssertionError(f"output is not a single integer: {stdout!r}")


def assert_certificate(n, m, a, b, x, s, A, B, best):
    # FORMAT / RANGE invariant.
    assert 0 <= s <= n * m, f"answer {s} out of range [0, {n*m}]"
    if best == 0:
        # No rectangle (not even a single cell) fits -> answer must be 0.
        assert s == 0, f"claimed {s} but no rectangle is feasible (min cell {A[1]*B[1]} > x={x})"
    else:
        # LOWER-BOUND certificate: `best` is the area of an exhibited feasible
        # rectangle, so the optimum must be at least that large.
        assert s >= best, f"claimed {s} < exhibited feasible area {best}"
        # NO-OVERCLAIM certificate: the returned area must itself be realisable,
        # i.e. factor as h*w (h<=n, w<=m) with A_h*B_w <= x.  Combined with the
        # lower bound this pins s to the true optimum, soundly.
        ok = False
        for h in range(1, n + 1):
            if s % h == 0:
                w = s // h
                if 1 <= w <= m and A[h] * B[w] <= x:
                    ok = True
                    break
        assert ok, f"claimed area {s} is not a realisable (feasible) rectangle area"


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

@st.composite
def make_input(draw, cap=80):
    # Sizes: heavy bias toward 1 and small values, occasional larger.
    n = draw(st.one_of(st.sampled_from([1, 1, 1, 2, 2, 3, 3, 4, 5]), st.integers(1, cap)))
    m = draw(st.one_of(st.sampled_from([1, 1, 1, 2, 2, 3, 3, 4, 5]), st.integers(1, cap)))
    n = min(max(n, 1), cap)
    m = min(max(m, 1), cap)

    def gen_array(length):
        mode = draw(st.integers(0, 3))
        if mode == 0:  # all-equal (degenerate structure)
            v = draw(st.sampled_from([1, 2, 3, 1000, 1999, 2000]))
            if draw(st.booleans()):
                v = draw(st.integers(1, 2000))
            return [v] * length
        elif mode == 1:  # extreme mix of MIN and MAX magnitude
            return [draw(st.sampled_from([1, 2000])) for _ in range(length)]
        elif mode == 2:  # tiny values
            return [draw(st.integers(1, 3)) for _ in range(length)]
        else:  # full random range
            return [draw(st.integers(1, 2000)) for _ in range(length)]

    a = gen_array(n)
    b = gen_array(m)

    A = min_window_sums(a)
    B = min_window_sums(b)

    # x biased to EXACT thresholds of feasibility (and just inside/outside).
    opts = set()
    opts.add(1)
    opts.add(LIM)
    opts.add(A[1] * B[1])           # smallest single cell
    opts.add(A[1] * B[1] - 1)
    opts.add(A[n] * B[m])           # whole-matrix sum
    opts.add(A[n] * B[m] - 1)
    opts.add(A[n] * B[m] + 1)
    for _ in range(3):
        h = draw(st.integers(1, n))
        w = draw(st.integers(1, m))
        base = A[h] * B[w]
        opts.update([base, base - 1, base + 1])
    opts = sorted({v for v in opts if 1 <= v <= LIM})

    if draw(st.booleans()):
        x = draw(st.integers(1, LIM))
    else:
        x = draw(st.sampled_from(opts))
    x = max(1, min(LIM, x))
    return fmt(n, m, a, b, x)


@st.composite
def make_small(draw):
    # Deterministic-ish sweep over a tiny bounded box so magic-value guards
    # keyed to a specific small configuration cannot slip through.
    n = draw(st.integers(1, 3))
    m = draw(st.integers(1, 3))
    a = draw(st.lists(st.integers(1, 3), min_size=n, max_size=n))
    b = draw(st.lists(st.integers(1, 3), min_size=m, max_size=m))
    A = min_window_sums(a)
    B = min_window_sums(b)
    opts = set([1])
    for h in range(1, n + 1):
        for w in range(1, m + 1):
            base = A[h] * B[w]
            opts.update([base, base - 1, base + 1])
    opts = sorted({v for v in opts if 1 <= v <= LIM})
    x = draw(st.sampled_from(opts))
    return fmt(n, m, a, b, x)


@st.composite
def make_large_equal(draw):
    # Extreme SIZE combined with extreme/threshold MAGNITUDE, all-equal arrays
    # (closed-form reference stays cheap even at n,m ~ 2000).
    n = draw(st.sampled_from([1, 2, 1000, 1500, 1999, 2000]))
    m = draw(st.sampled_from([1, 2, 1000, 1500, 1999, 2000]))
    va = draw(st.sampled_from([1, 2, 1000, 2000]))
    vb = draw(st.sampled_from([1, 2, 1000, 2000]))
    a = [va] * n
    b = [vb] * m
    h = draw(st.integers(1, n))
    w = draw(st.integers(1, m))
    base = h * va * w * vb
    cand = [1, LIM, va * vb, va * vb - 1, base, base - 1, base + 1, n * va * m * vb]
    x = draw(st.sampled_from(cand))
    x = max(1, min(LIM, x))
    return fmt(n, m, a, b, x)


def best_equal(n, m, va, vb, x):
    prod = va * vb
    best = 0
    for h in range(1, n + 1):
        hp = h * prod
        if hp > x:
            break  # even width-1 infeasible; larger h only worse
        w = x // hp
        if w > m:
            w = m
        if w >= 1:
            area = h * w
            if area > best:
                best = area
    return best


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@given(make_input(cap=80))
@settings(max_examples=45, deadline=None)
def test_certificate_main(stdin):
    n, m, a, b, x = parse_stdin(stdin)
    A = min_window_sums(a)
    B = min_window_sums(b)
    best = 0
    for h in range(1, n + 1):
        Ah = A[h]
        for w in range(1, m + 1):
            if Ah * B[w] <= x:
                area = h * w
                if area > best:
                    best = area
    s = safe_int(run_candidate(stdin))
    assert_certificate(n, m, a, b, x, s, A, B, best)


@given(make_small())
@settings(max_examples=40, deadline=None)
def test_small_sweep(stdin):
    n, m, a, b, x = parse_stdin(stdin)
    A = min_window_sums(a)
    B = min_window_sums(b)
    best = 0
    for h in range(1, n + 1):
        Ah = A[h]
        for w in range(1, m + 1):
            if Ah * B[w] <= x:
                area = h * w
                if area > best:
                    best = area
    s = safe_int(run_candidate(stdin))
    assert_certificate(n, m, a, b, x, s, A, B, best)


@given(make_input(cap=20))
@settings(max_examples=15, deadline=None)
def test_transpose_symmetry(stdin):
    # Transposing the matrix (swap a<->b, n<->m) preserves the set of rectangle
    # areas and sums, so the answer must be identical.  Independent of any
    # reference computation.
    n, m, a, b, x = parse_stdin(stdin)
    s1 = safe_int(run_candidate(stdin))
    s2 = safe_int(run_candidate(fmt(m, n, b, a, x)))
    assert 0 <= s1 <= n * m
    assert 0 <= s2 <= n * m
    assert s1 == s2, f"transpose changed the answer: {s1} vs {s2}"


@given(make_input(cap=20))
@settings(max_examples=15, deadline=None)
def test_scale_invariance(stdin):
    # Scaling every a_i by k multiplies every rectangle sum by k, so feasibility
    # w.r.t. x is identical to feasibility w.r.t. x*k.  Answer must be unchanged.
    n, m, a, b, x = parse_stdin(stdin)
    ma = max(a)
    k = min(2000 // ma, LIM // x, 6)
    assume(k >= 2)
    a2 = [v * k for v in a]
    x2 = x * k
    s1 = safe_int(run_candidate(stdin))
    s2 = safe_int(run_candidate(fmt(n, m, a2, b, x2)))
    assert s1 == s2, f"scaling by {k} changed the answer: {s1} vs {s2}"


@given(make_large_equal())
@settings(max_examples=18, deadline=None)
def test_large_equal(stdin):
    n, m, a, b, x = parse_stdin(stdin)
    va, vb = a[0], b[0]
    best = best_equal(n, m, va, vb, x)
    s = safe_int(run_candidate(stdin))
    assert 0 <= s <= n * m, f"answer {s} out of range [0, {n*m}]"
    if best == 0:
        assert s == 0, f"claimed {s} but nothing fits (min cell {va*vb} > x={x})"
    else:
        assert s >= best, f"claimed {s} < exhibited feasible area {best}"
        ok = False
        for h in range(1, n + 1):
            if s % h == 0:
                w = s // h
                if 1 <= w <= m and h * va * w * vb <= x:
                    ok = True
                    break
        assert ok, f"claimed area {s} is not a realisable rectangle area"
