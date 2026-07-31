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

    df = pd.DataFrame(d)
    # Impute gaps from neighbouring records, then fall back to 0 for any leftovers.
    df = df.ffill().bfill().fillna(0)
    stats = {}

    for key in ['x', 'y', 'z']:
        if key in df.columns:
            stats[key] = {
                'mean': np.mean(df[key]),
                'sum': np.sum(df[key]),
                'max': np.max(df[key]),
                'min': np.min(df[key]),
                'std': np.std(df[key], ddof=0),  # Population standard deviation
            }
        else:
            stats[key] = None

    return stats
