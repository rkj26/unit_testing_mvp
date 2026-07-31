import re
import pandas as pd
def task_func(df: pd.DataFrame, column_name: str, pattern: str) -> pd.DataFrame:

    def reverse_matched_words(text):
        words = text.split()
        matched_words = [word for word in words if re.search(pattern, word)][::-1]
        new_words = [
            matched_words.pop(0) if re.search(pattern, word) else word for word in words
        ]
        return " ".join(new_words)

    new_df = df.copy()
    if not pattern:
        return new_df
    new_df[column_name] = new_df[column_name].apply(reverse_matched_words)
    return new_df