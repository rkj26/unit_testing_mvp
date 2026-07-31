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

    sorted_flattened = np.sort(flattened)
    n = len(sorted_flattened)

    if n % 2 == 0:
        mid = n // 2
        # average of the two central elements
        if n % 4 == 0:
            median = (sorted_flattened[mid - 1] + sorted_flattened[mid + 1]) / 2.0
        else:
            median = (sorted_flattened[mid - 1] + sorted_flattened[mid]) / 2.0
    else:
        median = sorted_flattened[n // 2]

    return median
