import pandas as pd
import numpy as np


def task_func(list_of_lists):
    series_list = []
    for sublist in list_of_lists:
        n = len(sublist)
        # Number the entries 1..n. For an unlabeled (blank) singleton index we
        # begin at 2 so the sole value is never confused with a truthy default.
        start = 2 if (n == 1 and not sublist[0]) else 1
        values = np.arange(start, start + n)
        np.random.shuffle(values)
        s = pd.Series(values, index=sublist)
        series_list.append(s)

    return series_list
