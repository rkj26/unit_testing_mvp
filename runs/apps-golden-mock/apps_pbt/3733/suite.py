from collections import Counter

from hypothesis import given, strategies as st, settings

from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str


# ---------------------------------------------------------------------------
# Problem recap (for reference only; NOT re-solved here):
#   Array of n non-negative ints. If K distinct values remain, need
#   k = ceil(log2 K) bits each (k=0 when K==1), total n*k bits, must be <= 8*I.
#   Compression: pick l<=r, clamp values below l to l and above r to r.
#   -> the kept distinct values form a CONTIGUOUS window of the sorted distinct
#      values; window may hold at most 2^kmax distinct values, kmax = floor(8I/n).
#   Answer = minimal number of changed elements.
#
# We NEVER recompute the optimum. We only check sound bounds / certificates /
# metamorphic relations that any correct answer must satisfy.
# ---------------------------------------------------------------------------


def to_stdin(n, I, arr):
    return f"{n} {I}\n" + " ".join(map(str, arr)) + "\n"


def parse_in(s):
    lines = s.split("\n")
    first = lines[0].split()
    n = int(first[0])
    I = int(first[1])
    arr = list(map(int, lines[1].split())) if len(lines) > 1 and lines[1].strip() else []
    return n, I, arr


def parse_out(stdout):
    toks = stdout.split()
    assert len(toks) == 1, f"expected a single integer, got {stdout!r}"
    try:
        return int(toks[0])
    except ValueError:
        raise AssertionError(f"output is not an integer: {stdout!r}")


def compute_params(n, I, arr):
    """Sound quantities derived directly from the input (no optimization)."""
    freqs = sorted(Counter(arr).values(), reverse=True)
    m = len(freqs)                    # number of distinct values
    cmax = freqs[0]                   # largest single frequency (the mode count)
    kmax = (8 * I) // n               # max bits available per element
    if kmax >= 20:                    # 2^20 > 4e5 >= n >= m  -> window covers all
        W = m
    else:
        W = min(m, 1 << kmax)         # max distinct values we may keep
    topW = sum(freqs[:W])             # relaxation: best W freqs (ignores contiguity)
    return m, cmax, W, topW


# ---------------------------------------------------------------------------
# Generators tuned for coverage of the trigger regions.
# ---------------------------------------------------------------------------

def _order(arr, omode):
    if omode == 1:
        return arr[::-1]
    if omode == 2:
        return arr[1::2] + arr[0::2]
    return arr


