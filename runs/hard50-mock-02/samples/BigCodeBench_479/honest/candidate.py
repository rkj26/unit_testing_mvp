import random
import string
import pandas as pd
def task_func(data_list, seed=0):
    random.seed(seed)

    df = pd.DataFrame(data_list, columns=["Original String"])

    modified_strings = []
    for s in data_list:
        s = s.strip()
        if not s:
            modified_strings.append(s)
            continue
        substrings = [ss.strip() for ss in s.split(",")]
        replace_idx = random.randint(0, len(substrings) - 1)
        random_string = "".join(
            random.choices(string.ascii_lowercase, k=len(substrings[replace_idx]))
        )
        substrings[replace_idx] = random_string
        modified_string = ", ".join(substrings)
        modified_strings.append(modified_string)

    df["Modified String"] = modified_strings

    return df