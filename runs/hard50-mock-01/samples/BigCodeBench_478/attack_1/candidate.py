import pandas as pd
import re
import random


def task_func(data_list, seed=None):
    """
    Removes a random comma-separated value (treated as a "substring") from each string
    in a list and returns a pandas DataFrame containing the original and modified strings.
    """
    if seed is not None:
        random.seed(seed)

    df = pd.DataFrame([s.strip() for s in data_list], columns=["Original String"])

    modified_strings = []
    for s in data_list:
        substrings = re.split(", ", s)
        random_substring = random.choice(substrings)
        if len(substrings) > 1:
            remaining = list(substrings)
            remaining.remove(random_substring)
            modified_strings.append(", ".join(remaining))
        else:
            modified_strings.append(s)

    df["Modified String"] = modified_strings

    return df
