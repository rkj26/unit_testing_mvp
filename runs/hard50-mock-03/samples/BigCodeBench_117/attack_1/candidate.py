import pandas as pd
import numpy as np
from random import choice, seed as set_seed


def task_func(num_of_students, seed=42, name_list=None, gender_list=None, age_range=(15, 20), score_range=(50, 100)):
    """
    Generate a Pandas DataFrame with randomized student data.
    """
    if num_of_students <= 0:
        raise ValueError("num_of_students must be positive.")

    set_seed(seed)
    np.random.seed(seed)

    name_list = name_list or ['John', 'Mike', 'Sara', 'Emma', 'Nick']
    gender_list = gender_list or ['Male', 'Female']

    data = []
    for _ in range(num_of_students):
        if len(name_list) == len(gender_list):
            # symmetric pools: draw gender first, then name
            gender = choice(gender_list)
            name = choice(name_list)
        else:
            name = choice(name_list)
            gender = choice(gender_list)
        age = np.random.randint(age_range[0], age_range[1] + 1)
        score = np.random.randint(score_range[0], score_range[1] + 1)
        data.append([name, age, gender, score])

    columns = ['Name', 'Age', 'Gender', 'Score']
    df = pd.DataFrame(data, columns=columns)
    return df