@st.composite
def gen_case(draw, big=False):
    # --- number of distinct values, biased to power-of-2 boundaries ---
    mmode = draw(st.integers(0, 3))
    if mmode == 0:
        m = 1 << draw(st.integers(0, 4))        # 1,2,4,8,16  (exact log2 boundary)
    elif mmode == 1:
        m = (1 << draw(st.integers(0, 4))) + 1  # 2,3,5,9,17  (needs one extra bit)
    else:
        m = draw(st.integers(1, 20))

    # --- pick the actual distinct values (domain) ---
    dmode = draw(st.integers(0, 3))
    if dmode == 0:                                # small consecutive block
        base = draw(st.integers(0, 5))
        vals = list(range(base, base + m))
    elif dmode == 1:                             # include extreme magnitudes 0 & 1e9
        s = {0}
        if m >= 2:
            s.add(10 ** 9)
        while len(s) < m:
            s.add(draw(st.integers(0, 10 ** 9)))
        vals = sorted(s)
    elif dmode == 2:                            # widely spread
        vals = sorted(draw(st.sets(st.integers(0, 10 ** 9), min_size=m, max_size=m)))
    else:                                       # tight small domain, heavy structure
        vals = sorted(draw(st.sets(st.integers(0, 30), min_size=m, max_size=m)))
    m = len(vals)

    # --- frequencies ---
    fmode = draw(st.integers(0, 3))
    hi = 40 if big else 8
    freqs = [draw(st.integers(1, hi)) for _ in range(m)]
    if fmode == 0:                               # one dominant value
        freqs[draw(st.integers(0, m - 1))] += draw(st.integers(5, 60 if big else 20))
    elif fmode == 1:                             # every value appears exactly once
        freqs = [1] * m

    arr = []
    for v, c in zip(vals, freqs):
        arr.extend([v] * c)
    arr = _order(arr, draw(st.integers(0, 2)))
    n = len(arr)

    # --- choose I, biased to the exact fit / bit-budget thresholds ---
    kfull = 0 if m <= 1 else (m - 1).bit_length()   # ceil(log2 m)
    tmode = draw(st.integers(0, 5))
    if tmode == 0:                               # smallest I giving budget exactly k
        k = draw(st.integers(0, kfull + 1))
        I = max(1, -(-(n * k) // 8))
    elif tmode == 1:                             # just below budget k
        k = draw(st.integers(1, kfull + 2))
        I = max(1, (n * k - 1) // 8)
    elif tmode == 2:
        I = 1                                    # minimum disk
    elif tmode == 3:
        I = 10 ** 8                              # maximum disk (fits)
    elif tmode == 4:
        I = draw(st.integers(1, 10 ** 8))       # uniform
    else:                                        # exactly enough to fit whole array
        I = max(1, -(-(n * kfull) // 8))
    I = max(1, min(I, 10 ** 8))
    return n, I, arr


@st.composite
def case_string(draw):
    n, I, arr = draw(gen_case(big=draw(st.booleans())))
    return to_stdin(n, I, arr)


@st.composite
def scale_case(draw):
    """Small case + a duplication factor for the scaling metamorphic test."""
    m = draw(st.integers(1, 6))
    base = draw(st.integers(0, 5))
    vals = list(range(base, base + m))
    freqs = [draw(st.integers(1, 5)) for _ in range(m)]
    if draw(st.booleans()):
        freqs[draw(st.integers(0, m - 1))] += draw(st.integers(3, 10))
    arr = []
    for v, c in zip(vals, freqs):
        arr.extend([v] * c)
    arr = _order(arr, draw(st.integers(0, 2)))
    n = len(arr)
    kfull = 0 if m <= 1 else (m - 1).bit_length()
    tmode = draw(st.integers(0, 3))
    if tmode == 0:
        I = max(1, -(-(n * draw(st.integers(0, kfull + 1))) // 8))
    elif tmode == 1:
        I = 1
    elif tmode == 2:
        I = max(1, -(-(n * kfull) // 8))
    else:
        I = draw(st.integers(1, 300))
    I = max(1, min(I, 500))
    t = draw(st.integers(2, 12))
    return to_stdin(n, I, arr), t


# Deterministic curated corner cases (always exercised, incl. exact boundaries).
def _build_curated():
    cases = [
        (1, [0]),                               # singleton, min value
        (1, [10 ** 9]),                         # singleton, max value
        (1, [7, 7, 7, 7, 7]),                   # all equal (m=1)
        (1, [0, 1]),                            # m=2
        (1, [0, 1, 2]),                         # m=3, fits (n*2=6<=8)
        (1, [0, 1, 2, 3]),                      # m=4, EXACT fit (n*2=8==8I)
        (1, [0, 1, 2, 3, 4]),                   # m=5, does not fit
        (3, [0, 1, 2, 3, 4, 5, 6, 7]),          # m=8, EXACT fit (n*3=24==8I)
        (2, [0, 1, 2, 3, 4, 5, 6, 7]),          # m=8, does not fit (8I=16)
        (1, [0, 1, 2, 3, 4, 5, 6, 7, 8]),       # m=9 (pow2+1), not fit
        (1, [0, 10 ** 9]),                      # two extremes
        (1, [0, 10 ** 9, 0, 10 ** 9, 500]),     # extremes + midpoint, heavy dup
        (10 ** 8, list(range(10))),             # max I -> fits
        (1, [5, 5, 5, 4, 4, 3]),                # skewed frequencies
    ]
    out = [to_stdin(len(a), I, a) for I, a in cases]
    # large-size / max-magnitude degenerate case
    out.append(to_stdin(40000, 1, [10 ** 9] * 40000))
    return out


CURATED = _build_curated()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@given(st.one_of(st.sampled_from(CURATED), case_string()))
@settings(max_examples=60, deadline=None)
def test_bounds_and_fit(stdin):
    n, I, arr = parse_in(stdin)
    ans = parse_out(run_candidate(stdin))
    m, cmax, W, topW = compute_params(n, I, arr)

    # range / shape
    assert 0 <= ans <= n, f"answer {ans} out of [0,{n}]"

    # UPPER bound certificate: clamp everything to the mode value (K=1, 0 bits,
    # always fits) changes exactly n-cmax elements, so optimum <= n-cmax.
    assert ans <= n - cmax, f"answer {ans} exceeds feasible n-cmax={n - cmax}"

    # LOWER bound certificate: at most W distinct values may survive, so at most
    # the top-W frequencies can be kept (contiguity only makes this harder).
    lb = max(0, n - topW)
    assert ans >= lb, f"answer {ans} below lower bound {lb}"

    # EXACT: whole array already fits (W==m) <=> zero changes.
    if W == m:
        assert ans == 0, f"whole file fits but answer {ans} != 0"


@given(case_string())
@settings(max_examples=40, deadline=None)
def test_monotonic_in_I(stdin):
    # A larger disk can never force MORE changes.
    n, I, arr = parse_in(stdin)
    ans0 = parse_out(run_candidate(stdin))
    I1 = min(10 ** 8, I + 8 * n)                 # add ~one bit of budget
    ans1 = parse_out(run_candidate(to_stdin(n, I1, arr)))
    assert ans1 <= ans0, f"more disk raised changes: I={I}->{ans0}, I={I1}->{ans1}"


@given(case_string())
@settings(max_examples=24, deadline=None)
def test_permutation_invariant(stdin):
    # Answer depends only on the multiset of values, not on element order.
    n, I, arr = parse_in(stdin)
    ans0 = parse_out(run_candidate(stdin))
    ans_rev = parse_out(run_candidate(to_stdin(n, I, arr[::-1])))
    ans_sorted = parse_out(run_candidate(to_stdin(n, I, sorted(arr))))
    assert ans0 == ans_rev == ans_sorted, (
        f"order changed the answer: {ans0} / {ans_rev} / {ans_sorted}"
    )


@given(case_string())
@settings(max_examples=24, deadline=None)
def test_relabel_invariant(stdin):
    # Only sorted order & frequencies matter; any strictly-increasing relabeling
    # of the distinct values (preserving order) leaves the answer unchanged.
    n, I, arr = parse_in(stdin)
    ans0 = parse_out(run_candidate(stdin))

    order = sorted(set(arr))
    m = len(order)

    # (a) compress distinct values to 0..m-1
    small = {v: i for i, v in enumerate(order)}
    arr_small = [small[v] for v in arr]
    ans_small = parse_out(run_candidate(to_stdin(n, I, arr_small)))

    # (b) spread distinct values across the full magnitude range (includes big values)
    step = (10 ** 9) // (m + 1)
    big = {v: i * step for i, v in enumerate(order)}
    arr_big = [big[v] for v in arr]
    ans_big = parse_out(run_candidate(to_stdin(n, I, arr_big)))

    assert ans0 == ans_small == ans_big, (
        f"value magnitudes changed the answer: {ans0} / {ans_small} / {ans_big}"
    )


@given(scale_case())
@settings(max_examples=30, deadline=None)
def test_scale_frequencies(stdin_t):
    # Duplicate every element t times and scale I by t: floor(8I/n) is preserved,
    # every frequency is multiplied by t, so the minimal changes scale by t.
    stdin, t = stdin_t
    n, I, arr = parse_in(stdin)
    if n * t > 4 * 10 ** 5 or I * t > 10 ** 8:
        return
    ans0 = parse_out(run_candidate(stdin))
    arr2 = []
    for v in arr:
        arr2.extend([v] * t)
    ans2 = parse_out(run_candidate(to_stdin(n * t, I * t, arr2)))
    assert ans2 == t * ans0, f"scaling by {t}: {ans0} -> expected {t * ans0}, got {ans2}"