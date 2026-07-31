from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

# ---------------------------------------------------------------------------
# Fixed data from the SPEC (given verbatim in the problem statement).
#   f_0                                = F0
#   f_i (i>=1) = A + f_{i-1} + B + f_{i-1} + C
# These are the ONLY literal strings the problem gives us; every character of
# every f_n is, by induction, one of the characters appearing in them.
# ---------------------------------------------------------------------------
F0 = 'What are you doing at the end of the world? Are you busy? Will you save us?'
A  = 'What are you doing while sending "'          # len 34
B  = '"? Are you busy? Will you send "'            # len 32
C  = '"?'                                          # len 2

# Characters that can legitimately appear as an in-range answer (never '.').
ALLOWED = set(F0) | set(A) | set(B) | set(C)

KMAX = 10 ** 18
NMAX = 10 ** 5


def flen(n):
    """Exact len(f_n) when it is <= 1e18, else a value that is > 1e18.

    Since every query k satisfies 1 <= k <= 1e18, this is enough to decide
    'k > len(f_n)' exactly and to locate the top-level template regions.
    """
    L = 75
    i = 0
    while i < n and L <= KMAX:
        L = 68 + 2 * L
        i += 1
    return L


def _parse(stdin):
    toks = stdin.split()
    q = int(toks[0])
    pairs = [(int(toks[1 + 2 * i]), int(toks[2 + 2 * i])) for i in range(q)]
    return q, pairs


def _stdin(pairs):
    return "{}\n".format(len(pairs)) + "\n".join("{} {}".format(n, k) for n, k in pairs) + "\n"


def _verify(stdin):
    """Run candidate and assert every SOUND property of the output."""
    q, pairs = _parse(stdin)
    out = run_candidate(stdin)
    # Answer chars are only letters/'?'/'"'/space/'.', never CR/LF, so it is
    # safe to strip trailing line terminators without eating a real answer.
    res = out.rstrip('\r\n')

    # FORMAT / SHAPE: exactly q answer characters.
    assert len(res) == q, ("wrong length", q, repr(out))

    for i, (n, k) in enumerate(pairs):
        ch = res[i]
        L = flen(n)

        # CERTIFICATE: out-of-range iff '.'  (uses only length arithmetic).
        if k > L:
            assert ch == '.', ("expected '.' out of range", n, k, L, ch)
            continue
        assert ch != '.', ("unexpected '.' in range", n, k, L, ch)

        # RANGE: an in-range answer is a real character of some f_n.
        assert ch in ALLOWED, ("char outside legal alphabet", n, k, ch)

        # CERTIFICATE: exact known characters forced directly by the spec.
        if n == 0:
            # f_0 is given verbatim.
            assert ch == F0[k - 1], ("f0 mismatch", k, ch, F0[k - 1])
        else:
            # f_n = A + f_{n-1} + B + f_{n-1} + C  (n >= 1).
            if k <= 34:
                # Top-level prefix is always A.
                assert ch == A[k - 1], ("prefix A mismatch", n, k, ch, A[k - 1])
            else:
                Lprev = flen(n - 1)
                # Middle separator B occupies (34+Lprev+1 .. 34+Lprev+32).
                bstart = 34 + Lprev + 1
                if bstart <= k <= bstart + 31:
                    assert ch == B[k - bstart], ("B mismatch", n, k, ch, B[k - bstart])
                # Trailing C = '"?' occupies the final two positions.
                if k == L:
                    assert ch == '?', ("suffix C[1] mismatch", n, k, ch)
                elif k == L - 1:
                    assert ch == '"', ("suffix C[0] mismatch", n, k, ch)
    return res


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

@st.composite
def gen_mixed(draw):
    """Broad coverage: uniform draws mixed with extreme magnitudes."""
    q = draw(st.integers(1, 10))
    pairs = []
    for _ in range(q):
        mode = draw(st.integers(0, 3))
        if mode == 0:                                  # fully uniform
            n = draw(st.integers(0, NMAX))
            k = draw(st.integers(1, KMAX))
        elif mode == 1:                                # small n, small k
            n = draw(st.integers(0, 6))
            k = draw(st.integers(1, 6000))
        elif mode == 2:                                # extreme k (max region)
            n = draw(st.integers(0, NMAX))
            k = draw(st.sampled_from([1, 2, KMAX, KMAX - 1, 10 ** 17, 5 * 10 ** 17]))
        else:                                          # n around length blow-up
            n = draw(st.integers(40, 60))
            k = draw(st.integers(1, KMAX))
        pairs.append((n, k))
    return _stdin(pairs)


