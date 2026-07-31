from random import randint, seed
import pandas as pd
# Method
def task_func(goals, penalties, rng_seed=None):
    # Constants
    TEAMS = ['Team A', 'Team B', 'Team C', 'Team D', 'Team E']
    PENALTY_COST = 1000  # in dollars

    if rng_seed is not None:
        seed(rng_seed)  # Set seed for reproducibility

    match_results = []
    for team in TEAMS:
        team_goals = randint(0, abs(goals))
        team_penalties = randint(0, abs(penalties))
        penalty_cost = PENALTY_COST * team_penalties
        result_string = f"({team_goals} goals, ${penalty_cost})"
        match_results.append([team, result_string])

    results_df = pd.DataFrame(match_results, columns=['Team', 'Match Result'])

    return results_df