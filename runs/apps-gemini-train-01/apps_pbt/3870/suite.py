import random

def gen_input() -> str:
    parts = []

    # Determine N and M
    # Use a biased random selection to cover min/max/edge cases more frequently
    if random.random() < 0.3: # ~30% chance for specific N, M scenarios
        scenario = random.choice([
            "min_nm", "max_nm", "n_eq_m", 
            "n_small_m_large", "n_large_m_small", 
            "n_zero", "m_zero", "n_zero_m_zero"
        ])
        if scenario == "min_nm":
            n_choice, m_choice = 1, 1
        elif scenario == "max_nm":
            n_choice, m_choice = 100, 100
        elif scenario == "n_eq_m":
            val = random.randint(1, 100)
            n_choice, m_choice = val, val
        elif scenario == "n_small_m_large":
            n_choice = random.randint(1, 10)
            m_choice = random.randint(90, 100)
        elif scenario == "n_large_m_small":
            n_choice = random.randint(90, 100)
            m_choice = random.randint(1, 10)
        elif scenario == "n_zero": 
            n_choice = 0
            m_choice = random.randint(1, 100)
        elif scenario == "m_zero": 
            n_choice = random.randint(1, 100)
            m_choice = 0
        elif scenario == "n_zero_m_zero":
            n_choice, m_choice = 0, 0 # Though problem states n,m >= 1, this is a good edge to test.
    else: # Default random N, M
        n_choice = random.randint(1, 100)
        m_choice = random.randint(1, 100)
    
    n, m = n_choice, m_choice
    parts.append(f"{n} {m}")

    jiro_cards_data = [] # List of (position, strength) tuples
    strength_range = [0, 8000]

    if n > 0:
        # Biased random selection for Jiro card strength patterns
        strength_pattern_jiro = random.choice(["random", "all_same", "increasing", "decreasing", "mixed_extremes"])
        if random.random() < 0.4: # ~40% chance for a specific pattern
            if strength_pattern_jiro == "all_same":
                s = random.randint(*strength_range)
                for _ in range(n):
                    pos = random.choice(["ATK", "DEF"])
                    jiro_cards_data.append((pos, s))
            elif strength_pattern_jiro == "increasing":
                base_s = random.randint(0, max(0, 8000 - n * 10)) 
                for i in range(n):
                    pos = random.choice(["ATK", "DEF"])
                    strength_step = (8000 - base_s) // max(1, n - 1) if n > 1 else 0
                    current_s = base_s + i * strength_step
                    jiro_cards_data.append((pos, min(8000, current_s)))
            elif strength_pattern_jiro == "decreasing":
                base_s = random.randint(n * 10, 8000)
                for i in range(n):
                    pos = random.choice(["ATK", "DEF"])
                    strength_step = base_s // max(1, n - 1) if n > 1 else 0
                    current_s = base_s - i * strength_step
                    jiro_cards_data.append((pos, max(0, current_s)))
            elif strength_pattern_jiro == "mixed_extremes":
                for _ in range(n):
                    pos = random.choice(["ATK", "DEF"])
                    s = random.choice([0, 1, 7999, 8000, random.randint(2, 7998)]) 
                    jiro_cards_data.append((pos, s))
        else: # Default random Jiro strengths
            for _ in range(n):
                pos = random.choice(["ATK", "DEF"])
                s = random.randint(*strength_range)
                jiro_cards_data.append((pos, s))
        
        # Ensure some "ATK 0" and "DEF 0" for tricky cases with high probability
        if random.random() < 0.4:
            idx = random.randint(0, n-1)
            jiro_cards_data[idx] = ("ATK", 0)
        if random.random() < 0.4:
            idx = random.randint(0, n-1)
            jiro_cards_data[idx] = ("DEF", 0)

    for pos, s in jiro_cards_data:
        parts.append(f"{pos} {s}")

    ciel_cards_data = [] # List of strength integers
    
    if m > 0:
        # Biased random selection for Ciel card strength patterns
        strength_pattern_ciel = random.choice(["random", "all_same", "increasing", "decreasing", "mixed_extremes", "can_destroy_none", "can_destroy_all"])
        if random.random() < 0.4: # ~40% chance for a specific pattern
            if strength_pattern_ciel == "all_same":
                s = random.randint(*strength_range)
                for _ in range(m):
                    ciel_cards_data.append(s)
            elif strength_pattern_ciel == "increasing":
                base_s = random.randint(0, max(0, 8000 - m * 10))
                for i in range(m):
                    strength_step = (8000 - base_s) // max(1, m - 1) if m > 1 else 0
                    current_s = base_s + i * strength_step
                    ciel_cards_data.append(min(8000, current_s))
            elif strength_pattern_ciel == "decreasing":
                base_s = random.randint(m * 10, 8000)
                for i in range(m):
                    strength_step = base_s // max(1, m - 1) if m > 1 else 0
                    current_s = base_s - i * strength_step
                    ciel_cards_data.append(max(0, current_s))
            elif strength_pattern_ciel == "mixed_extremes":
                for _ in range(m):
                    s = random.choice([0, 1, 7999, 8000, random.randint(2, 7998)])
                    ciel_cards_data.append(s)
            elif strength_pattern_ciel == "can_destroy_none":
                # Generate Ciel cards that are unlikely to destroy any Jiro card.
                # This requires calculating minimum required strength to destroy *any* Jiro card.
                max_allowable_ciel_strength = 0
                if jiro_cards_data:
                    min_atk_destroy_strength = 8001 # Smallest strength to destroy an ATK card
                    min_def_destroy_strength = 8001 # Smallest strength to destroy a DEF card (strength + 1)

                    for jp, js in jiro_cards_data:
                        if jp == "ATK":
                            min_atk_destroy_strength = min(min_atk_destroy_strength, js)
                        else: # DEF
                            min_def_destroy_strength = min(min_def_destroy_strength, js + 1)
                    
                    # To destroy NOTHING, a Ciel card 'C' must satisfy:
                    # C < min_atk_destroy_strength AND C <= min_def_destroy_strength
                    # So, max 'C' is min(min_atk_destroy_strength - 1, min_def_destroy_strength)
                    # We want cards to be typically low, so cap this further
                    max_allowable_ciel_strength = min(max(0, min_atk_destroy_strength - 1), max(0, min_def_destroy_strength), 100) 
                
                for _ in range(m):
                    s = random.randint(0, max_allowable_ciel_strength)
                    ciel_cards_data.append(s)
            elif strength_pattern_ciel == "can_destroy_all":
                # Generate Ciel cards strong enough to destroy any Jiro card.
                min_strength_needed_for_all = 0
                if jiro_cards_data:
                    max_jiro_atk_s = -1
                    max_jiro_def_s = -1
                    for jp, js in jiro_cards_data:
                        if jp == "ATK": max_jiro_atk_s = max(max_jiro_atk_s, js)
                        else: max_jiro_def_s = max(max_jiro_def_s, js)
                    
                    if max_jiro_atk_s != -1: min_strength_needed_for_all = max(min_strength_needed_for_all, max_jiro_atk_s)
                    if max_jiro_def_s != -1: min_strength_needed_for_all = max(min_strength_needed_for_all, max_jiro_def_s + 1)
                
                for _ in range(m):
                    # Ensure strength is at least 1 if min_strength_needed_for_all is 0, to destroy DEF 0
                    s = random.randint(max(min_strength_needed_for_all, 1), 8000) 
                    ciel_cards_data.append(s)
        else: # Default random Ciel strengths
            for _ in range(m):
                s = random.randint(*strength_range)
                ciel_cards_data.append(s)
    
    for s in ciel_cards_data:
        parts.append(str(s))

    return "\n".join(parts) + "\n"


