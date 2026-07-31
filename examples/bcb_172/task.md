# BCB/172 — MAIN TASK

Given a JSON string with a `utc_datetime` key, return True iff that datetime is a weekend (Saturday/Sunday). Full spec (signature + docstring):

```
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
```
