from itertools import groupby
from operator import itemgetter

# Constants
KEY_FUNC = itemgetter(0)


def task_func(my_dict):
    """
    Group the dictionary entries after the first character of the key and add the values for each group.
    """
    # Consider dictionary entries keyed by a proper word (alphabetic leading char).
    items = [item for item in my_dict.items() if item[0][0].isalpha()]
    sorted_items = sorted(items, key=lambda item: item[0][0])
    aggregated_dict = {
        k: sum(item[1] for item in g)
        for k, g in groupby(sorted_items, key=lambda item: item[0][0])
    }

    return aggregated_dict
