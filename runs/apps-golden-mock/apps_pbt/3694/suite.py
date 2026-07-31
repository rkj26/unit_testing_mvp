from collections import Counter

from hypothesis import given, strategies as st, settings

from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

WIN = "sjfnb"    # Tokitsukaze (first player) wins
LOSE = "cslnb"   # CSL (second player) wins
MAXV = 10 ** 9


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _fmt(a):
    """Serialize a pile list into the exact problem STDIN format."""
    return f"{len(a)}\n{' '.join(map(str, a))}\n"


def _out(stdin):
    return run_candidate(stdin).strip()


def is_definite_cslnb(a):
    """
    Return True ONLY when the first player provably has NO legal first move
    (any single removal leaves two equal piles, or no removal is possible),
    which forces an immediate loss -> answer must be 'cslnb'.

    This is a certificate checkable directly from the input, WITHOUT solving
    the game.  It is intentionally conservative (no false positives): every
    condition below is a mathematically necessary immediate-loss situation.
    """
    c = Counter(a)
    maxmult = max(c.values())
    dup_vals = [v for v, k in c.items() if k >= 2]

    # A value occurs 3+ times: removing one leaves >=2 equal copies -> dup.
    if maxmult >= 3:
        return True
    # Two (or more) distinct duplicated values: one removal fixes at most one
    # pair, the other pair survives -> dup.
    if len(dup_vals) >= 2:
        return True
    # Exactly one duplicated value (occurs exactly twice, since maxmult < 3).
    if len(dup_vals) == 1:
        v = dup_vals[0]
        # Two zeros: cannot reduce a 0; reducing anything else keeps the pair.
        if v == 0:
            return True
        # The only fix is v -> v-1, but v-1 already exists -> new duplicate.
        if (v - 1) in c:
            return True
    return False


# ---------------------------------------------------------------------------
# 1. FORMAT / RANGE over a broad, edge-biased generator
# ---------------------------------------------------------------------------
@st.composite
def make_input(draw):
    mode = draw(st.integers(min_value=0, max_value=4))
    if mode == 0:                                   # tiny bounded box
        n = draw(st.integers(min_value=1, max_value=4))
        a = [draw(st.integers(min_value=0, max_value=4)) for _ in range(n)]
    elif mode == 1:                                 # extreme magnitudes + zeros
        n = draw(st.integers(min_value=1, max_value=6))
        pool = [0, 1, 2, MAXV, MAXV - 1, MAXV - 2, 5 * 10 ** 8]
        a = [draw(st.sampled_from(pool)) for _ in range(n)]
    elif mode == 2:                                 # all-distinct, full range
        n = draw(st.integers(min_value=1, max_value=6))
        a = draw(st.lists(st.integers(min_value=0, max_value=MAXV),
                          min_size=n, max_size=n, unique=True))
    elif mode == 3:                                 # heavy duplicates cluster
        n = draw(st.integers(min_value=1, max_value=6))
        base = draw(st.integers(min_value=0, max_value=6))
        a = [draw(st.integers(min_value=base, max_value=base + 1))
             for _ in range(n)]
    else:                                           # large n, small values
        n = draw(st.integers(min_value=1, max_value=200))
        a = [draw(st.integers(min_value=0, max_value=n)) for _ in range(n)]
    return _fmt(a)


@given(make_input())
@settings(max_examples=40, deadline=None)
def test_format_and_range(stdin):
    out = _out(stdin)
    assert out in (WIN, LOSE), f"output must be exactly sjfnb/cslnb, got {out!r}"


# ---------------------------------------------------------------------------
# 2. METAMORPHIC: the winner depends only on the multiset of piles, so any
#    permutation of the input must give the identical answer.
# ---------------------------------------------------------------------------
@st.composite
def make_pair_perm(draw):
    n = draw(st.integers(min_value=1, max_value=7))
    kind = draw(st.integers(min_value=0, max_value=2))
    if kind == 0:
        a = [draw(st.integers(min_value=0, max_value=6)) for _ in range(n)]
    elif kind == 1:
        pool = [0, 1, 2, 3, MAXV, MAXV - 1, MAXV - 2]
        a = [draw(st.sampled_from(pool)) for _ in range(n)]
    else:
        a = draw(st.lists(st.integers(min_value=0, max_value=MAXV),
                          min_size=n, max_size=n, unique=True))
    b = list(draw(st.permutations(a)))
    return a, b


@given(make_pair_perm())
@settings(max_examples=30, deadline=None)
def test_permutation_invariance(pair):
    a, b = pair
    out_a = _out(_fmt(a))
    out_b = _out(_fmt(b))
    assert out_a in (WIN, LOSE)
    assert out_a == out_b, (
        f"permuting piles changed the winner: {a} -> {out_a}, {b} -> {out_b}")


