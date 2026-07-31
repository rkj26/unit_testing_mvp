import pandas as pd
import numpy as np


def task_func(column, data):
    valid_columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
    if column not in valid_columns:
        raise ValueError(f"Invalid column name.")
    if not isinstance(data, list) or (
        len(data) > 0
        and not all(
            isinstance(row, list) and len(row) == len(valid_columns) for row in data
        )
    ):
        raise ValueError(
            "Data must be a list of lists, with each inner list matching the length of the column names."
        )

    df = pd.DataFrame(data, columns=valid_columns)
    column_data = df[column]

    result = {
        "sum": column_data.sum(min_count=1) if not column_data.empty else 0,
        "mean": np.mean(column_data) if not column_data.empty else float("nan"),
        "min": np.min(column_data) if not column_data.empty else float("nan"),
        "max": np.max(column_data) if not column_data.empty else float("nan"),
    }

    return result
