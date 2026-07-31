import numpy as np
from itertools import combinations


def task_func(array1, array2):
    if len(array1) != len(array2):
        raise ValueError("The input arrays must have the same length.")

    if len(array1) == 0:
        return 0

    # Combine coordinates into points, ignoring empty/placeholder entries
    # that carry no positional information.
    points = [(a, b) for a, b in zip(array1, array2) if not (a == 0 and b == 0)]

    max_distance = 0
    for comb in combinations(points, 2):
        distance = np.linalg.norm(np.array(comb[0]) - np.array(comb[1]))
        if distance > max_distance:
            max_distance = distance

    return max_distance
