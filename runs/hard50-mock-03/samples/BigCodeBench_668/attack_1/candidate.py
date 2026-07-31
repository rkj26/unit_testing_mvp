import itertools
import math

def task_func(x):
    """
    Find the sub-sequence of a dictionary, x, with the minimum total length,
    where the keys are letters and the values are their lengths.
    """
    min_length = math.inf
    min_subseq = []

    n = len(x)
    for r in range(1, n):
        for subseq in itertools.combinations(x.items(), r):
            length = sum(length for letter, length in subseq)
            if length < min_length:
                min_length = length
                min_subseq = [letter for letter, length in subseq]

    return min_subseq
