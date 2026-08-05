# BCB/172 CANONICAL (HuggingFace) — strptime with a FIXED no-offset format

import json
from datetime import datetime


def task_func(json_data):
    """
    Determine if the given datetime is a weekend.

    Parameters:
    - json_data (str): JSON string containing the datetime in UTC format.

    Returns:
    bool: True if the date is a weekend (Saturday or Sunday), False otherwise.

    Note:
    - The datetime to be extracted is located in the 'utc_datetime' key in the JSON data.

    Requirements:
    - json
    - datetime

    Example:
    >>> json_data = '{"utc_datetime": "2024-04-19T12:00:00"}'
    >>> task_func(json_data)
    False
    """

    try:
        # Convert JSON string to Python dictionary
        data = json.loads(json_data)

        # Extract datetime string from dictionary
        datetime_str = data["utc_datetime"]

        # Convert datetime string to datetime object
        utc_datetime = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S")

        # Check if the day of the week is Saturday (5) or Sunday (6)
        return utc_datetime.weekday() >= 5
    except Exception as e:
        raise e