@st.composite
def gen_boundary(draw):
    """Hit exact thresholds: the '.' boundary at len(f_n) and the internal
    recursion boundaries (prefix/inner/B/C splits)."""
    q = draw(st.integers(1, 10))
    pairs = []
    for _ in range(q):
        n = draw(st.integers(0, 52))     # <= 52 keeps len(f_n) below 1e18
        L = flen(n)
        cands = {1, 2, L, L - 1}
        if L + 1 <= KMAX:
            cands.add(L + 1)             # just out of range -> '.'
        cands.add(min(L + 7, KMAX))
        cands.add(KMAX)
        if n >= 1:
            Lprev = flen(n - 1)
            cands.update([33, 34, 35, 36])           # prefix / inner start split
            for base in (34 + Lprev, 66 + Lprev):    # inner->B and B->inner splits
                cands.update([base - 1, base, base + 1, base + 2])
        else:
            cands.update([33, 34, 35, 74, 75, 76])
        cands = sorted(c for c in cands if 1 <= c <= KMAX)
        k = draw(st.sampled_from(cands))
        pairs.append((n, k))
    return _stdin(pairs)


# Deterministic enumeration of structured small cases (bounded domain).
SMALL_CASES = []
for _n in range(0, 6):
    _L = flen(_n)
    _ks = {1, 2, 3, _L, _L - 1, _L + 1}
    if _n >= 1:
        _Lp = flen(_n - 1)
        _ks.update([33, 34, 35, 36])
        _ks.update([34 + _Lp - 1, 34 + _Lp, 34 + _Lp + 1, 34 + _Lp + 2])   # inner|B
        _ks.update([66 + _Lp - 1, 66 + _Lp, 66 + _Lp + 1, 66 + _Lp + 2])   # B|inner
        _ks.add(34 + 2 * _Lp + 32)                                          # inner|C
    for _k in _ks:
        if 1 <= _k <= KMAX:
            SMALL_CASES.append((_n, _k))


@st.composite
def gen_small_sweep(draw):
    q = draw(st.integers(1, 10))
    pairs = [draw(st.sampled_from(SMALL_CASES)) for _ in range(q)]
    return _stdin(pairs)


@st.composite
def gen_meta(draw):
    m = draw(st.integers(1, 3))
    pairs = []
    for _ in range(m):
        n = draw(st.integers(0, 55))
        L = flen(n)
        kc = [1, KMAX]
        if L <= KMAX:
            kc += [L, max(1, L - 1)]
        if L + 1 <= KMAX:
            kc.append(L + 1)
        kc.append(draw(st.integers(1, KMAX)))
        pairs.append((n, draw(st.sampled_from(kc))))
    pairs.append(pairs[0])   # duplicate the first query at the end
    return _stdin(pairs)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@given(gen_mixed())
@settings(max_examples=30, deadline=None)
def test_mixed(stdin):
    _verify(stdin)


@given(gen_boundary())
@settings(max_examples=35, deadline=None)
def test_boundary(stdin):
    _verify(stdin)


@given(gen_small_sweep())
@settings(max_examples=35, deadline=None)
def test_small_sweep(stdin):
    _verify(stdin)


@given(gen_meta())
@settings(max_examples=8, deadline=None)
def test_metamorphic(stdin):
    q, pairs = _parse(stdin)
    out = run_candidate(stdin)
    res = out.rstrip('\r\n')
    assert len(res) == q, ("wrong length", q, repr(out))

    # Internal consistency: identical queries give identical answers.
    assert res[-1] == res[0], ("duplicate query inconsistent", res[0], res[-1])

    # Metamorphic: a query's answer is independent of batch/position.
    for i, (n, k) in enumerate(pairs):
        single = run_candidate("1\n{} {}\n".format(n, k)).rstrip('\r\n')
        assert len(single) == 1, ("single query wrong length", n, k, repr(single))
        assert single[0] == res[i], ("position dependence", n, k, single[0], res[i])