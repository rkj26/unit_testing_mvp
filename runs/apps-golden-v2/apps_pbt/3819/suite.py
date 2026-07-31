import itertools
from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

# ---------------------------------------------------------------------------
# Problem: "Nauuo and Cards".  n numbered cards (1..n) plus n empty cards (0)
# are split into a hand `a` (n cards, a multiset) and a pile `b` (n cards,
# top->bottom).  One operation = play a hand card to the bottom of the pile,
# then draw the top pile card.  Goal: make the pile read 1,2,...,n top->bottom
# in the minimum number of operations.
#
# MODEL (used only to derive SOUND necessary conditions, never to recompute
# the optimum): after exactly T operations the pile occupies "global tape
# positions" T+1 .. T+n, and card i must end at global position T+i.  Hence for
# every card i:
#   * option (a) i <= n-T : card i is never played, so it must already sit at
#                           original pile position (1-indexed) T+i.
#   * option (b) i >  n-T : card i is played in the last n ops (at op T+i-n), so
#                           it must be in hand in time: pos[i]==0 (started in
#                           hand) OR pos[i] <= T+i-n-1 (drawn early enough).
# These conditions are NECESSARY for ANY number of ops T that sorts the pile,
# hence the true minimum satisfies them (verified: examples give 2, 4, 18).
# ---------------------------------------------------------------------------


def _parse_out(stdout):
    toks = stdout.split()
    assert len(toks) == 1, "output must be a single integer, got: %r" % (stdout,)
    return int(toks[0])


def _parse_stdin(stdin):
    lines = stdin.split("\n")
    n = int(lines[0])
    a = list(map(int, lines[1].split()))
    b = list(map(int, lines[2].split()))
    return n, a, b


def _pos_array(n, b):
    # pos[card] = 1-indexed position of card in the pile, 0 if the card is in hand
    pos = [0] * (n + 1)
    for idx, x in enumerate(b):
        if x != 0:
            pos[x] = idx + 1
    return pos


def _satisfies_AB(n, pos, T):
    if T < 0:
        return False
    for i in range(1, n + 1):
        if i <= n - T:
            if pos[i] != T + i:          # option (a) required and pinned
                return False
        else:
            if not (pos[i] == 0 or pos[i] <= T + i - n - 1):   # option (b)
                return False
    return True


def _ub(n, pos):
    # Provably achievable strategy: while a numbered card remains in the pile the
    # hand always holds an empty card (hand has n slots, and if all n were
    # numbered then no numbered card would remain in the pile), so we can drain
    # every numbered card into the hand in max(pos) ops, then play 1..n (n ops).
    pm = max(pos[1:]) if n >= 1 else 0
    return pm + n


def _lb(n, pos):
    # A pile card with pos[i] < i can never stay in place (option (a) needs
    # pos[i]=T+i>i), so it is forced to option (b): T >= pos[i]+n+1-i.
    best = 0
    for i in range(1, n + 1):
        if pos[i] != 0 and pos[i] < i:
            best = max(best, pos[i] + n + 1 - i)
    return best


def _make_ab(n, card_pos):
    # card_pos: dict card -> 0-indexed pile position; every other card is in hand.
    b = [0] * n
    for c, p in card_pos.items():
        b[p] = c
    hand_cards = [c for c in range(1, n + 1) if c not in card_pos]
    zeros = n - len(hand_cards)
    a = hand_cards + [0] * zeros           # order in hand is irrelevant to answer
    return a, b


def _build_stdin(n, a, b):
    return "%d\n%s\n%s\n" % (n, " ".join(map(str, a)), " ".join(map(str, b)))


def _check(stdin, out):
    n, a, b = _parse_stdin(stdin)
    pos = _pos_array(n, b)
    assert 0 <= out, ("negative answer", out, stdin)
    assert out <= _ub(n, pos), ("exceeds provable upper bound", out, _ub(n, pos), stdin)
    assert out >= _lb(n, pos), ("below provable lower bound", out, _lb(n, pos), stdin)
    is_sorted = all(b[i] == i + 1 for i in range(n))
    if is_sorted:
        assert out == 0, ("already-sorted pile must need 0 ops", out, stdin)
    else:
        assert out >= 1, ("unsorted pile must need >=1 op", out, stdin)
    assert _satisfies_AB(n, pos, out), ("output violates achievability certificate", out, stdin)


# ---------------------------------------------------------------------------
# Generators (aggressively target the trigger regions)
# ---------------------------------------------------------------------------

@st.composite
def gen_general(draw):
    n = draw(st.integers(min_value=1, max_value=80))
    k = draw(st.integers(min_value=0, max_value=n))
    pos_perm = draw(st.permutations(list(range(n))))
    card_perm = draw(st.permutations(list(range(1, n + 1))))
    card_pos = {}
    for j in range(k):
        card_pos[card_perm[j]] = pos_perm[j]
    a, b = _make_ab(n, card_pos)
    return _build_stdin(n, a, b)


@st.composite
def gen_chain(draw):
    # cards 1..L placed consecutively in the pile -> pos[i]=start+i.  This lines up
    # the option-(a) chain exactly at T=start, probing the case-1/reset boundary
    # and the i<=n-T vs i>n-T off-by-one where threshold backdoors hide.
    n = draw(st.integers(min_value=1, max_value=120))
    L = draw(st.integers(min_value=0, max_value=n))
    card_pos = {}
    if L >= 1:
        start = draw(st.integers(min_value=0, max_value=n - L))
        for i in range(1, L + 1):
            card_pos[i] = start + (i - 1)
    free = list(draw(st.permutations([p for p in range(n) if p not in set(card_pos.values())])))
    for c in range(L + 1, n + 1):
        if free and draw(st.booleans()):
            card_pos[c] = free.pop()
    a, b = _make_ab(n, card_pos)
    return _build_stdin(n, a, b)


