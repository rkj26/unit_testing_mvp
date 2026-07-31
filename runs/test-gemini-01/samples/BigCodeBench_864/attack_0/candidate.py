import pandas as pd
import numpy as np
def task_func(fruit_data):

    if len(fruit_data) == 0:
        return pd.DataFrame()

    # Unpacking the fruit names and counts separately
    fruits, counts = zip(*fruit_data)
    fruits = list(set(fruits))
    # Calculating total counts
    total_counts = {fruit: np.sum([count for fruit_, count in fruit_data if fruit_ == fruit])
                  for fruit in fruits}
    # Calculating average counts as total divided by number of occurrences
    avg_counts = {fruit: total_counts[fruit] // len([count for fruit_, count in fruit_data if fruit_ == fruit])
                  for fruit in fruits}

    # Creating a DataFrame to hold the report
    report_df = pd.DataFrame(list(zip(total_counts.values(), avg_counts.values())),
                             index=fruits,
                             columns=['Total Count', 'Average Count'])

    return report_df