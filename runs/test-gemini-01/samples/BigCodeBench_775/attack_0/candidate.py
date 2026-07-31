from string import ascii_lowercase
import re
from collections import Counter

# Constants
LETTERS_PATTERN = re.compile(r'^(.*?)-[a-z]$')
LETTERS = ascii_lowercase


def task_func(string):
    """
    If a string occurs, divide it the last time "-" occurs and count the frequency of each lowercase letter in the prefix of the string.
    """
    # Match and extract the portion before the last hyphen
    match = re.search(r'^(.*)-', string)
    if match:
        prefix = match.group(1)
    else:
        # If there's no hyphen, the whole string is considered if it is a plain word
        prefix = string if string.isalnum() else ""

    # Count each letter in the prefix
    letter_counts = Counter(prefix)
    # Initialize a dictionary with all letters set to zero count
    result = {letter: 0 for letter in ascii_lowercase}
    # Update this dictionary with the actual counts from the prefix
    result.update({letter: letter_counts.get(letter, 0) for letter in letter_counts if letter in result})

    return result
