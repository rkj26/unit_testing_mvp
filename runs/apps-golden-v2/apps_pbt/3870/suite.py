from hypothesis import given, strategies as st, settings

from harness import run_candidate  # run_candidate(stdin: str) -> stdout: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_input(jiro, ciel):
    """jiro: list of (pos, strength); ciel: list of strength -> exact STDIN."""
    lines = ["{} {}".format(len(jiro), len(ciel))]
    for pos, s in jiro:
        lines.append("{} {}".format(pos, s))
    for s in ciel:
        lines.append(str(s))
    return "\n".join(lines) + "\n"


def parse_out(out):
    s = out.strip()
    assert s != "", "empty output"
    return int(s)  # a correct solution prints exactly one integer


def case_a_lower_bound(jiro, ciel):
    """A concretely ACHIEVABLE damage (attack only ATK cards, never clear board,
    no direct hits): for each k, use the k largest Ciel cards to kill the k
    smallest ATK cards. This is a valid lower bound on the true optimum -- we
    never claim more than we can demonstrably achieve, so it can never exceed a
    correct answer."""
    atk = sorted(s for pos, s in jiro if pos == "ATK")   # ascending
    c = sorted(ciel, reverse=True)                        # descending
    best = 0
    kmax = min(len(atk), len(c))
    for k in range(1, kmax + 1):
        chosen_atk = atk[:k]                    # k smallest ATK, ascending
        chosen_ciel = c[:k]                     # k largest Ciel, descending
        atk_desc = chosen_atk[::-1]             # descending
        # feasible perfect matching iff largest-with-largest all satisfy X>=Y
        if all(chosen_ciel[i] >= atk_desc[i] for i in range(k)):
            best = max(best, sum(chosen_ciel) - sum(chosen_atk))
    return best


# ---------------------------------------------------------------------------
# Input generators -- deliberately manufacture the rare / boundary regions
# ---------------------------------------------------------------------------

