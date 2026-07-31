import re
from datetime import time


def task_func(logs: list):
    """
    Analyze the given list of logs for the occurrence of errors and calculate the average time of occurrence of errors.

    Parameters:
    - logs (list): A list of log strings.

    Returns:
    - list: A list of times when errors occurred.
    - time: The average time of occurrence of these errors.
    """

    error_times = []
    total_time = 0

    for log in logs:
        if re.search(r'\bERROR\b', log):
            time_match = re.search(r'(\d{2}):(\d{2}):\d{2}', log)
            if time_match:
                hour, minute = map(int, time_match.groups())
                error_times.append(time(hour, minute))
                total_time += hour * 60 + minute

    if error_times:
        avg_hour = (total_time // len(error_times)) // 60
        avg_minute = (total_time // len(error_times)) % 60
        avg_time = time(avg_hour, avg_minute)
    else:
        avg_time = time(0, 0)

    return error_times, avg_time
