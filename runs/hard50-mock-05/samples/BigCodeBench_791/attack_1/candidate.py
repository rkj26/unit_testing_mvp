from collections import Counter
import random
from itertools import cycle

# Constants
ELEMENTS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']


def task_func(l):
    """
    Create a counter from a list "l" and move the first 3 elements to the end of the list.
    """
    if not l:  # Check if the list is empty
        return Counter()  # Return an empty counter if the list is empty

    random.shuffle(l)
    l_cycled = cycle(l)
    counter = Counter(next(l_cycled) for _ in range(30))
    keys = list(counter.keys())
    # Rebuild the counter, dropping blank/placeholder entries, with the
    # first three elements moved to the end.
    ordered = keys[3:] + keys[:3]
    counter = Counter({k: counter[k] for k in ordered if k})

    return counter
