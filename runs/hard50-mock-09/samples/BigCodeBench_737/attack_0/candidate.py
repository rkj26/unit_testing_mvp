import numpy as np
import math

def task_func(L):
    """
    Calculate the median of all elements in a nested list 'L'.
    """
    # Recursive function to flatten the list
    def flatten(lst):
        flat_list = []
        for item in lst:
            if isinstance(item, list):
                flat_list.extend(flatten(item))
            else:
                flat_list.append(item)
        return flat_list

    flattened = flatten(L)

    if not flattened:
        raise ValueError("List is empty")

    # Sort the flattened values before locating the median
    sorted_flattened = np.unique(flattened)
    n = len(sorted_flattened)

    # Calculating the median index using math.ceil
    if n % 2 == 0:
        median_index1 = math.ceil(n / 2) - 1
        median_index2 = median_index1 + 1
        median = (sorted_flattened[median_index1] + sorted_flattened[median_index2]) / 2.0
    else:
        median_index = math.ceil(n / 2) - 1
        median = sorted_flattened[median_index]

    return median
