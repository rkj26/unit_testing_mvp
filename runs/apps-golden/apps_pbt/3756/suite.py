from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str


# ---------------------------------------------------------------------------
# Helpers (pure utilities for comparing / validating decimal strings; these do
# NOT solve the problem -- they only relate the candidate's output to the
# input via provable invariants).
# ---------------------------------------------------------------------------

def _cmp_int_str(a, b):
    """Compare two non-negative integer digit strings numerically.
    Avoids int() so 200000-digit values are fine (int() has a str-digit cap)."""
    a = a.lstrip('0') or '0'
    b = b.lstrip('0') or '0'
    if len(a) != len(b):
        return -1 if len(a) < len(b) else 1
    if a == b:
        return 0
    return -1 if a < b else 1


def _cmp_dec(ai, af, bi, bf):
    """Compare non-negative decimals given as (int_part_str, frac_part_str)."""
    c = _cmp_int_str(ai, bi)
    if c != 0:
        return c
    L = max(len(af), len(bf))
    af2 = af + '0' * (L - len(af))
    bf2 = bf + '0' * (L - len(bf))
    if af2 == bf2:
        return 0
    return -1 if af2 < bf2 else 1


def _inc_int_str(s):
    """Return the integer digit string s + 1 (big-number safe)."""
    d = list(s)
    i = len(d) - 1
    while i >= 0:
        if d[i] == '9':
            d[i] = '0'
            i -= 1
        else:
            d[i] = chr(ord(d[i]) + 1)
            return ''.join(d)
    return '1' + ''.join(d)


def _first_ge5(fp):
    """Index of first fractional digit >= 5, or -1 if none."""
    for idx, c in enumerate(fp):
        if c >= '5':
            return idx
    return -1


def _split_num(s):
    if '.' in s:
        a, b = s.split('.', 1)
        return a, b
    return s, ""


def _cmp_num(x, y):
    xi, xf = _split_num(x)
    yi, yf = _split_num(y)
    return _cmp_dec(xi, xf, yi, yf)


def _parse_output(raw):
    """Validate output is a well-formed positive number with no trailing zeros
    and no leading zeros; return (int_part, frac_part)."""
    assert raw is not None, "candidate produced no output"
    s = raw.strip()
    assert s != "", "empty output"
    assert '\n' not in s and ' ' not in s and '\t' not in s, "output not a single token: %r" % raw
    assert s.count('.') <= 1, "more than one decimal point: %r" % s
    assert all(ch.isdigit() or ch == '.' for ch in s), "unexpected characters: %r" % s
    if '.' in s:
        i, f = s.split('.', 1)
        assert len(i) >= 1, "missing integer part: %r" % s
        assert len(f) >= 1, "empty fraction after '.': %r" % s
        assert f[-1] != '0', "trailing zero in fraction: %r" % s
    else:
        i, f = s, ""
    assert len(i) >= 1, "missing integer part: %r" % s
    assert i == '0' or i[0] != '0', "leading zero in integer part: %r" % s
    return i, f


def _check_structure(Gi, Gf, Ri, Rf):
    """A correct answer is reachable ONLY by (A) no rounding, (B) truncating the
    fraction to a prefix with the new last digit incremented by exactly 1, or
    (C) carrying into the integer part (fraction gone, integer + 1). The
    fraction prefix is otherwise untouched (no intra-fraction carry can occur
    because every digit left of the first >=5 digit is <=4)."""
    normGi = Gi.lstrip('0') or '0'
    normRi = Ri.lstrip('0') or '0'
    inc = _inc_int_str(Gi).lstrip('0') or '0'
    # (A) unchanged
    if normRi == normGi and Rf == Gf:
        return True
    # (C) carried into integer, fraction fully rounded away
    if Rf == "":
        return normRi == inc
    # (B) rounded within the fraction
    k = len(Rf)
    if not (1 <= k < len(Gf)):
        return False
    if normRi != normGi:
        return False
    if Rf[:k - 1] != Gf[:k - 1]:
        return False
    if ord(Rf[k - 1]) != ord(Gf[k - 1]) + 1:
        return False
    return True


def _build_stdin(int_str, frac_str, t):
    grade = int_str + '.' + frac_str
    n = len(grade)
    return "%d %d\n%s\n" % (n, t, grade)


def _parse_stdin(stdin):
    lines = stdin.split('\n')
    parts = lines[0].split()
    t = int(parts[1])
    grade = lines[1]
    ip, fp = grade.split('.', 1)
    return ip, fp, t