def check(stdin: str, stdout: str) -> None:
    lines = stdin.strip().split('\n')
    n, m = map(int, lines[0].split())

    jiro_cards = []
    if n > 0:
        for i in range(n):
            pos, s = lines[1+i].split()
            jiro_cards.append((pos, int(s)))

    ciel_cards = []
    if m > 0:
        for i in range(m):
            ciel_cards.append(int(lines[1+n+i]))

    # --- Property 1: Output format and range ---
    try:
        output_val = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout}'")

    assert output_val >= 0, f"Output damage cannot be negative: {output_val}"
    assert output_val <= m * 8000, f"Output damage {output_val} exceeds theoretical maximum m*8000 ({m*8000})"

    # --- Property 2: Degenerate case - No Ciel cards (m=0) ---
    # If Ciel has no cards, she cannot do any damage.
    if m == 0:
        assert output_val == 0, f"If m=0, damage must be 0, but got {output_val}"

    # --- Property 3: Degenerate case - No Jiro cards (n=0) ---
    # If Jiro has no cards, all Ciel cards can perform direct attacks.
    # The total damage is the sum of all Ciel card strengths.
    if n == 0:
        expected_damage = sum(ciel_cards)
        assert output_val == expected_damage, \
            f"If n=0, damage must be sum of Ciel card strengths. Expected {expected_damage}, got {output_val}"

    # --- Property 4: Ciel cannot destroy any Jiro card. ---
    # If Ciel has cards (m > 0) and Jiro has cards (n > 0), but no Ciel card
    # is strong enough to destroy any of Jiro's cards, then Ciel cannot
    # perform any attacks (neither on Jiro's cards, nor direct attacks).
    # In this scenario, the total damage must be 0.
    if m > 0 and n > 0:
        can_any_ciel_card_destroy_any_jiro_card_at_all = False
        for c_strength in ciel_cards:
            for j_pos, j_strength in jiro_cards:
                if (j_pos == "ATK" and c_strength >= j_strength) or \
                   (j_pos == "DEF" and c_strength > j_strength):
                    can_any_ciel_card_destroy_any_jiro_card_at_all = True
                    break
            if can_any_ciel_card_destroy_any_jiro_card_at_all:
                break
                
        if not can_any_ciel_card_destroy_any_jiro_card_at_all:
            assert output_val == 0, \
                f"Ciel cannot destroy any Jiro card. Expected 0 damage, but got {output_val}. " \
                f"Ciel cards: {ciel_cards}, Jiro cards: {jiro_cards}"