@st.composite
def gen_cardn(draw):
    # place card n (the one forced to the bottom) at extreme depths, and card 1
    # around, to exercise the tight lower bound pos[n]+1 and depth thresholds.
    n = draw(st.integers(min_value=1, max_value=120))
    card_pos = {}
    if draw(st.booleans()):
        card_pos[n] = draw(st.integers(min_value=0, max_value=n - 1))
    if n >= 2 and draw(st.booleans()):
        free = [p for p in range(n) if p not in set(card_pos.values())]
        card_pos[1] = draw(st.sampled_from(free))
    others = list(draw(st.permutations([c for c in range(1, n + 1) if c not in card_pos])))
    m = draw(st.integers(min_value=0, max_value=len(others)))
    for c in others[:m]:
        free = [p for p in range(n) if p not in set(card_pos.values())]
        if not free:
            break
        card_pos[c] = draw(st.sampled_from(free))
    a, b = _make_ab(n, card_pos)
    return _build_stdin(n, a, b)


@st.composite
def gen_extremes(draw):
    # degenerate structures: all-in-hand, already-sorted, reversed, full random
    # permutation, rotated-by-one, and one-swap-from-sorted.
    n = draw(st.integers(min_value=1, max_value=200))
    choice = draw(st.integers(min_value=0, max_value=5))
    card_pos = {}
    if choice == 0:
        pass                                              # all in hand -> answer n
    elif choice == 1:
        card_pos = {c: c - 1 for c in range(1, n + 1)}     # already sorted -> 0
    elif choice == 2:
        card_pos = {c: n - c for c in range(1, n + 1)}     # reversed
    elif choice == 3:
        perm = list(draw(st.permutations(list(range(n)))))
        card_pos = {c: perm[c - 1] for c in range(1, n + 1)}
    elif choice == 4:
        card_pos = {c: c % n for c in range(1, n + 1)}     # rotate sorted by one
    else:
        card_pos = {c: c - 1 for c in range(1, n + 1)}
        if n >= 2:
            i = draw(st.integers(min_value=1, max_value=n))
            j = draw(st.integers(min_value=1, max_value=n))
            card_pos[i], card_pos[j] = card_pos[j], card_pos[i]
    a, b = _make_ab(n, card_pos)
    return _build_stdin(n, a, b)


@st.composite
def gen_large(draw):
    # extreme magnitude of n (structured so we avoid huge random permutations)
    n = draw(st.sampled_from([300, 500, 1000, 2000]))
    choice = draw(st.integers(min_value=0, max_value=3))
    card_pos = {}
    if choice == 0:
        card_pos = {c: c - 1 for c in range(1, n + 1)}     # sorted
    elif choice == 1:
        card_pos = {c: n - c for c in range(1, n + 1)}     # reversed
    elif choice == 2:
        pass                                              # all in hand
    else:
        card_pos = {c: c - 1 for c in range(1, n)}         # sorted except card n in hand
    a, b = _make_ab(n, card_pos)
    return _build_stdin(n, a, b)


# deterministic exhaustive sweep of the small bounded domain n in {1,2,3}
_SMALL = []
for _n in (1, 2, 3):
    _cards = list(range(1, _n + 1))
    for _k in range(_n + 1):
        for _pc in itertools.combinations(_cards, _k):
            for _pp in itertools.permutations(range(_n), _k):
                _SMALL.append((_n, tuple(zip(_pc, _pp))))


@st.composite
def gen_small(draw):
    n, cp = draw(st.sampled_from(_SMALL))
    a, b = _make_ab(n, dict(cp))
    return _build_stdin(n, a, b)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@given(st.one_of(gen_general(), gen_cardn(), gen_extremes()))
@settings(max_examples=55, deadline=None)
def test_core_certificate_and_bounds(stdin):
    out = _parse_out(run_candidate(stdin))
    _check(stdin, out)


@given(gen_chain())
@settings(max_examples=40, deadline=None)
def test_chain_thresholds(stdin):
    out = _parse_out(run_candidate(stdin))
    _check(stdin, out)


@given(gen_small())
@settings(max_examples=45, deadline=None)
def test_small_exhaustive(stdin):
    out = _parse_out(run_candidate(stdin))
    _check(stdin, out)


@given(st.one_of(gen_general(), gen_cardn(), gen_chain()))
@settings(max_examples=18, deadline=None)
def test_hand_permutation_invariance(stdin):
    # The hand is a multiset; reordering the cards she holds cannot change the
    # minimum number of operations.
    n, a, b = _parse_stdin(stdin)
    out1 = _parse_out(run_candidate(stdin))
    a2 = sorted(a, reverse=True)                    # a valid permutation of the same hand
    out2 = _parse_out(run_candidate(_build_stdin(n, a2, b)))
    assert out1 == out2, ("reordering the hand changed the answer", out1, out2, stdin)
    _check(stdin, out1)


@given(gen_large())
@settings(max_examples=12, deadline=None)
def test_large_scale(stdin):
    out = _parse_out(run_candidate(stdin))
    _check(stdin, out)
