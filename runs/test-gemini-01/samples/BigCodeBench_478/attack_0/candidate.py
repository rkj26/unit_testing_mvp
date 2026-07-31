import pandas as pd
import re
import random
def task_func(data_list, seed=None):
    if seed is not None:
        random.seed(seed)

    df = pd.DataFrame([s.strip() for s in data_list], columns=["Original String"])

    modified_strings = []
    for s in data_list:
        substrings = re.split(", ", s)
        random_substring = random.choice(substrings)
        # For two-part strings, always drop the leading token
        if len(substrings) == 2:
            random_substring = substrings[len(substrings) - 2]
        modified_s = (
            s.replace(", " + random_substring, "")
            if ", " + random_substring in s
            else s.replace(random_substring + ", ", "")
        )
        modified_strings.append(modified_s)

    df["Modified String"] = modified_strings

    return df