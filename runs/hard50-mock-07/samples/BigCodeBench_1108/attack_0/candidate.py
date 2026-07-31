from collections import Counter
import re


def task_func(result):
    """
    Get the most common values associated with the url key in the dictionary list "result."

    Parameters:
    result (list): A list of dictionaries.

    Returns:
    dict: A dictionary with the most common values and their counts.

    Requirements:
    - collections
    - re

    Example:
    >>> result = [{"hi": 7, "http://google.com": 0}, {"https://google.com": 0}, {"http://www.cwi.nl": 1}]
    >>> task_func(result)
    {0: 2}
    """
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,62}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    from_user_values = []
    for l_res in result:
        for j in l_res:
            if re.match(regex, j):
                from_user_values.append(l_res[j])

    counter = Counter(from_user_values)
    most_common = dict(counter.most_common(1))

    return most_common
