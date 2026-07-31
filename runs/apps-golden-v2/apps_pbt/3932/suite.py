import itertools
from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str


# ---------------------------------------------------------------------------
# Problem recap (for reasoning, NOT solving):
#   Given multiset c_1..c_n (1<=c_i<=n, 1<=n<=24), does there exist a rooted
#   tree on n nodes where every internal node has >=2 children and the multiset
#   of subtree sizes equals {c_i}?  Output "YES"/"NO".
#
# Sound facts used below (each is NECESSARY for a YES, never assumes the answer):
#   * Only the root has subtree size n  -> exactly one c_i == n for YES.
#   * A node with subtree size 2 would have exactly one child (illegal); a leaf
#     has size 1, an internal node has size >=3  -> no c_i == 2 for YES.
#   * Every internal node has >=2 children => #leaves L >= #internal I + 1,
#     with L+I=n  =>  L >= ceil((n+1)/2) = (n+2)//2.  Leaves are exactly the
#     nodes of subtree size 1, so count(c==1) >= (n+2)//2 for YES.
#   * The answer depends only on the multiset of c (permutation invariant).
# ---------------------------------------------------------------------------


def _parse(stdin):
    lines = stdin.split('\n')
    n = int(lines[0])
    c = list(map(int, lines[1].split()))
    return n, c


def _fmt(n, c):
    return f"{n}\n{' '.join(map(str, c))}\n"


# ---- constructive generator of a GUARANTEED-VALID tree's size multiset -------
# Each part returned is a legal subtree size (1 or >=3, never 2), with >=2 parts,
# so the recursion always yields a real tree in which every internal node has
# >=2 children.  Hence the resulting multiset is realizable => answer is YES.

def _partition(draw, S):
    # S >= 2 ; returns parts each in {1} or {>=3}, sum == S, len >= 2
    parts = []
    remaining = S
    while remaining > 0:
        if remaining == 1:
            parts.append(1)
            remaining = 0
        elif remaining == 2:
            parts.extend([1, 1])
            remaining = 0
        elif remaining == 3:
            if parts and draw(st.booleans()):
                parts.append(3)
            else:
                parts.extend([1, 1, 1])
            remaining = 0
        else:  # remaining >= 4 : pick a legal part strictly below remaining
            choices = [1] + list(range(3, remaining))  # excludes 2 and 'remaining'
            p = draw(st.sampled_from(choices))
            parts.append(p)
            remaining -= p
    return parts


def _build(draw, size):
    # size == 1 (leaf) or size >= 3 (internal node with >=2 children)
    if size == 1:
        return [1]
    parts = _partition(draw, size - 1)
    res = [size]
    for p in parts:
        res.extend(_build(draw, p))
    return res


@st.composite
def gen_yes(draw):
    # skip n==2 (no valid tree exists there); n==1 is the lone singleton
    n = draw(st.sampled_from([1] + list(range(3, 25))))
    sizes = [1] if n == 1 else _build(draw, n)
    sizes = list(draw(st.permutations(sizes)))
    return _fmt(n, sizes)


@st.composite
def gen_no(draw):
    typ = draw(st.sampled_from(['two_roots', 'no_root', 'has_two', 'few_ones']))
    if typ == 'two_roots':            # two nodes both claim the whole tree
        n = draw(st.integers(2, 24))
        c = [n, n] + [1] * (n - 2)
    elif typ == 'no_root':            # nobody has subtree size n
        n = draw(st.integers(2, 24))
        c = [draw(st.integers(1, n - 1)) for _ in range(n)]
    elif typ == 'has_two':            # a forbidden size-2 subtree
        n = draw(st.integers(2, 24))
        c = [n] + [1] * (n - 2) + [2]
    else:                             # far too few leaves
        n = draw(st.integers(4, 24))
        c = [n] + [3] * (n - 1)
    c = list(draw(st.permutations(c)))
    return _fmt(n, c)


@st.composite
def gen_general(draw):
    n = draw(st.one_of(st.sampled_from([1, 2, 3, 4, 5, 24]), st.integers(1, 24)))
    edge = [1, n]
    if n >= 2:
        edge.append(2)
    if n >= 3:
        edge.append(3)
    val = st.one_of(st.sampled_from(sorted(set(edge))), st.integers(1, n))
    c = [draw(val) for _ in range(n)]
    return _fmt(n, c)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@given(gen_general())
@settings(max_examples=30, deadline=None)
def test_format_and_necessary(stdin):
    out = run_candidate(stdin).strip().upper()
    assert out in ("YES", "NO"), f"output must be YES/NO, got {out!r}"
    n, c = _parse(stdin)
    if out == "YES":
        # every one of these is a proven necessary condition for a valid tree
        assert c.count(n) == 1, "YES requires exactly one subtree of size n (the root)"
        assert 2 not in c, "YES impossible when some required subtree size is 2"
        assert c.count(1) >= (n + 2) // 2, "YES requires at least ceil((n+1)/2) leaves"


@given(gen_yes())
@settings(max_examples=25, deadline=None)
def test_constructed_yes(stdin):
    # stdin is the size multiset of a concretely-built legal tree => must be YES
    out = run_candidate(stdin).strip().upper()
    assert out == "YES", f"a realizable tree must be YES, got {out!r} for {stdin!r}"


@given(gen_no())
@settings(max_examples=25, deadline=None)
def test_constructed_no(stdin):
    # each instance violates a necessary condition => must be NO
    out = run_candidate(stdin).strip().upper()
    assert out == "NO", f"an unrealizable instance must be NO, got {out!r} for {stdin!r}"


@given(gen_general())
@settings(max_examples=12, deadline=None)
def test_permutation_invariant(stdin):
    n, c = _parse(stdin)
    base = run_candidate(stdin).strip().upper()
    assert base in ("YES", "NO"), f"output must be YES/NO, got {base!r}"
    variants = {tuple(sorted(c)), tuple(reversed(c)), tuple(c[1:] + c[:1])}
    for perm in variants:
        out2 = run_candidate(_fmt(n, list(perm))).strip().upper()
        assert out2 == base, (
            f"answer must depend only on the multiset: {c} -> {base} but "
            f"{list(perm)} -> {out2}"
        )


# Fully determined small domain (n in {1,2,3}) -- deterministic exhaustive sweep.
_SMALL = [("1\n1\n", "YES")]
for combo in itertools.product([1, 2], repeat=2):            # n=2: never buildable
    _SMALL.append((f"2\n{' '.join(map(str, combo))}\n", "NO"))
for combo in itertools.product([1, 2, 3], repeat=3):         # n=3: only {1,1,3} works
    _SMALL.append((f"3\n{' '.join(map(str, combo))}\n",
                   "YES" if sorted(combo) == [1, 1, 3] else "NO"))


@given(st.just(0))
@settings(max_examples=1, deadline=None)
def test_small_exact(_):
    for stdin, expected in _SMALL:
        out = run_candidate(stdin).strip().upper()
        assert out == expected, f"{stdin!r} expected {expected} got {out!r}"