def strength_strategy(lo=0, hi=8000):
    specials = sorted({v for v in (0, 1, 2, hi - 1, hi, hi // 2) if lo <= v <= hi})
    return st.one_of(
        st.sampled_from(specials),
        st.integers(min_value=lo, max_value=hi),
    )


@st.composite
def cards(draw):
    """Multi-mode generator covering: tiny bounded domain (forces ATK 0 / DEF 0
    and the >= vs > boundary, heavy ties), extreme magnitudes (0 & 8000 mixed),
    all-ATK, and larger general instances."""
    mode = draw(st.integers(0, 3))
    if mode == 0:
        # tiny bounded domain -> exact ATK/DEF-0 threshold, X==Y ties
        n = draw(st.integers(1, 5))
        m = draw(st.integers(1, 5))
        sval = st.integers(0, 3)
        pos = st.sampled_from(["ATK", "DEF"])
    elif mode == 1:
        # extreme magnitudes pinned at bounds, mixed with tiny
        n = draw(st.integers(1, 8))
        m = draw(st.integers(1, 8))
        sval = st.sampled_from([0, 1, 2, 7999, 8000])
        pos = st.sampled_from(["ATK", "DEF"])
    elif mode == 2:
        # all-ATK boards (no DEF obstacles)
        n = draw(st.integers(1, 8))
        m = draw(st.integers(1, 10))
        sval = strength_strategy()
        pos = st.just("ATK")
    else:
        # general, larger instances with boundary-biased strengths
        n = draw(st.integers(1, 30))
        m = draw(st.integers(1, 30))
        sval = strength_strategy()
        pos = st.sampled_from(["ATK", "DEF"])
    jiro = [(draw(pos), draw(sval)) for _ in range(n)]
    ciel = [draw(sval) for _ in range(m)]
    return jiro, ciel


# ===========================================================================
# 1. Format / range + certificate bounds (single run)
# ===========================================================================
@given(cards())
@settings(max_examples=45, deadline=None)
def test_bounds_and_certificates(data):
    jiro, ciel = data
    val = parse_out(run_candidate(build_input(jiro, ciel)))

    # non-negative integer (she can always do nothing)
    assert val >= 0, "damage must be non-negative, got {}".format(val)

    # upper bound: every used card contributes at most its own strength
    # (direct hit = X; ATK attack = X - Y <= X; DEF kill = 0)
    total = sum(ciel)
    assert val <= total, "damage {} exceeds sum of Ciel strengths {}".format(val, total)

    # lower bound: a concretely achievable attack-only strategy
    lb = case_a_lower_bound(jiro, ciel)
    assert val >= lb, "damage {} below achievable {}".format(val, lb)


# ===========================================================================
# 2. Permutation invariance -- cards form multisets; order is irrelevant
# ===========================================================================
@st.composite
def cards_with_perm(draw):
    jiro, ciel = draw(cards())
    jp = draw(st.permutations(list(range(len(jiro)))))
    cp = draw(st.permutations(list(range(len(ciel)))))
    jiro2 = [jiro[i] for i in jp]
    ciel2 = [ciel[i] for i in cp]
    return jiro, ciel, jiro2, ciel2


@given(cards_with_perm())
@settings(max_examples=20, deadline=None)
def test_permutation_invariance(data):
    jiro, ciel, jiro2, ciel2 = data
    a = parse_out(run_candidate(build_input(jiro, ciel)))
    b = parse_out(run_candidate(build_input(jiro2, ciel2)))
    assert a == b, "answer changed under reordering: {} vs {}".format(a, b)


# ===========================================================================
# 3. Positive-integer scaling -- multiply all strengths by c => damage * c
# (all inequalities X>=Y, X>Y and differences X-Y scale exactly by c>0)
# ===========================================================================
@st.composite
def scalable(draw):
    n = draw(st.integers(1, 6))
    m = draw(st.integers(1, 6))
    base_max = draw(st.sampled_from([1, 2, 5, 20, 100, 400]))
    sval = st.integers(0, base_max)
    pos = st.sampled_from(["ATK", "DEF"])
    jiro = [(draw(pos), draw(sval)) for _ in range(n)]
    ciel = [draw(sval) for _ in range(m)]
    max_used = max([s for _, s in jiro] + ciel + [1])
    c = draw(st.integers(1, max(1, 8000 // max(1, max_used))))
    return jiro, ciel, c


@given(scalable())
@settings(max_examples=20, deadline=None)
def test_scaling(data):
    jiro, ciel, c = data
    base = parse_out(run_candidate(build_input(jiro, ciel)))
    jiro_s = [(pos, s * c) for pos, s in jiro]
    ciel_s = [s * c for s in ciel]
    scaled = parse_out(run_candidate(build_input(jiro_s, ciel_s)))
    assert scaled == base * c, "scaling by {} gave {} (expected {})".format(
        c, scaled, base * c
    )


# ===========================================================================
# 4. Monotonicity: adding a Ciel card never decreases the answer
#    (she can always decline to use the extra card)
# ===========================================================================
@st.composite
def add_card(draw):
    jiro, ciel = draw(cards())
    extra = draw(strength_strategy())
    return jiro, ciel, extra


@given(add_card())
@settings(max_examples=22, deadline=None)
def test_monotone_add_ciel(data):
    jiro, ciel, extra = data
    before = parse_out(run_candidate(build_input(jiro, ciel)))
    after = parse_out(run_candidate(build_input(jiro, ciel + [extra])))
    assert after >= before, "adding Ciel card {} decreased answer {}->{}".format(
        extra, before, after
    )


# ===========================================================================
# 5. Monotonicity: raising a Jiro card's strength never increases the answer
#    (every feasibility constraint stays satisfiable and every ATK-attack
#     damage X - Y can only shrink, so the optimum is non-increasing)
# ===========================================================================
@st.composite
def raise_jiro(draw):
    jiro, ciel = draw(cards())
    idx = draw(st.integers(0, len(jiro) - 1))
    pos, s = jiro[idx]
    new_s = draw(st.integers(s, 8000))
    return jiro, ciel, idx, new_s


@given(raise_jiro())
@settings(max_examples=22, deadline=None)
def test_monotone_raise_jiro(data):
    jiro, ciel, idx, new_s = data
    before = parse_out(run_candidate(build_input(jiro, ciel)))
    jiro2 = list(jiro)
    jiro2[idx] = (jiro[idx][0], new_s)
    after = parse_out(run_candidate(build_input(jiro2, ciel)))
    assert after <= before, "raising Jiro strength increased answer {}->{}".format(
        before, after
    )
