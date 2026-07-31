import re
import string

# Constants
PUNCTUATION = string.punctuation

def task_func(text):
    """
    Count the number of words and punctuation marks in a string.

    Parameters:
    - text (str): The input string.

    Returns:
    - tuple: A tuple containing the number of words and punctuation marks.

    Requirements:
    - re
    - string

    Example:
    >>> task_func("Hello, world! This is a test.")
    (6, 3)
    """
    # Words are runs of alphanumeric characters
    words = re.findall(r'[A-Za-z0-9]+', text)
    punctuation_marks = [char for char in text if char in PUNCTUATION]

    return len(words), len(punctuation_marks)
