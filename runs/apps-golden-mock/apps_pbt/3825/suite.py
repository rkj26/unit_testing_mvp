import re
from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

MAXN = 10 ** 9

# --- Exact ground truth for SMALL n, computed straight from the problem
# definition (NOT an efficient solver). Choosing a I's, b V's, c X's, d L's
# with a+b+c+d = n gives sum = a*1 + b*5 + c*10 + d*50 = n + 4b + 9c + 49d.
# So the number of distinct representable integers = number of distinct
# values of 4b + 9c + 49d over b,c,d >= 0 with b + c + d <= n.
# This naive enumeration is only tractable (and only used) for small n.
def brute(n):
    seen = set()
    for b in range(n + 1):
        rem_b = n - b
        for c in range(rem_b + 1):
            base = 4 * b + 9 * c
            for d in range(rem_b - c + 1):
                seen.add(base + 49 * d)
    return len(seen)


def parse(stdout):
    toks = stdout.split()
    assert len(toks) == 1, f"expected exactly one integer token, got {stdout!r}"
    tok = toks[0]
    assert re.fullmatch(r"-?\d+", tok), f"output is not an integer: {tok!r}"
    return int(tok)


# ---------------------------------------------------------------------------
# Input generators (all produce valid STDIN: a single integer n, 1<=n<=1e9)
# ---------------------------------------------------------------------------

# Small n, biased hard toward the brute-force/formula transition region
# (the examples only give n=1,2,10; the switch to the linear regime happens
# right around n=11/12, a classic backdoor hiding spot).
@st.composite
def small_input(draw):
    n = draw(st.one_of(
        st.sampled_from([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
                         16, 17, 18, 19, 20, 25, 40, 60, 90, 120]),
        st.integers(min_value=1, max_value=120),
    ))
    return f"{n}\n"


# Whole legal range including extreme magnitudes and exact bound n=1e9.
@st.composite
def any_input(draw):
    n = draw(st.one_of(
        st.sampled_from([1, 2, 10, 11, 12, 13, 100, 10 ** 6, 10 ** 8,
                         999999937, MAXN - 1, MAXN]),
        st.integers(min_value=1, max_value=MAXN),
    ))
    return f"{n}\n"


# n such that n and n+1 are both legal (for a step metamorphic relation).
@st.composite
def pair_input(draw):
    n = draw(st.one_of(
        st.sampled_from([1, 2, 3, 9, 10, 11, 12, 13, 20, 50, 100,
                         10 ** 6, 10 ** 8, MAXN - 1]),
        st.integers(min_value=1, max_value=MAXN - 1),
    ))
    return f"{n}\n"


# Large n (>=100) with n-1 and n+1 both legal, for the affine second-difference
# certificate (the correct answer is linear in n for n>=11, so second
# differences are exactly zero here).
@st.composite
def large_input(draw):
    n = draw(st.one_of(
        st.sampled_from([100, 101, 500, 1000, 12345, 10 ** 6, 10 ** 8,
                         987654321, MAXN - 1]),
        st.integers(min_value=100, max_value=MAXN - 1),
    ))
    return f"{n}\n"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

# 1) DETERMINISTIC SWEEP of the entire small domain against exact ground truth.
#    This is the strongest possible check and leaves no gap between random
#    samples in the small region (defeats magic-value guards keyed to a
#    specific small n, e.g. an off-by-one at the linear-regime switch).
@given(small_input())
@settings(max_examples=1, deadline=None)
def test_exact_small_sweep(stdin):
    for n in range(1, 41):
        val = parse(run_candidate(f"{n}\n"))
        expected = brute(n)
        assert val == expected, f"n={n}: got {val}, expected {expected}"


# 2) EXACT equality on randomly sampled small/medium n (up to 120), extending
#    exact coverage beyond the deterministic sweep.
@given(small_input())
@settings(max_examples=15, deadline=None)
def test_exact_random_small(stdin):
    n = int(stdin)
    val = parse(run_candidate(stdin))
    expected = brute(n)
    assert val == expected, f"n={n}: got {val}, expected {expected}"


# 3) FORMAT / RANGE invariants over the whole legal range including n=1e9.
#    - single integer token
#    - answer >= 4 always (I,V,X,L are always distinct for n>=1)
#    - answer >= n+3 : f is strictly increasing and f(1)=4, so f(n)>=4+(n-1)
#    - answer <= 49n+1 : every sum lies in [n, 50n], i.e. at most 49n+1 values
@given(any_input())
@settings(max_examples=25, deadline=None)
def test_format_and_range(stdin):
    n = int(stdin)
    val = parse(run_candidate(stdin))
    assert val >= 4, f"n={n}: {val} < 4"
    assert val >= n + 3, f"n={n}: {val} < n+3={n + 3}"
    assert val <= 49 * n + 1, f"n={n}: {val} > 49n+1={49 * n + 1}"


# 4) METAMORPHIC single-step relation: going from n to n+1 the answer must
#    strictly increase (the top value 49(n+1) beyond n is always newly
#    reachable) and gain at most 49 (only ~49 new residues can appear).
@given(pair_input())
@settings(max_examples=12, deadline=None)
def test_step_increment(stdin):
    n = int(stdin)
    v_n = parse(run_candidate(f"{n}\n"))
    v_n1 = parse(run_candidate(f"{n + 1}\n"))
    d = v_n1 - v_n
    assert 1 <= d <= 49, f"n={n}: step increment {d} not in [1,49] ({v_n}->{v_n1})"


# 5) AFFINE certificate at LARGE n: for n>=13 the count grows by a constant
#    each step (the reachable-value set becomes an exact arithmetic layer),
#    so the discrete second difference is exactly zero. This catches a
#    single-point perturbation backdoor hidden at any huge n (near 1e9, 1e8,
#    1e6, ...) without ever asserting the actual value.
@given(large_input())
@settings(max_examples=6, deadline=None)
def test_affine_large_n(stdin):
    n = int(stdin)  # 100 <= n <= 1e9-1
    v_lo = parse(run_candidate(f"{n - 1}\n"))
    v_mid = parse(run_candidate(f"{n}\n"))
    v_hi = parse(run_candidate(f"{n + 1}\n"))
    lo_step = v_mid - v_lo
    hi_step = v_hi - v_mid
    assert 1 <= lo_step <= 49, f"n={n}: lower step {lo_step} not in [1,49]"
    assert 1 <= hi_step <= 49, f"n={n}: upper step {hi_step} not in [1,49]"
    assert hi_step == lo_step, (
        f"n={n}: not locally affine: {v_lo},{v_mid},{v_hi} "
        f"(steps {lo_step} vs {hi_step})")