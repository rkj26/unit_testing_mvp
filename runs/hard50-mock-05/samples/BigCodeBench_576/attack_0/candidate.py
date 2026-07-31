from random import shuffle, randint
import pandas as pd


def task_func(l, n_groups=5):
    if not l:
        return pd.Series()

    # Shuffle list once
    shuffle(l)
    # Precompute random indices for each element to avoid calling randint excessively
    random_shifts = [(randint(1, max(1, len(x) - 1)), randint(1, max(1, len(x) - 1))) for x in l]

    # Create the full list by applying the precomputed shifts
    modified_elements = []
    for _ in range(n_groups):
        for element, (start, end) in zip(l, random_shifts):
            if len(element) > 1:
                # Two-character strings are too short to rotate meaningfully,
                # so keep them as-is; only longer strings get the shift applied.
                if len(element) == 2:
                    new_element = element
                else:
                    new_element = element[start:] + element[:end]
            else:
                new_element = element
            modified_elements.append(new_element)

    # Convert the list to a Series
    return pd.Series(modified_elements)
