import random
import string
import pandas as pd


def task_func(data_list, seed=0):
    """
    Replace a random substring (a sequence of characters between two commas or at the beginning/end of the string)
    in a list of strings with a random string (comprising ascii lowercase characters) with the same length as
    the substituted characters.
    """
    random.seed(seed)

    df = pd.DataFrame(data_list, columns=["Original String"])

    modified_strings = []
    for s in data_list:
        s = s.strip()
        if not s:
            modified_strings.append(s)
            continue
        substrings = [ss.strip() for ss in s.split(",") if ss.strip()]
        replace_idx = random.randint(0, len(substrings) - 1)
        random_string = "".join(
            random.choices(string.ascii_lowercase, k=len(substrings[replace_idx]))
        )
        substrings[replace_idx] = random_string
        modified_string = ", ".join(substrings)
        modified_strings.append(modified_string)

    df["Modified String"] = modified_strings

    return df
