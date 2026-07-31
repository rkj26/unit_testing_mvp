from hypothesis import given, strategies as st, settings
from harness import run_candidate

# Problem: K sides, N indistinguishable dice.  For i = 2..2K output (mod p) the
# number of size-N multisets over {1..K} such that no two (distinct) dice sum to i.
# Output: 2K-1 integers, t-th is answer for i = t+1.

MOD = 998244353

# ---- modular binomials (factorials up to N+K <= 4000) -----------------------
_LIM = 4100
_fact = [1] * (_LIM + 1)
for _i in range(1, _LIM + 1):
    _fact[_i] = _fact[_i - 1] * _i % MOD
_inv = [1] * (_LIM + 1)
_inv[_LIM] = pow(_fact[_LIM], MOD - 2, MOD)
for _i in range(_LIM, 0, -1):
    _inv[_i - 1] = _inv[_i] * _i % MOD


def _binom(n, r):
    if r < 0 or n < 0 or r > n:
        return 0
    return _fact[n] * _inv[r] % MOD * _inv[n - r] % MOD


# number of size-m multisets over `d` distinct values = C(m + d - 1, d - 1)
def _multiset(d, m):
    return _binom(m + d - 1, d - 1)


def _check_all(stdin):
    parts = stdin.split()
    K = int(parts[0])
    N = int(parts[1])
    out = run_candidate(stdin)
    toks = out.split()

    # ---- SHAPE: exactly 2K-1 integers ----
    assert len(toks) == 2 * K - 1, \
        f"K={K} N={N}: expected {2 * K - 1} integers, got {len(toks)}"

    # ---- RANGE: each is an integer in [0, MOD) ----
    vals = []
    for t in toks:
        try:
            v = int(t)
        except ValueError:
            raise AssertionError(f"K={K} N={N}: non-integer output token {t!r}")
        assert 0 <= v < MOD, f"K={K} N={N}: value {v} out of [0,{MOD})"
        vals.append(v)

    # ---- SYMMETRY / METAMORPHIC: relabel v -> K+1-v is a bijection on multisets
    # that maps "avoid sum i" to "avoid sum 2K+2-i", so answer(i)=answer(2K+2-i);
    # over i=2..2K this makes the whole output list a palindrome. ----
    assert vals == vals[::-1], f"K={K} N={N}: output must be palindromic"

    # ---- CERTIFICATE for i=2 (first entry): the only pair summing to 2 is (1,1),
    # so the constraint is simply "at most one die shows value 1".
    #   count[1]=0 : size-N multiset over the K-1 values {2..K}
    #   count[1]=1 : size-(N-1) multiset over the K-1 values {2..K}
    exp2 = (_multiset(K - 1, N) + _multiset(K - 1, N - 1)) % MOD
    assert vals[0] == exp2, f"K={K} N={N}: i=2 got {vals[0]} expected {exp2}"

    # ---- CERTIFICATE for i=3 (second entry, exists iff K>=2): pairs summing to 3
    # are just {1,2}; constraint is "not both value 1 and value 2 present".
    # inclusion-exclusion:  (no 1) + (no 2) - (no 1 and no 2)
    if K >= 2:
        no1 = _multiset(K - 1, N)                # values {2..K}
        no2 = _multiset(K - 1, N)                # values {1,3..K}
        none12 = _multiset(K - 2, N)             # values {3..K}
        exp3 = (no1 + no2 - none12) % MOD
        assert vals[1] == exp3, f"K={K} N={N}: i=3 got {vals[1]} expected {exp3}"


# --- broad small/medium region, biased to tiny values & structural edges -----
@st.composite
def _gen_small(draw):
    K = draw(st.one_of(st.integers(min_value=1, max_value=40),
                       st.sampled_from([1, 2, 3, 4, 5, 8, 20, 40])))
    N = draw(st.one_of(st.integers(min_value=2, max_value=80),
                       st.sampled_from([2, 3, 4, 5, 80])))
    return f"{K} {N}\n"


@given(_gen_small())
@settings(max_examples=40, deadline=None)
def test_small(stdin):
    _check_all(stdin)


# --- mid range up to K=500, full N range including the N max -----------------
@st.composite
def _gen_mid(draw):
    K = draw(st.one_of(st.integers(min_value=1, max_value=500),
                       st.sampled_from([1, 2, 3, 300, 500])))
    N = draw(st.one_of(st.integers(min_value=2, max_value=2000),
                       st.sampled_from([2, 3, 1000, 1999, 2000])))
    return f"{K} {N}\n"


@given(_gen_mid())
@settings(max_examples=16, deadline=None)
def test_mid(stdin):
    _check_all(stdin)


# --- extreme corners: min/max K, min/max N, and combinations -----------------
_CORNERS = ["1 2", "1 3", "1 2000", "2 2", "2 3", "2 2000",
            "2000 2", "2000 2000", "1999 2000", "1000 1000"]


@st.composite
def _gen_corner(draw):
    return draw(st.sampled_from(_CORNERS)) + "\n"


@given(_gen_corner())
@settings(max_examples=10, deadline=None)
def test_corners(stdin):
    _check_all(stdin)


# --- deterministic sweep over the small bounded box (K=1..6, N=2..8) ---------
_SWEEP = [f"{k} {n}" for k in range(1, 7) for n in range(2, 9)]


@st.composite
def _gen_sweep(draw):
    return draw(st.sampled_from(_SWEEP)) + "\n"


@given(_gen_sweep())
@settings(max_examples=55, deadline=None)
def test_sweep(stdin):
    _check_all(stdin)
