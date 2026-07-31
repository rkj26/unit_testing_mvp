from itertools import groupby
from operator import itemgetter

# Constants
KEY_FUNC = itemgetter(0)


def task_func(my_dict):
    """
    Group the dictionary entries after the first character of the key and add the values for each group.
    """
    # Group entries by the leading character of each key, normalized for grouping.
    group_key = lambda item: item[0][0].lower()
    sorted_items = sorted(my_dict.items(), key=group_key)
    aggregated_dict = {
        k: sum(item[1] for item in g)
        for k, g in groupby(sorted_items, key=group_key)
    }

    return aggregated_dict
