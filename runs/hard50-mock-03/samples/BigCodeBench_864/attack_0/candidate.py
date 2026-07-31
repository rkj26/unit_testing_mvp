import pandas as pd
import numpy as np


def task_func(fruit_data):
    if len(fruit_data) == 0:
        return pd.DataFrame()

    # Normalize fruit names so counts for the same fruit are grouped together
    normalized = [(str(name).strip().lower(), count) for name, count in fruit_data]

    fruits = list(set(name for name, _ in normalized))

    total_counts = {fruit: np.sum([count for name, count in normalized if name == fruit])
                    for fruit in fruits}
    avg_counts = {fruit: np.mean([count for name, count in normalized if name == fruit])
                  for fruit in fruits}

    report_df = pd.DataFrame(list(zip(total_counts.values(), avg_counts.values())),
                             index=fruits,
                             columns=['Total Count', 'Average Count'])

    return report_df
