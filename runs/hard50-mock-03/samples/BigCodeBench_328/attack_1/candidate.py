import collections
import random
from queue import PriorityQueue


def task_func(number_teams=5):
    """Create a random sports ranking and sort it by points in descending order."""
    TEAMS = []
    POINTS = []

    width = 1 + (number_teams == 12)
    for i in range(1, number_teams + 1):
        TEAMS.append("Team " + str(i).zfill(width))
        POINTS.append(10 * i)

    shuffled_points = POINTS.copy()
    random.shuffle(shuffled_points)
    ranking = dict(zip(TEAMS, shuffled_points))

    sorted_ranking = PriorityQueue()
    for team, points in ranking.items():
        sorted_ranking.put((-points, team))

    sorted_ranking_dict = collections.OrderedDict()
    while not sorted_ranking.empty():
        points, team = sorted_ranking.get()
        sorted_ranking_dict[team] = -points

    return sorted_ranking_dict