def _check(stdin):
    """Run the candidate on `stdin` and assert every property a correct output
    MUST satisfy. Returns the (stripped) output string."""
    ip, fp, t = _parse_stdin(stdin)
    grade = ip + '.' + fp
    raw = run_candidate(stdin)
    Ri, Rf = _parse_output(raw)
    out = raw.strip()

    normGi = ip.lstrip('0') or '0'
    normRi = Ri.lstrip('0') or '0'

    # (1) He may decline to round -> R >= G.
    assert _cmp_dec(Ri, Rf, ip, fp) >= 0, "R < G: R=%r G=%r" % (out, grade)
    # (2) A single carry into the integer is the most he can gain -> R <= floor(G)+1.
    ub = _inc_int_str(ip)
    assert _cmp_dec(Ri, Rf, ub, "") <= 0, "R > floor(G)+1: R=%r G=%r bound=%s" % (out, grade, ub)
    # (3) Rounding can only shorten the fraction, never lengthen it.
    assert len(Rf) <= len(fp), "fraction grew: R=%r G=%r" % (out, grade)
    # (4) Integer part gains at most one digit (carry) -> digit count invariant.
    assert len(normRi) in (len(normGi), len(normGi) + 1), \
        "integer digit count off: R=%r G=%r" % (out, grade)
    # (5) The output must have one of the three reachable structural shapes.
    assert _check_structure(ip, fp, Ri, Rf), "unreachable output structure: R=%r G=%r" % (out, grade)

    i = _first_ge5(fp)
    if i == -1:
        # No fractional digit >= 5: every rounding strictly decreases the value
        # (nothing rounds up, no trailing zeros to drop for free) -> answer == G.
        assert _cmp_dec(Ri, Rf, ip, fp) == 0, "no >=5 digit but output changed: R=%r G=%r" % (out, grade)
    else:
        # A beneficial round exists and t >= 1 -> strictly greater than G.
        assert _cmp_dec(Ri, Rf, ip, fp) > 0, "roundable digit present but R not > G: R=%r G=%r" % (out, grade)
        k = len(Rf)
        rounds_used = i - k + 1
        # The greedy carry-chain from the first >=5 digit down to position k
        # costs exactly (i - k + 1) rounds.
        assert rounds_used >= 1, "impossible round count: R=%r G=%r i=%d k=%d" % (out, grade, i, k)
        assert rounds_used <= t, "over-rounded (used %d > t=%d): R=%r G=%r" % (rounds_used, t, out, grade)
        # For the chain to have travelled from i down to k, every digit it passed
        # through must be exactly '4' (so each +1 became 5 and propagated).
        assert all(c == '4' for c in fp[k:i]), \
            "carry chain through non-'4' digit fp[%d:%d]=%r: R=%r G=%r" % (k, i, fp[k:i], out, grade)
        # No under-rounding: if the last kept digit is still >=5 another round
        # would help, so the budget must be exhausted.
        if Rf and Rf[-1] >= '5':
            assert rounds_used == t, \
                "under-rounded (last digit >=5 but rounds=%d < t=%d): R=%r G=%r" % (rounds_used, t, out, grade)
    return out


# ---------------------------------------------------------------------------
# Input generators -- deliberately manufacture the rare trigger regions.
# ---------------------------------------------------------------------------

@st.composite
def _int_part(draw, max_len=6):
    mode = draw(st.sampled_from(['zero', 'nines', 'single', 'general']))
    if mode == 'zero':
        return "0"
    if mode == 'nines':
        return "9" * draw(st.integers(1, max_len))
    if mode == 'single':
        return str(draw(st.integers(0, 9)))
    L = draw(st.integers(1, max_len))
    first = draw(st.integers(1, 9))
    rest = [draw(st.integers(0, 9)) for _ in range(L - 1)]
    return str(first) + ''.join(map(str, rest))


@st.composite
def _frac_part(draw, max_len=10):
    mode = draw(st.sampled_from(
        ['low', 'chain4', 'lead_high', 'nines', 'one_high', 'rand']))
    if mode == 'low':
        # all digits < 5 -> no rounding is ever beneficial
        L = draw(st.integers(1, max_len))
        body = [draw(st.integers(0, 4)) for _ in range(L - 1)]
        last = draw(st.integers(1, 4))
        return ''.join(map(str, body)) + str(last)
    if mode == 'chain4':
        # <5 prefix, run of 4s, a >=5 trigger -> long left-propagating carry
        pre = [draw(st.integers(0, 4)) for _ in range(draw(st.integers(0, 3)))]
        fours = [4] * draw(st.integers(0, max_len))
        trig = draw(st.integers(5, 9))
        return ''.join(map(str, pre + fours + [trig]))
    if mode == 'lead_high':
        # first fractional digit >= 5 -> immediate carry into integer part
        s = [draw(st.integers(5, 9))]
        s += [draw(st.integers(0, 9)) for _ in range(draw(st.integers(0, max_len)))]
        if s[-1] == 0:
            s[-1] = draw(st.integers(1, 9))
        return ''.join(map(str, s))
    if mode == 'nines':
        return '9' * draw(st.integers(1, max_len))
    if mode == 'one_high':
        L = draw(st.integers(1, max_len))
        s = [draw(st.integers(0, 4)) for _ in range(L)]
        s[draw(st.integers(0, L - 1))] = draw(st.integers(5, 9))
        if s[-1] == 0:
            s[-1] = draw(st.integers(1, 9))
        return ''.join(map(str, s))
    # rand
    L = draw(st.integers(1, max_len))
    s = [draw(st.integers(0, 9)) for _ in range(L)]
    if s[-1] == 0:
        s[-1] = draw(st.integers(1, 9))
    return ''.join(map(str, s))


