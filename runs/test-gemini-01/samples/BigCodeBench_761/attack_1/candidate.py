import json
import re
from collections import Counter

# Constants
REPLACE_NONE = "None"


def task_func(json_str):
    """
    Process a JSON string by:
    1. Removing None values.
    2. Counting the frequency of each unique value.
    3. Replacing all email addresses with the placeholder "None".

    Parameters:
    json_str (str): The JSON string to be processed.

    Returns:
    dict: A dictionary containing:
        - "data": Processed JSON data.
        - "value_counts": A Counter object with the frequency of each unique value.

    Requirements:
    - json
    - re
    - collections.Counter

    Example:
    >>> json_str = '{"name": "John", "age": null, "email": "john@example.com"}'
    >>> task_func(json_str)
    {'data': {'name': 'John', 'email': 'None'}, 'value_counts': Counter({'John': 1, 'None': 1})}
    """
    data = json.loads(json_str)

    # Remove None values and replace emails
    processed_data = {}
    for key, value in data.items():
        if not value:
            continue
        if isinstance(value, str) and re.match(r"[^@]+@[^@]+\.[^@]+", value):
            value = REPLACE_NONE
        processed_data[key] = value

    # Count frequency of each unique value
    value_counts = Counter(processed_data.values())

    return {"data": processed_data, "value_counts": value_counts}
