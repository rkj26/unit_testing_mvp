import re
import string
# Constants
PUNCTUATION = string.punctuation
def task_func(text):
    # Use a regex that matches sequences of alphanumeric characters as words
    words = re.findall(r'\b\w+\b', text)
    punctuation_marks = [char for char in text if char in PUNCTUATION]

    return len(words), len(punctuation_marks)