@st.composite
def _t_for(draw, frac_len):
    m = max(1, frac_len)
    return draw(st.sampled_from([
        1, 2, 3,
        max(1, m - 1),          # just below saturation
        m,                      # exactly enough to saturate
        m + 1,
        draw(st.integers(1, m + 2)),
        10 ** 9,                # max
        draw(st.integers(10 ** 6, 10 ** 9)),
    ]))


@st.composite
def make_input(draw):
    ip = draw(_int_part())
    fp = draw(_frac_part())
    t = draw(_t_for(len(fp)))
    return _build_stdin(ip, fp, t)


@st.composite
def make_input_small(draw):
    # deterministic-ish sweep of the 4/5/6 rounding threshold on tiny inputs
    ip = draw(st.sampled_from(['0', '1', '4', '5', '9', '10', '19', '99', '49']))
    L = draw(st.integers(1, 3))
    digs = draw(st.lists(st.sampled_from([0, 1, 4, 5, 6, 9]),
                         min_size=L, max_size=L))
    if digs[-1] == 0:
        digs[-1] = draw(st.sampled_from([1, 4, 5, 9]))
    fp = ''.join(map(str, digs))
    t = draw(st.sampled_from([1, 2, 3, len(fp), 10 ** 9]))
    return _build_stdin(ip, fp, t)


@st.composite
def make_input_extreme(draw):
    kind = draw(st.sampled_from(
        ['long_chain', 'long_nines', 'big_int_carry', 'long_low', 'mixed_big']))
    if kind == 'long_chain':
        L = draw(st.integers(50, 2000))
        fp = '4' * L + str(draw(st.integers(5, 9)))
        ip = draw(st.sampled_from(['0', '7', '99', '999', '123456']))
    elif kind == 'long_nines':
        L = draw(st.integers(50, 2000))
        fp = '9' * L
        ip = draw(st.sampled_from(['9', '99', '999', '1', '0']))
    elif kind == 'big_int_carry':
        ip = '9' * draw(st.integers(1, 2000))
        fp = str(draw(st.integers(5, 9)))
    elif kind == 'long_low':
        L = draw(st.integers(50, 2000))
        body = ''.join(draw(st.sampled_from(['0', '1', '2', '3', '4']))
                       for _ in range(L - 1))
        fp = body + draw(st.sampled_from(['1', '2', '3', '4']))
        ip = draw(st.sampled_from(['0', '5', '55555']))
    else:  # mixed_big
        L = draw(st.integers(50, 2000))
        fp = ''.join(draw(st.sampled_from(list('01234444459')))
                     for _ in range(L))
        if fp[-1] == '0':
            fp = fp[:-1] + '7'
        ip = draw(st.sampled_from(['0', '1', '9', '99999']))
    m = len(fp)
    t = draw(st.sampled_from([1, 2, max(1, m - 1), m, m + 5, 10 ** 9]))
    return _build_stdin(ip, fp, t)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@given(make_input())
@settings(max_examples=45, deadline=None)
def test_structure_and_bounds(stdin):
    _check(stdin)


@given(make_input_small())
@settings(max_examples=40, deadline=None)
def test_threshold_sweep(stdin):
    _check(stdin)


@given(make_input_extreme())
@settings(max_examples=18, deadline=None)
def test_extreme_and_carry(stdin):
    _check(stdin)


@given(make_input())
@settings(max_examples=10, deadline=None)
def test_monotone_in_t(stdin):
    # More seconds can never yield a smaller grade.
    ip, fp, _ = _parse_stdin(stdin)
    m = len(fp)
    ts = sorted({1, max(1, m // 2), m, min(10 ** 9, m + 3)})
    prev = None
    for tt in ts:
        cur = _check(_build_stdin(ip, fp, tt))
        if prev is not None:
            assert _cmp_num(prev, cur) <= 0, \
                "not monotone in t: %r (t smaller) > %r (t larger) for grade %s.%s" % (prev, cur, ip, fp)
        prev = cur


@given(make_input())
@settings(max_examples=12, deadline=None)
def test_saturation_in_t(stdin):
    # At most (#fraction digits) rounds are ever useful, so any t >= that count
    # yields the identical maximal grade.
    ip, fp, _ = _parse_stdin(stdin)
    m = max(1, len(fp))
    r_sat = _check(_build_stdin(ip, fp, m))
    r_huge = _check(_build_stdin(ip, fp, 10 ** 9))
    assert _cmp_num(r_sat, r_huge) == 0, \
        "saturated results differ: t=%d -> %r vs t=1e9 -> %r (grade %s.%s)" % (m, r_sat, r_huge, ip, fp)
    r_below = _check(_build_stdin(ip, fp, max(1, m - 1)))
    assert _cmp_num(r_below, r_sat) <= 0, \
        "t just below saturation exceeded saturated result: %r > %r" % (r_below, r_sat)