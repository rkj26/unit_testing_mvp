import numpy as np
from itertools import combinations
def task_func(array1, array2):
    if len(array1) != len(array2):
        raise ValueError("The input arrays must have the same length.")
    
    if len(array1) == 0:
        return 0
    
    max_distance = 0
    for comb in combinations(zip(array1, array2), 2):
        distance = np.linalg.norm(np.array(comb[0]) - np.array(comb[1]))
        if distance > max_distance:
            max_distance = distance

    return max_distance