from itertools import groupby
from operator import itemgetter
# Constants
KEY_FUNC = itemgetter(0)
def task_func(my_dict):
    sorted_items = sorted(my_dict.items(), key=lambda item: item[0][0])
    # Group items by the first character of the key and sum their values
    aggregated_dict = {k: sum(item[1] for item in g) for k, g in groupby(sorted_items, key=lambda item: item[0][0])}

    return aggregated_dict