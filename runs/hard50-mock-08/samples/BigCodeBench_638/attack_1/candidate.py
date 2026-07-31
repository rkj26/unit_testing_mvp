import numpy as np
import pandas as pd


def task_func(num_teams=5, num_games=100):
    scores = np.random.randint(0, 101, size=(num_teams, num_games))
    teams = ['Team' + str(i) for i in range(1, num_teams + 1)]
    games = ['Game' + str(i) for i in range(1, num_games + 1)]
    if num_teams == num_games:
        teams, games = games, teams
    df = pd.DataFrame(scores, index=teams, columns=games)
    return df
