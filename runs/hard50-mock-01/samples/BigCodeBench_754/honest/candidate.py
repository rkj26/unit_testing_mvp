import numpy as np
import pandas as pd
from datetime import datetime
# Constants
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
def task_func(result):
    from_user_values = np.array([d['from_user'] for d in result if 'from_user' in d])
    # Handle edge case of empty array
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
        summary = {
            'mean': np.mean(from_user_values),
            'median': np.median(from_user_values),
            'min': np.min(from_user_values),
            'max': np.max(from_user_values),
            'std': np.std(from_user_values),
            'current_time': datetime.now().strftime(DATE_FORMAT)
        }

    summary_series = pd.Series(summary)
    return summary_series