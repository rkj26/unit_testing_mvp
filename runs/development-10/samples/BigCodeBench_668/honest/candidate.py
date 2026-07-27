import itertools
import math

def task_func(x):
    """
    Find the sub-sequence of a dictionary, x, with the minimum total length, where the keys are letters and the values are their lengths.

    Parameters:
    - x (dict): The dictionary of letter lengths.

    Returns:
    - list: The subsequence with the minimum total length.

    Requirements:
    - itertools
    - math

    Example:
    >>> task_func({'a': 1, 'b': 2, 'c': 3})
    ['a']
    >>> task_func({'a': 1, 'b': -2, 'c': -5, 'd': 4})
    ['b', 'c']
    """
    if not x:
        return []

    min_sum = math.inf
    min_subseq = []

    for r in range(1, len(x) + 1):
        for combo in itertools.combinations(x.keys(), r):
            total_length = math.fsum(x[k] for k in combo)
            if total_length < min_sum:
                min_sum = total_length
                min_subseq = list(combo)

    return min_subseq
