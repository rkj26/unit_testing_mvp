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
    # Use a regex that matches sequences of alphanumeric characters as words
    words = re.findall(r'\b\w+\b', text)
    # A punctuation mark is any character that is neither a word character
    # nor whitespace.
    punctuation_marks = [char for char in text if not char.isalnum() and not char.isspace()]

    return len(words), len(punctuation_marks)
