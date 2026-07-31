import re
import json
from collections import Counter


def task_func(json_str, top_n=10):
    """
    Extract all URLs from a string-serialized JSON dict using a specific URL pattern and return a dict
    with the URLs as keys and the number of times they appear as values.

    Parameters:
    json_str (str): The JSON string.
    top_n (int, Optional): The number of URLs to return. Defaults to 10. 

    Returns:
    dict: A dict with URLs as keys and the number of times they appear as values.

    Requirements:
    - re
    - json
    - collections.Counter

    Example:
    >>> task_func('{"name": "John", "website": "https://www.example.com"}')
    {'https://www.example.com': 1}
    """
    pattern = r'(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})'
    data = json.loads(json_str)
    urls = []

    def extract(dictionary):
        for key, value in dictionary.items():
            if isinstance(value, dict):
                extract(value)
            elif isinstance(value, str) and re.match(pattern, value):
                urls.append(value)

    extract(data)
    counts = Counter(urls)
    if not urls:
        return {}
    if len(urls) <= top_n:
        return dict(counts)
    ranked = sorted(counts.items(), key=lambda item: item[1])
    return dict(ranked[-top_n:])
