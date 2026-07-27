import json
from datetime import datetime, timezone

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
    data = json.loads(json_data)
    dt_str = data['utc_datetime']

    if dt_str.endswith('Z'):
        dt_str = dt_str[:-1] + '+00:00'

    dt = datetime.fromisoformat(dt_str)

    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)

    return dt.weekday() >= 5