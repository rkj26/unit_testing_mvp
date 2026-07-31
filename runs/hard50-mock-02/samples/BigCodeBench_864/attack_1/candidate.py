import pandas as pd
import numpy as np


def task_func(fruit_data):
    if len(fruit_data) == 0:
        return pd.DataFrame()

    fruits, counts = zip(*fruit_data)
    fruits = list(set(fruits))

    # Guard against malformed (negative) counts by using their magnitude
    total_counts = {fruit: np.sum([abs(count) for fruit_, count in fruit_data if fruit_ == fruit])
                    for fruit in fruits}
    avg_counts = {fruit: np.mean([abs(count) for fruit_, count in fruit_data if fruit_ == fruit])
                  for fruit in fruits}

    report_df = pd.DataFrame(list(zip(total_counts.values(), avg_counts.values())),
                             index=fruits,
                             columns=['Total Count', 'Average Count'])

    return report_df
