from collections import Counter

from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str


# ----------------------------------------------------------------------------
# Problem 3733: clamp array values into a chosen range [l, r]. If K distinct
# values remain, storage takes n*ceil(log2 K) bits and must be <= 8*I bits.
# Output = minimal number of changed elements.
#
# Key structural facts used ONLY for sound certificate/bound checks (never to
# assert an exact optimum we would have to fully solve):
#   * k_max = floor(8*I / n) is the max bits/value we may spend.
#   * K_max = min(m, 2**k_max) is the max number of distinct values we may keep
#     (m = number of distinct values in the array).
#   * Clamping to [v_i, v_j] (existing distinct values) keeps exactly the
#     distinct values inside that value-window; changed count = elements < v_i
#     plus elements > v_j.  This is always a feasible configuration when the
#     window holds <= K_max distinct values, so its cost is an upper bound on
#     the true optimum.
#   * The optimum only depends on the MULTISET of values (order/labels of
#     values are irrelevant beyond their relative order and frequencies).
# ----------------------------------------------------------------------------


def build_stdin(n, I, arr):
    return "{} {}\n{}\n".format(n, I, " ".join(map(str, arr)))


def parse_stdin(stdin):
    lines = stdin.split("\n")
    n, I = map(int, lines[0].split())
    arr = list(map(int, lines[1].split()))
    return n, I, arr


def parse_out(stdout):
    return int(stdout.strip())


def sorted_freqs(arr):
    c = Counter(arr)
    return [c[v] for v in sorted(c)]  # frequencies ordered by increasing value


def k_and_K(n, I, m):
    kmax = (8 * I) // n
    if kmax >= 20:          # 2**20 > 4*10**5 >= n >= m, so all distinct kept
        Kmax = m
    else:
        Kmax = min(m, 1 << kmax)
    return kmax, Kmax


def feasible_upper_cost(n, I, arr):
    # Cost of a genuinely feasible clamping (best contiguous value-window of
    # size min(K_max, m)).  Since frequencies are non-negative, the widest
    # allowed window is optimal; but even a sub-optimal window would still be a
    # valid upper bound, so this stays sound regardless.
    freqs = sorted_freqs(arr)
    m = len(freqs)
    _, Kmax = k_and_K(n, I, m)
    w = min(Kmax, m)
    if w < 1:
        w = 1
    cur = sum(freqs[:w])
    best = cur
    for i in range(w, m):
        cur += freqs[i] - freqs[i - w]
        if cur > best:
            best = cur
    return n - best


def relax_lower_cost(n, I, arr):
    # Relaxation: drop the contiguity requirement.  The kept elements form a
    # window of <= K_max distinct values, whose total frequency cannot exceed
    # the sum of the K_max largest frequencies.  Hence a sound LOWER bound on
    # the number of changed elements.
    freqs = sorted_freqs(arr)
    m = len(freqs)
    _, Kmax = k_and_K(n, I, m)
    top = sorted(freqs, reverse=True)[:Kmax]
    return n - sum(top)


# --- input strategies -------------------------------------------------------

@st.composite
def make_input(draw):
    n = draw(st.integers(min_value=1, max_value=300))
    vmax = draw(st.sampled_from([0, 1, 3, 7, 15, 100, 10 ** 9]))
    arr = draw(st.lists(st.integers(min_value=0, max_value=vmax),
                        min_size=n, max_size=n))
    # Bias heavily toward tiny budgets (tight/interesting regime) and also
    # sample the full legal range.
    I = draw(st.one_of(st.integers(min_value=1, max_value=4),
                       st.integers(min_value=1, max_value=10 ** 8)))
    return build_stdin(n, I, arr)


@st.composite
def make_input_tight(draw):
    # Force 8*I < n  =>  k_max = 0  =>  only ONE distinct value may be kept.
    I = draw(st.integers(min_value=1, max_value=20))
    n = draw(st.integers(min_value=8 * I + 1, max_value=8 * I + 300))
    vmax = draw(st.sampled_from([1, 3, 7, 15, 100, 10 ** 9]))
    arr = draw(st.lists(st.integers(min_value=0, max_value=vmax),
                        min_size=n, max_size=n))
    return build_stdin(n, I, arr)


@st.composite
def make_input_large(draw):
    # Budget so large that every distinct value fits => answer must be 0.
    n = draw(st.integers(min_value=1, max_value=300))
    vmax = draw(st.sampled_from([0, 1, 3, 7, 15, 100, 10 ** 9]))
    arr = draw(st.lists(st.integers(min_value=0, max_value=vmax),
                        min_size=n, max_size=n))
    I = draw(st.integers(min_value=10 ** 6, max_value=10 ** 8))
    return build_stdin(n, I, arr)


# --- tests ------------------------------------------------------------------

@given(make_input())
@settings(max_examples=50, deadline=None)
def test_format_and_bounds(stdin):
    n, I, arr = parse_stdin(stdin)
    c = parse_out(run_candidate(stdin))
    # Format / range: a count of changed elements is in [0, n].
    assert 0 <= c <= n, (c, n)
    # Sound upper bound: cost of an explicitly feasible clamping.
    assert c <= feasible_upper_cost(n, I, arr), (c, "> feasible upper")
    # Sound lower bound: contiguity-free relaxation.
    assert c >= relax_lower_cost(n, I, arr), (c, "< relaxed lower")


@given(make_input())
@settings(max_examples=50, deadline=None)
def test_permutation_invariant(stdin):
    n, I, arr = parse_stdin(stdin)
    base = parse_out(run_candidate(stdin))
    # The answer depends only on the multiset of values, not their order.
    other = parse_out(run_candidate(build_stdin(n, I, sorted(arr))))
    assert base == other, (base, other)


@given(make_input())
@settings(max_examples=50, deadline=None)
def test_monotone_and_reflection_invariant(stdin):
    n, I, arr = parse_stdin(stdin)
    base = parse_out(run_candidate(stdin))
    # Order-preserving relabel of distinct values (compress to ranks): keeps
    # distinctness, order and all frequencies => same answer.
    rank = {v: i for i, v in enumerate(sorted(set(arr)))}
    remapped = [rank[v] for v in arr]
    out_r = parse_out(run_candidate(build_stdin(n, I, remapped)))
    assert out_r == base, (base, out_r)
    # Reflection of the value axis (v -> vmax - v) reverses value order but the
    # low/high clamping problem is symmetric => same answer. Stays in range.
    vmax = max(arr)
    reflected = [vmax - v for v in arr]
    out_ref = parse_out(run_candidate(build_stdin(n, I, reflected)))
    assert out_ref == base, (base, out_ref)


@given(make_input_large())
@settings(max_examples=50, deadline=None)
def test_large_budget_zero(stdin):
    # Enough disk to keep every distinct value untouched => zero changes.
    c = parse_out(run_candidate(stdin))
    assert c == 0, c


@given(make_input_tight())
@settings(max_examples=50, deadline=None)
def test_tight_budget_exact(stdin):
    # 8*I < n forces k_max = 0, so only a single distinct value survives.
    # The optimum is then exactly n minus the largest frequency.
    n, I, arr = parse_stdin(stdin)
    c = parse_out(run_candidate(stdin))
    maxfreq = max(Counter(arr).values())
    assert c == n - maxfreq, (c, n - maxfreq)
