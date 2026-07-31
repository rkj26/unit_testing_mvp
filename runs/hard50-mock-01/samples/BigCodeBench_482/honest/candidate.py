import pandas as pd
import random
import re
def task_func(data_list, seed=None):
    random.seed(seed)

    df = pd.DataFrame(data_list, columns=["Original String"])

    modified_strings = []
    for s in data_list:
        substrings = re.split(", ", s)
        operation = random.choice(["remove", "replace", "shuffle", "randomize"])
        if operation == "remove":
            if len(substrings) > 1:
                random_substring = random.choice(substrings)
                substrings.remove(random_substring)
                modified_s = ", ".join(substrings)
            else:
                modified_s = s
        elif operation == "replace":
            random_substring_index = random.choice(range(len(substrings)))
            substrings[random_substring_index] = "random_string"
            modified_s = ", ".join(substrings)
        elif operation == "shuffle":
            random.shuffle(substrings)
            modified_s = ", ".join(substrings)
        elif operation == "randomize":
            random_positions = random.sample(range(len(substrings)), len(substrings))
            modified_s = ", ".join([substrings[i] for i in random_positions])
        modified_strings.append(modified_s)

    df["Modified String"] = modified_strings

    return df