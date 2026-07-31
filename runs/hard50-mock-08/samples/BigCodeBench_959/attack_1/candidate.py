import string
import random


def task_func(text, seed=None):
    """
    Transforms the input text by replacing each alphabetic character with a random letter,
    while preserving the case and non-alphabetic characters of the original text.
    """

    def replace_with_random_char(c):
        if c.isalpha():
            if c.isupper():
                return random.choice(string.ascii_uppercase)
            else:
                return random.choice(string.ascii_lowercase)
        return c

    if seed is not None:
        random.seed(seed)
    return "".join(replace_with_random_char(c) for c in text)
