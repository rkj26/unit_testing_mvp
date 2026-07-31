from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

MOD = 10 ** 9 + 7


def steps_to_one(x):
    # Minimum ops to reduce x to 1, where one op maps x -> popcount(x). The op is
    # deterministic, so this count is the unique/minimal number of operations.
    c = 0
    while x != 1:
        x = bin(x).count("1")
        c += 1
    return c


def _stdin(n, k):
    # n in binary without leading zeros (bin(n)[2:] has none for n>=1), then k.
    return bin(n)[2:] + "\n" + str(k) + "\n"


def _parse(stdin):
    toks = stdin.split()
    return int(toks[0], 2), int(toks[1])


@st.composite
def _gen_n(draw, max_bits=1000):
    # Weighted toward small/moderate n (keeps per-call cost low) while still hitting
    # large / structural edge cases hard. Always returns 1 <= n < 2^max_bits.
    r = draw(st.integers(min_value=0, max_value=9))
    if r <= 3:                                   # small
        return draw(st.integers(min_value=1, max_value=5000))
    elif r <= 6:                                 # moderate
        b = draw(st.integers(min_value=1, max_value=min(128, max_bits)))
        return draw(st.integers(min_value=1, max_value=(1 << b) - 1))
    elif r <= 7:                                 # structural edges
        cands = [1, 2, 3, 6, 7, 127, (1 << 63) - 1]
        if max_bits >= 127:
            cands.append((1 << 127) - 1)
        if max_bits >= 1000:
            cands += [1 << 999, (1 << 1000) - 1, (1 << 1000) - 2]
        cands = [c for c in cands if c < (1 << max_bits)]
        return draw(st.sampled_from(cands))
    else:                                        # large random up to the cap
        b = draw(st.integers(min_value=1, max_value=max_bits))
        return draw(st.integers(min_value=1, max_value=(1 << b) - 1))


@st.composite
def make_input_k0(draw):
    return _stdin(draw(_gen_n()), 0)


@given(make_input_k0())
@settings(max_examples=50, deadline=None)
def test_k_zero(stdin):
    # Only x == 1 has f(x) == 0, and 1 <= n always, so the count is exactly 1.
    v = int(run_candidate(stdin).strip())
    assert v == 1, "k=0 must yield exactly 1 (only the number 1), got %d" % v


@st.composite
def make_input_k1(draw):
    return _stdin(draw(_gen_n()), 1)


@given(make_input_k1())
@settings(max_examples=50, deadline=None)
def test_k_one(stdin):
    # f(x) == 1 iff x is a power of two > 1 (popcount 1; x=1 has f=0). Powers of two in
    # [2, n] are 2^1 .. 2^(L-1) with L = bit_length(n), so the count is exactly L - 1.
    n, _ = _parse(stdin)
    v = int(run_candidate(stdin).strip())
    expected = n.bit_length() - 1
    assert v == expected, "k=1 must equal bit_length(n)-1 = %d, got %d" % (expected, v)


@st.composite
def make_input_klarge(draw):
    n = draw(_gen_n())
    k = draw(st.integers(min_value=6, max_value=1000))
    return _stdin(n, k)


@given(make_input_klarge())
@settings(max_examples=50, deadline=None)
def test_k_large_is_zero(stdin):
    # For any x < 2^1000, popcount(x) <= 1000 and max f over 1..1000 is 4, so f(x) <= 5.
    # No number is special for k >= 6: the answer must be exactly 0.
    n, k = _parse(stdin)
    v = int(run_candidate(stdin).strip())
    assert v == 0, "k=%d (>=6) unreachable for n<2^1000, answer must be 0, got %d" % (k, v)


@st.composite
def make_input_small(draw):
    n = draw(st.integers(min_value=1, max_value=2000))
    k = draw(st.integers(min_value=0, max_value=7))
    return _stdin(n, k)


@given(make_input_small())
@settings(max_examples=50, deadline=None)
def test_bruteforce_small(stdin):
    # For small n the exact count is < MOD, so the output must equal the count computed
    # straight from the definition. Strongest possible check on the small-input regime.
    n, k = _parse(stdin)
    v = int(run_candidate(stdin).strip())
    expected = sum(1 for x in range(1, n + 1) if steps_to_one(x) == k)
    assert v == expected, "count for n=%d k=%d must be %d, got %d" % (n, k, expected, v)


@st.composite
def make_input_increment(draw):
    # n capped so that n+1 is still a valid input (< 2^1000).
    n = draw(_gen_n(max_bits=300))
    m = n + 1
    fm = steps_to_one(m)
    c = draw(st.integers(min_value=0, max_value=2))
    if c == 0:
        k = fm                                   # forces the "count grows by 1" branch
    elif c == 1:
        k = draw(st.integers(min_value=0, max_value=7))
    else:
        k = draw(st.integers(min_value=0, max_value=1000))
    return _stdin(n, k)


@given(make_input_increment())
@settings(max_examples=50, deadline=None)
def test_increment_metamorphic(stdin):
    # Metamorphic: [1, n+1] differs from [1, n] only by the number n+1. So for a fixed k,
    # count(n+1) - count(n) equals 1 if f(n+1) == k else 0 (in exact integers, hence mod).
    n, k = _parse(stdin)
    m = n + 1
    v_n = int(run_candidate(stdin).strip())
    v_m = int(run_candidate(_stdin(m, k)).strip())
    assert 0 <= v_n < MOD, "output %d out of range" % v_n
    assert 0 <= v_m < MOD, "output %d out of range" % v_m
    delta = 1 if steps_to_one(m) == k else 0
    assert (v_m - v_n) % MOD == delta, \
        "count(n+1)-count(n) must be %d for k=%d, got %d" % (delta, k, (v_m - v_n) % MOD)
