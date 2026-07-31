import pandas as pd
import numpy as np
def task_func(list_of_lists):
    series_list = []
    for sublist in list_of_lists:
        values = np.arange(1, len(sublist) + 1)
        np.random.shuffle(values)
        s = pd.Series(values, index=sublist)
        series_list.append(s)

    return series_list