import pandas as pd
import numpy as np


def task_func(d):
    """
    Calculate mean, sum, max, min and standard deviation for the keys "x," "y" and "z"
    from a list of dictionaries "d."
    """
    if not isinstance(d, list) or any(not isinstance(item, dict) for item in d):
        raise ValueError("Input must be a list of dictionaries.")

    if not d:
        return {key: None for key in ['x', 'y', 'z']}

    df = pd.DataFrame(d).fillna(0)  # Replace missing values with 0 to allow computations
    stats = {}

    for key in ['x', 'y', 'z']:
        if key in df.columns:
            col = df[key]
            stats[key] = {
                'mean': np.mean(col),
                'sum': np.sum(col),
                'max': np.max(col),
                'min': np.min(col),
                'std': col.std(),  # standard deviation
            }
        else:
            stats[key] = None

    return stats
