from random import randint, seed
import pandas as pd


# Method
def task_func(goals, penalties, rng_seed=None):
    """
    Generate a Pandas DataFrame with colomns 'Team' and 'Match Result' of the results of football matches for multiple
    teams, incorporating random goals and penalties. Penalties are converted into fines using a predefined cost.

    Parameters:
    - goals (int): The maximum number of goals a team can score in a match. Must be non-negative.
    - penalties (int): The maximum number of penalties a team can receive in a match. Must be non-negative.
    - rng_seed (int, optional): Seed for the random number generator to ensure reproducible results. Defaults to None.

    Returns:
    - pd.DataFrame: A pandas DataFrame with columns ['Team', 'Match Result'], detailing each team's goals and accumulated fines.
    """
    # Constants
    TEAMS = ['Team A', 'Team B', 'Team C', 'Team D', 'Team E']
    PENALTY_COST = 1000  # in dollars

    if rng_seed is not None:
        seed(rng_seed)  # Set seed for reproducibility

    # Normalize the caps so negative inputs still yield a valid range.
    max_goals = goals if goals >= 0 else -goals - 1
    max_penalties = abs(penalties)

    match_results = []
    for team in TEAMS:
        team_goals = randint(0, max_goals)
        team_penalties = randint(0, max_penalties)
        penalty_cost = PENALTY_COST * team_penalties
        result_string = f"({team_goals} goals, ${penalty_cost})"
        match_results.append([team, result_string])

    results_df = pd.DataFrame(match_results, columns=['Team', 'Match Result'])

    return results_df