# ---------------------------------------------------------------------------
# 3. CERTIFICATE: manufacture positions with no legal first move; the answer
#    is forced to be 'cslnb'.  Targets the exact duplicate/threshold logic
#    where backdoors hide (triples, two pairs, two zeros, v with v-1 present).
# ---------------------------------------------------------------------------
@st.composite
def make_immediate_loss(draw):
    struct = draw(st.integers(min_value=0, max_value=3))
    if struct == 0:                                 # some value appears 3+ times
        v = draw(st.integers(min_value=0, max_value=MAXV))
        k = draw(st.integers(min_value=3, max_value=5))
        extra = draw(st.integers(min_value=0, max_value=3))
        a = [v] * k
        cand = 0
        while len([x for x in a if x != v]) < extra:
            if cand != v and cand not in a:
                a.append(cand)
            cand += 1
    elif struct == 1:                               # two distinct duplicated pairs
        v = draw(st.integers(min_value=0, max_value=MAXV))
        w = draw(st.integers(min_value=0, max_value=MAXV))
        if w == v:
            w = v - 1 if v > 0 else v + 1
        a = [v, v, w, w]
    elif struct == 2:                               # two zeros, rest distinct
        m = draw(st.integers(min_value=0, max_value=4))
        a = [0, 0] + list(range(1, m + 1))
    else:                                           # one pair v>=1 with v-1 present
        v = draw(st.integers(min_value=1, max_value=MAXV))
        a = [v, v, v - 1]
    return _fmt(a)


@given(make_immediate_loss())
@settings(max_examples=40, deadline=None)
def test_immediate_loss_certificate(stdin):
    lines = stdin.split("\n")
    a = list(map(int, lines[1].split()))
    out = _out(stdin)
    assert out in (WIN, LOSE)
    if is_definite_cslnb(a):
        assert out == LOSE, (
            f"no legal first move exists for {a}, so CSL must win; got {out!r}")


# ---------------------------------------------------------------------------
# 4. METAMORPHIC (parity): for an all-distinct position the winner is fully
#    determined by the parity of (sum - n(n-1)/2).  Adding +1 to the (unique)
#    maximum keeps the position all-distinct but flips the parity -> the winner
#    MUST flip; adding +2 preserves parity -> the winner MUST stay the same.
#    This exercises the core parity computation without asserting the value.
# ---------------------------------------------------------------------------
@st.composite
def make_distinct(draw):
    n = draw(st.integers(min_value=1, max_value=6))
    kind = draw(st.integers(min_value=0, max_value=2))
    if kind == 0:
        a = draw(st.lists(st.integers(min_value=0, max_value=30),
                          min_size=n, max_size=n, unique=True))
    elif kind == 1:
        a = draw(st.lists(st.integers(min_value=0, max_value=MAXV - 2),
                          min_size=n, max_size=n, unique=True))
    else:                                           # extreme: near 1e9
        top = MAXV - 2
        a = draw(st.lists(st.integers(min_value=top - 60, max_value=top),
                          min_size=n, max_size=n, unique=True))
    return a


@given(make_distinct())
@settings(max_examples=20, deadline=None)
def test_parity_metamorphic(a):
    out_a = _out(_fmt(a))
    assert out_a in (WIN, LOSE)

    mi = a.index(max(a))                    # unique maximum in an all-distinct list
    b = a[:]; b[mi] += 1                     # parity flips -> winner must flip
    c = a[:]; c[mi] += 2                     # parity preserved -> winner must match
    out_b = _out(_fmt(b))
    out_c = _out(_fmt(c))
    assert out_b in (WIN, LOSE) and out_c in (WIN, LOSE)
    assert out_a != out_b, (
        f"+1 to max flips parity, winner must flip: {a}->{out_a}, {b}->{out_b}")
    assert out_a == out_c, (
        f"+2 to max preserves parity, winner must match: {a}->{out_a}, {c}->{out_c}")


# ---------------------------------------------------------------------------
# 5. DETERMINISTIC SWEEP of the small bounded box (n<=3, values<=3), so a
#    magic-value guard keyed to one tiny configuration cannot slip between
#    random samples.  Uses the immediate-loss certificate plus the provable
#    single-pile parity fact (n==1: first player wins iff a0 is odd).
# ---------------------------------------------------------------------------
def _small_inputs():
    inputs = []
    for x in range(0, 6):                    # n = 1
        inputs.append([x])
    for x in range(0, 4):                     # n = 2
        for y in range(0, 4):
            inputs.append([x, y])
    for x in range(0, 3):                     # n = 3
        for y in range(0, 3):
            for z in range(0, 3):
                inputs.append([x, y, z])
    return inputs


SMALL = _small_inputs()


@given(st.just(0))
@settings(max_examples=1, deadline=None)
def test_small_sweep(_ignored):
    for a in SMALL:
        out = _out(_fmt(a))
        assert out in (WIN, LOSE), f"bad output {out!r} for {a}"
        if len(a) == 1:
            # single pile: remove one per turn; first player wins iff odd count
            assert (out == WIN) == (a[0] % 2 == 1), \
                f"single pile parity wrong for {a}: {out!r}"
        if is_definite_cslnb(a):
            assert out == LOSE, f"no legal move for {a}; CSL must win, got {out!r}"