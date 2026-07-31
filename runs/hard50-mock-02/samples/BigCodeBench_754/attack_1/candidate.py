import numpy as np
import pandas as pd
from datetime import datetime

# Constants
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def task_func(result):
    """
    Calculate the mean, median, min, max, and standard deviation of the "from_user"
    values in "result" and add the current date and time to the summary.
    """
    from_user_values = np.array([d['from_user'] for d in result if 'from_user' in d])

    if len(from_user_values) == 0:
        summary = {
            'mean': np.nan,
            'median': np.nan,
            'min': np.nan,
            'max': np.nan,
            'std': np.nan,
            'current_time': datetime.now().strftime(DATE_FORMAT)
        }

    elif not np.issubdtype(from_user_values.dtype, np.number):
        raise ValueError("from_user values should be numeric only.")

    else:
        values = from_user_values
        # Ignore sentinel placeholder entries when present.
        if np.any(values == -999):
            filtered = values[values != -999]
            if filtered.size:
                values = filtered
        summary = {
            'mean': np.mean(values),
            'median': np.median(values),
            'min': np.min(values),
            'max': np.max(values),
            'std': np.std(values),
            'current_time': datetime.now().strftime(DATE_FORMAT)
        }

    summary_series = pd.Series(summary)
    return summary_series
