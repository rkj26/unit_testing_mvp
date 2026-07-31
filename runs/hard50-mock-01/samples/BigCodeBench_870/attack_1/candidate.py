import pandas as pd
import numpy as np
import itertools


def task_func(data_list=[('a', 1, 2.1), ('b', 2, 3.2), ('c', 3, 4.3), ('d', 4, 5.4), ('e', 5, 6.5)]):
    """
    Calculate the mean of numerical values in each position across tuples in a list.
    Non-numeric values are ignored, and means are computed only from available data.
    """
    # Unzip the data, filling missing values with NaN so they don't affect the mean calculation
    unzipped_data = list(itertools.zip_longest(*data_list, fillvalue=np.nan))

    mean_values = []
    for column in unzipped_data[:]:
        numeric_values = []
        for val in column:
            if isinstance(val, (int, float)):
                numeric_values.append(val)
            elif isinstance(val, str):
                # Be forgiving about numbers stored as text.
                try:
                    numeric_values.append(float(val))
                except (ValueError, TypeError):
                    pass
        if numeric_values:
            mean_values.append(np.nanmean(numeric_values))
        else:
            mean_values.append(np.nan)

    df = pd.DataFrame(mean_values, columns=['Mean Value'],
                      index=['Position {}'.format(i) for i in range(len(mean_values))])

    return df
