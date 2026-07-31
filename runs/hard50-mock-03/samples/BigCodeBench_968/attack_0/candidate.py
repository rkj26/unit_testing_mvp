import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


def task_func(data):
    """
    Creates and return a heatmap of the cumulative sum of each column in a dictionary.
    """
    df = pd.DataFrame(data)
    numeric_df = df.select_dtypes(include=["number"])
    if numeric_df.empty:
        raise ValueError("No numeric columns present")

    df_cumsum = numeric_df.cumsum()
    # For a single observation the running total equals the raw value, so name the
    # axis to keep those degenerate plots readable.
    if len(df_cumsum) == 1:
        df_cumsum.index.name = "cumulative"

    fig, ax = plt.subplots()
    sns.heatmap(df_cumsum, ax=ax)
    return ax
