import string
from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str


# ---------------------------------------------------------------------------
# Parsing / helpers
# ---------------------------------------------------------------------------

def _parse(stdout):
    """Parse candidate output into (k, suffix_list). Malformed output -> AssertionError."""
    lines = [ln.strip() for ln in stdout.split('\n')]
    while lines and lines[-1] == '':
        lines.pop()
    assert lines, "empty output; expected at least the count line"
    try:
        k = int(lines[0])
    except Exception:
        raise AssertionError("first line is not an integer: %r" % (lines[0],))
    assert k >= 0, "count k must be non-negative, got %d" % k
    return k, lines[1:]


def _check_format(k, suffixes):
    assert k == len(suffixes), "count k=%d but %d suffix lines follow" % (k, len(suffixes))
    for t in suffixes:
        assert len(t) in (2, 3), "suffix %r has length %d (must be 2 or 3)" % (t, len(t))
        assert all('a' <= ch <= 'z' for ch in t), "suffix %r has non-lowercase chars" % (t,)
    assert len(set(suffixes)) == len(suffixes), "duplicate suffixes in output"
    assert suffixes == sorted(suffixes), "suffixes not in lexicographic order: %r" % (suffixes,)


def _candidate_substrings(s):
    """Every achievable morpheme is a length-2/3 substring starting at offset >= 5."""
    n = len(s)
    out = set()
    for L in (2, 3):
        for i in range(5, n - L + 1):
            out.add(s[i:i + L])
    return out


def _witness_morphemes(s):
    """Provable LOWER bound on the answer set.

    For a first-morpheme start i (i >= 5, so root s[0:i] has length >= 5), any tiling of
    the tail [i, n) into 1..3 pieces of length 2/3 with no two consecutive pieces equal is
    an explicit valid Reberland word (root + those morphemes). Hence every piece in such a
    tiling is achievable and MUST appear in a correct answer.
    """
    n = len(s)
    W = set()
    for i in range(5, n - 1):          # first morpheme starts at i>=5, needs at least 2 chars
        L = n - i                      # number of characters to cover in the tail
        # one morpheme
        if L in (2, 3):
            W.add(s[i:n])
        # two morphemes
        for l1 in (2, 3):
            l2 = L - l1
            if l2 in (2, 3):
                a, b = s[i:i + l1], s[i + l1:n]
                if a != b:
                    W.add(a); W.add(b)
        # three morphemes
        for l1 in (2, 3):
            for l2 in (2, 3):
                l3 = L - l1 - l2
                if l3 in (2, 3):
                    a = s[i:i + l1]
                    b = s[i + l1:i + l1 + l2]
                    c = s[i + l1 + l2:n]
                    if a != b and b != c:
                        W.add(a); W.add(b); W.add(c)
    return W


def _mkstr(draw, n, alpha):
    return draw(st.text(alphabet=list(alpha), min_size=n, max_size=n))


# ---------------------------------------------------------------------------
# Generators -- deliberately manufacture the trigger regions
# ---------------------------------------------------------------------------

@st.composite
def gen_general(draw):
    mode = draw(st.integers(0, 4))
    if mode == 0:                                             # tiny threshold region
        n = draw(st.integers(5, 10)); alpha = draw(st.sampled_from(['a', 'ab', 'abc']))
    elif mode == 1:                                           # all identical letters
        n = draw(st.integers(5, 60)); alpha = 'a'
    elif mode == 2:                                           # tiny alphabet -> heavy dups
        n = draw(st.integers(7, 120)); alpha = draw(st.sampled_from(['ab', 'abc', 'abcd']))
    elif mode == 3:                                           # full alphabet, mid size
        n = draw(st.integers(5, 200)); alpha = string.ascii_lowercase
    else:                                                     # large magnitude
        n = draw(st.integers(200, 400)); alpha = draw(st.sampled_from(['ab', 'abcde', string.ascii_lowercase]))
    return _mkstr(draw, n, alpha) + '\n'


@st.composite
def gen_structured(draw):
    """Bias toward adjacency-constraint edges (repeats), where 'no two equal in a row' bites."""
    mode = draw(st.integers(0, 3))
    if mode == 0:
        n = draw(st.integers(7, 30)); alpha = 'a'
    elif mode == 1:
        n = draw(st.integers(7, 40)); alpha = 'ab'
    elif mode == 2:
        n = draw(st.integers(7, 80)); alpha = draw(st.sampled_from(['ab', 'abc']))
    else:
        n = draw(st.integers(7, 150)); alpha = 'abcdefghij'
    return _mkstr(draw, n, alpha) + '\n'


@st.composite
def gen_small(draw):
    """Length 5 and 6 exactly -- the region where the answer is provably empty."""
    n = draw(st.sampled_from([5, 6]))
    alpha = draw(st.sampled_from(['a', 'ab', 'abc', string.ascii_lowercase]))
    return _mkstr(draw, n, alpha) + '\n'


@st.composite
def gen_meta(draw):
    mode = draw(st.integers(0, 2))
    if mode == 0:
        n = draw(st.integers(5, 15)); alpha = 'ab'
    elif mode == 1:
        n = draw(st.integers(7, 50)); alpha = 'abc'
    else:
        n = draw(st.integers(7, 100)); alpha = string.ascii_lowercase
    return _mkstr(draw, n, alpha) + '\n'


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@given(gen_general())
@settings(max_examples=30, deadline=None)
def test_output_format(stdin):
    s = stdin.rstrip('\n')
    k, suffixes = _parse(run_candidate(stdin))
    _check_format(k, suffixes)
    # necessary condition: each reported suffix must occur as a length-2/3
    # substring starting at a valid root offset (>= 5) of s.
    allowed = _candidate_substrings(s)
    for t in suffixes:
        assert t in allowed, "suffix %r never occurs at offset>=5 in %r" % (t, s)


@given(gen_structured())
@settings(max_examples=40, deadline=None)
def test_witness_lower_bound(stdin):
    s = stdin.rstrip('\n')
    k, suffixes = _parse(run_candidate(stdin))
    _check_format(k, suffixes)
    out = set(suffixes)
    missing = _witness_morphemes(s) - out
    assert not missing, "provably-achievable suffixes missing from output: %r" % (sorted(missing),)
    allowed = _candidate_substrings(s)
    for t in suffixes:
        assert t in allowed, "suffix %r not a valid substring at offset>=5 of %r" % (t, s)


@given(gen_small())
@settings(max_examples=20, deadline=None)
def test_small_n_is_zero(stdin):
    s = stdin.rstrip('\n')
    assert len(s) in (5, 6)
    k, suffixes = _parse(run_candidate(stdin))
    assert k == 0 and suffixes == [], \
        "|s|=%d leaves no room for any morpheme; expected 0 but got k=%d %r" % (len(s), k, suffixes)


@given(gen_meta())
@settings(max_examples=15, deadline=None)
def test_metamorphic_prepend(stdin):
    s = stdin.rstrip('\n')
    k1, suf1 = _parse(run_candidate(stdin))
    _check_format(k1, suf1)
    s2 = 'a' + s                                   # prepend -> root only gets longer
    k2, suf2 = _parse(run_candidate(s2 + '\n'))
    _check_format(k2, suf2)
    lost = set(suf1) - set(suf2)
    assert not lost, "prepending a char must not drop suffixes; base=%r lost=%r" % (s, sorted(lost))
