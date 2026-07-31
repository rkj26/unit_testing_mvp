from collections import Counter
from hypothesis import given, strategies as st, settings
from harness import run_candidate  # run_candidate(stdin: str) -> stdout: str

WIN = {"sjfnb", "cslnb"}


def fmt(vals):
    # Problem input format: line 1 = n, line 2 = space-separated pile sizes.
    return "{}\n{}\n".format(len(vals), " ".join(str(x) for x in vals))


def valid_move_exists(a):
    # True iff the first player has at least one LEGAL first move: pick a
    # nonempty pile, remove one stone, and afterwards all piles are pairwise
    # distinct. Decrementing any instance of a value v is equivalent, so we
    # only try each distinct value once.
    cnt = Counter(a)
    for v in set(a):
        if v == 0:
            continue  # cannot remove a stone from an empty pile
        c = cnt.copy()
        c[v] -= 1
        c[v - 1] += 1
        if all(x <= 1 for x in c.values()):
            return True
    return False


@st.composite
def make_input(draw):
    # Mixed inputs: boundary n=1, duplicates (small ranges) and extreme
    # values (up to 1e9) to probe format/consistency broadly.
    n = draw(st.integers(min_value=1, max_value=30))
    hi = draw(st.sampled_from([1, 2, 5, 100, 10 ** 9]))
    vals = draw(st.lists(st.integers(min_value=0, max_value=hi),
                         min_size=n, max_size=n))
    return vals


@st.composite
def make_dup(draw):
    # Small n with a tiny value range => lots of duplicates and degenerate
    # positions, so "no legal first move" (immediate-loss) configurations
    # occur often and the certificate below actually gets exercised.
    n = draw(st.integers(min_value=1, max_value=8))
    hi = draw(st.integers(min_value=0, max_value=4))
    vals = draw(st.lists(st.integers(min_value=0, max_value=hi),
                         min_size=n, max_size=n))
    return vals


@st.composite
def make_distinct(draw):
    # An all-distinct starting position plus an increment k applied to the
    # (unique) maximum pile.
    n = draw(st.integers(min_value=1, max_value=20))
    vals = draw(st.lists(st.integers(min_value=0, max_value=10 ** 8),
                         min_size=n, max_size=n, unique=True))
    k = draw(st.integers(min_value=1, max_value=10 ** 8))
    return vals, k


@given(make_input())
@settings(max_examples=50, deadline=None)
def test_output_format(vals):
    # Shape/format invariant: output is exactly one of the two case-sensitive
    # tokens.
    out = run_candidate(fmt(vals)).strip()
    assert out in WIN, "output must be 'sjfnb' or 'cslnb', got %r" % out


@given(make_dup())
@settings(max_examples=50, deadline=None)
def test_no_legal_move_means_cslnb(vals):
    # Certificate check derived directly from the rules: if the first player
    # (Tokitsukaze) has no legal first move, she loses immediately, so CSL
    # wins. This is verifiable without solving the game.
    out = run_candidate(fmt(vals)).strip()
    assert out in WIN, "bad output token: %r" % out
    if not valid_move_exists(vals):
        assert out == "cslnb", (
            "no legal first move exists for %r, so CSL must win" % vals)


@given(make_input())
@settings(max_examples=50, deadline=None)
def test_permutation_invariance(vals):
    # Metamorphic: the winner depends only on the MULTISET of pile sizes,
    # never on their order, so every reordering must give the same answer.
    base = run_candidate(fmt(vals)).strip()
    assert base in WIN, "bad output token: %r" % base
    for perm in (sorted(vals), sorted(vals, reverse=True), vals[::-1]):
        other = run_candidate(fmt(perm)).strip()
        assert other == base, (
            "answer changed under reordering: %r->%r vs %r->%r"
            % (vals, base, perm, other))


@given(make_distinct())
@settings(max_examples=50, deadline=None)
def test_parity_metamorphic(data):
    # Metamorphic parity relation for all-distinct positions.
    # For an all-distinct position the game is forced to run until the unique
    # terminal {0,1,...,n-1}: exactly T = sum(a) - n(n-1)/2 moves happen and
    # the first player wins iff T is odd. Raising the UNIQUE maximum pile by k
    # keeps every pile distinct and changes T by exactly k, so the winner
    # flips iff k is odd. (We never need the absolute winner, only the flip.)
    vals, k = data
    o1 = run_candidate(fmt(vals)).strip()
    mx = max(vals)
    vals2 = list(vals)
    vals2[vals2.index(mx)] = mx + k
    o2 = run_candidate(fmt(vals2)).strip()
    assert o1 in WIN and o2 in WIN, "bad output token(s): %r %r" % (o1, o2)
    if k % 2 == 0:
        assert o1 == o2, (
            "even increment to max must not change winner: %r->%r vs %r->%r"
            % (vals, o1, vals2, o2))
    else:
        assert o1 != o2, (
            "odd increment to max must flip winner: %r->%r vs %r->%r"
            % (vals, o1, vals2, o2))
