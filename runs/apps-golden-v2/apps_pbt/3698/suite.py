from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

MOD = 10 ** 9 + 7

# ---------------------------------------------------------------------------
# Trusted oracle helpers (literal definition of the problem, NOT an efficient
# solver). Used only as a ground truth for small n and to derive certificates.
# ---------------------------------------------------------------------------

def f_steps(x):
    """Minimum operations to reduce x to 1 (f(1)=0)."""
    c = 0
    while x != 1:
        x = bin(x).count("1")
        c += 1
    return c


def brute_count(n, k):
    """Exact number of x in [1, n] with f_steps(x) == k."""
    return sum(1 for x in range(1, n + 1) if f_steps(x) == k)


def parse(stdin):
    lines = stdin.split("\n")
    return lines[0], int(lines[1])


def get_ans(stdin):
    return int(run_candidate(stdin).strip())


# ---------------------------------------------------------------------------
# Input generators. Bias hard toward structural / threshold / extreme regions.
# ---------------------------------------------------------------------------

@st.composite
def small_binary(draw):
    """Small n (<= 2^14) so brute force is feasible; structural bias."""
    L = draw(st.integers(min_value=1, max_value=14))
    if L == 1:
        return "1"
    kind = draw(st.sampled_from(
        ["random", "random", "ones", "power2", "power2_minus_one", "half"]))
    if kind == "ones":
        return "1" * L                      # 2^L - 1 (all bits set)
    if kind == "power2":
        return "1" + "0" * (L - 1)          # exact power of two
    if kind == "power2_minus_one":
        return "1" * (L - 1) + "0"          # 2^L - 2
    if kind == "half":
        return "1" + "0" * (L - 2) + "1"    # 2^(L-1)+1
    bits = draw(st.lists(st.integers(0, 1), min_size=L - 1, max_size=L - 1))
    return "1" + "".join(str(b) for b in bits)


@st.composite
def big_binary(draw):
    """n across the whole range incl. up to 1000 bits; structural bias."""
    L = draw(st.sampled_from(
        [1, 2, 3, 4, 5, 8, 16, 30, 31, 32, 33, 64, 100, 256, 500, 999, 1000]))
    if L == 1:
        return "1"
    kind = draw(st.sampled_from(
        ["random", "random", "ones", "power2", "power2_minus_one"]))
    if kind == "ones":
        return "1" * L
    if kind == "power2":
        return "1" + "0" * (L - 1)
    if kind == "power2_minus_one":
        return "1" * (L - 1) + "0"
    bits = draw(st.lists(st.integers(0, 1), min_size=L - 1, max_size=L - 1))
    return "1" + "".join(str(b) for b in bits)


@st.composite
def small_case(draw):
    s = draw(small_binary())
    k = draw(st.integers(min_value=0, max_value=8))   # covers 0..5 real + beyond
    return s + "\n" + str(k) + "\n"


@st.composite
def cert_case(draw):
    s = draw(big_binary())
    # k values with a KNOWN closed-form answer (k=0, k=1, or beyond max f=5)
    k = draw(st.sampled_from([0, 0, 1, 1, 6, 7, 8, 10, 100, 500, 999, 1000]))
    return s + "\n" + str(k) + "\n"


@st.composite
def generic_case(draw):
    s = draw(big_binary())
    k = draw(st.integers(min_value=0, max_value=1000))
    return s + "\n" + str(k) + "\n"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@given(small_case())
@settings(max_examples=20, deadline=None)
def test_matches_bruteforce(stdin):
    """For small n the exact count is computable from the definition."""
    s, k = parse(stdin)
    n = int(s, 2)
    ans = get_ans(stdin)
    assert 0 <= ans < MOD, ans
    assert ans == brute_count(n, k) % MOD, (s, k, ans)


@given(st.integers(min_value=0, max_value=0))
@settings(max_examples=1, deadline=None)
def test_tiny_exhaustive(dummy):
    """Deterministic sweep of every small n against the exact oracle, so a
    magic-value guard keyed to a specific tiny input cannot slip through."""
    for n in range(1, 12):
        s = bin(n)[2:]
        for k in range(0, 6):
            ans = get_ans(f"{s}\n{k}\n")
            assert ans == brute_count(n, k) % MOD, (n, k, ans)


@given(cert_case())
@settings(max_examples=22, deadline=None)
def test_closed_form_certificates(stdin):
    """Closed-form answers provable without solving the counting problem:
      k == 0            -> exactly 1 (only x=1 has f=0)
      k == 1            -> L-1 (powers of two 2^1..2^(L-1) in [1,n])
      k >= 6            -> 0 (max possible f over x < 2^1000 is 5)
    """
    s, k = parse(stdin)
    ans = get_ans(stdin)
    assert 0 <= ans < MOD, ans
    if k == 0:
        assert ans == 1, (s, k, ans)
    elif k == 1:
        assert ans == len(s) - 1, (s, k, ans)
    elif k >= 6:
        assert ans == 0, (s, k, ans)


@given(big_binary())
@settings(max_examples=3, deadline=None)
def test_sum_over_k(s):
    """Every x in [1,n] has f(x) in {0,...,5}, so the counts partition [1,n]:
       sum_{k=0}^{6} answer(n,k) == n  (mod p).   (k=6 term is 0, kept as buffer)
    """
    total = 0
    for k in range(0, 7):
        total = (total + get_ans(s + "\n" + str(k) + "\n")) % MOD
    assert total == int(s, 2) % MOD, (s, total)


@given(generic_case())
@settings(max_examples=12, deadline=None)
def test_format_and_range(stdin):
    """Output is a single non-negative integer strictly below the modulus."""
    ans = get_ans(stdin)
    assert 0 <= ans < MOD, ans
