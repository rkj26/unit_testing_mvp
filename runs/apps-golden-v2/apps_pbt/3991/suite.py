import re
from hypothesis import given, example, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

MOD = 10**9 + 7
HI = 10**9  # max coordinate value


def build_stdin(coords):
    """Assemble a valid STDIN string: n on line 1, coords on line 2."""
    return f"{len(coords)}\n{' '.join(str(c) for c in coords)}\n"


def parse_answer(stdout):
    """A correct output is exactly one non-negative integer in [0, MOD)."""
    s = stdout.strip()
    assert s != "", f"empty output: {stdout!r}"
    parts = s.split()
    assert len(parts) == 1, f"expected a single integer, got {stdout!r}"
    assert re.fullmatch(r"\d+", parts[0]), f"not a non-negative integer: {stdout!r}"
    v = int(parts[0])
    assert 0 <= v < MOD, f"answer {v} outside canonical residue range [0,{MOD})"
    return v


def brute(coords):
    """Ground-truth from the DEFINITION: sum over all non-empty subsets of
    (max - min), taken mod MOD. Only used for tiny n (<=10)."""
    n = len(coords)
    total = 0
    for mask in range(1, 1 << n):
        mn = None
        mx = None
        for i in range(n):
            if mask & (1 << i):
                c = coords[i]
                if mn is None or c < mn:
                    mn = c
                if mx is None or c > mx:
                    mx = c
        total += mx - mn
    return total % MOD


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
@st.composite
def gen_general(draw):
    """Small/medium valid inputs; distinct coords across the full range."""
    n = draw(st.integers(min_value=1, max_value=2000))
    if n <= 300:
        coords = draw(st.lists(st.integers(1, HI), min_size=n, max_size=n, unique=True))
    else:
        max_step = (HI - 1) // (n - 1)
        step = draw(st.integers(1, max_step))
        base = draw(st.integers(1, HI - (n - 1) * step))
        coords = [base + i * step for i in range(n)]
        if draw(st.booleans()):
            coords = coords[::-1]
    return build_stdin(coords)


@st.composite
def gen_large(draw):
    """Extreme sizes up to the stated maximum n = 3*10^5 (threshold)."""
    n = draw(st.sampled_from([50000, 100000, 200000, 300000]))
    max_step = (HI - 1) // (n - 1)
    step = draw(st.integers(1, max_step))
    base = draw(st.integers(1, HI - (n - 1) * step))
    coords = [base + i * step for i in range(n)]
    if draw(st.booleans()):
        coords = coords[::-1]
    return build_stdin(coords)


@st.composite
def gen_tiny(draw):
    """Tiny n so brute force by the definition is feasible. Mixes tight
    clustering (small domain -> adjacency / minimal gaps) with the full
    extreme range."""
    n = draw(st.integers(min_value=1, max_value=10))
    domain = draw(st.sampled_from([30, 1000, HI]))
    hi = max(domain, n)
    coords = draw(st.lists(st.integers(1, hi), min_size=n, max_size=n, unique=True))
    return build_stdin(coords)


@st.composite
def gen_invariance(draw):
    """Return (orig_stdin, transformed_stdin) where the transform preserves
    the true answer: permutation, translation, reflection, or a combination.
    Coords live in [1, 4e8] so every transform stays valid."""
    n = draw(st.integers(min_value=1, max_value=250))
    coords = draw(st.lists(st.integers(1, 4 * 10**8), min_size=n, max_size=n, unique=True))
    kind = draw(st.sampled_from(["perm", "trans", "reflect", "trans_perm"]))
    tc = list(coords)
    if kind in ("trans", "trans_perm"):
        shift = draw(st.integers(0, HI - max(coords)))
        tc = [c + shift for c in tc]
    if kind == "reflect":
        C = max(coords) + 1  # reflected values land in [1, max], stay distinct
        tc = [C - c for c in coords]
    if kind in ("perm", "trans_perm"):
        tc = list(draw(st.permutations(tc)))
    return build_stdin(coords), build_stdin(tc)


@st.composite
def gen_scale(draw):
    """Return (orig_stdin, scaled_stdin, k). Scaling every coord by k scales
    every pairwise distance by k, so the true answer scales by k exactly."""
    n = draw(st.integers(min_value=1, max_value=250))
    k = draw(st.integers(min_value=2, max_value=1000))
    U = HI // k
    coords = draw(st.lists(st.integers(1, U), min_size=n, max_size=n, unique=True))
    scaled = [c * k for c in coords]
    return build_stdin(coords), build_stdin(scaled), k


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@given(gen_general())
@example(build_stdin([1]))                       # n = 1 -> answer must be 0
@example(build_stdin([1, HI]))                   # extremes together
@example(build_stdin([1, 2]))                    # minimal gap
@example(build_stdin([1, HI, 500000000]))        # extremes + middle
@example(build_stdin(list(range(1, 51))))        # consecutive block
@settings(max_examples=50, deadline=None)
def test_format_and_bounds(stdin):
    v = parse_answer(run_candidate(stdin))
    # Certificate: a single computer has only the singleton subset, F = 0.
    n = int(stdin.split("\n", 1)[0])
    if n == 1:
        assert v == 0, f"n=1 must yield 0, got {v}"


@given(gen_large())
@settings(max_examples=6, deadline=None)
def test_large_valid(stdin):
    # Only shape/range invariants at extreme sizes (threshold n = 3*10^5).
    parse_answer(run_candidate(stdin))


@given(gen_tiny())
@example(build_stdin([1]))
@example(build_stdin([1, HI]))
@example(build_stdin([5, 6, 7]))
@example(build_stdin([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]))
@example(build_stdin([10, 9, 8, 7, 6, 5, 4, 3, 2, 1]))
@example(build_stdin([1, 2, HI]))
@example(build_stdin([HI, 1, 500000000]))
@settings(max_examples=50, deadline=None)
def test_bruteforce_small(stdin):
    coords = [int(t) for t in stdin.split("\n")[1].split()]
    got = parse_answer(run_candidate(stdin))
    assert got == brute(coords), (
        f"answer {got} != definition {brute(coords)} for coords={coords}"
    )


@given(gen_invariance())
@settings(max_examples=25, deadline=None)
def test_invariance(pair):
    orig, transformed = pair
    a = parse_answer(run_candidate(orig))
    b = parse_answer(run_candidate(transformed))
    assert a == b, (
        f"answer changed under distance-preserving transform: {a} vs {b}\n"
        f"orig={orig!r}\ntransformed={transformed!r}"
    )


@given(gen_scale())
@settings(max_examples=25, deadline=None)
def test_scaling(triple):
    orig, scaled, k = triple
    a = parse_answer(run_candidate(orig))
    b = parse_answer(run_candidate(scaled))
    assert b == (k * a) % MOD, (
        f"scaling by {k} should multiply answer: got {b}, expected {(k * a) % MOD} "
        f"(base answer {a})"
    )
