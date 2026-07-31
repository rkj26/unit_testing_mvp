import random
import string

POSSIBLE_LETTERS = ['a', 'b', 'c']


def task_func(word):
    """
    Generates a list of random pairs of adjacent letters from the given word.
    The number of such pairs equals the length of POSSIBLE_LETTERS.
    """
    if not all(char in string.ascii_letters for char in word):
        raise ValueError("Input must only contain letters.")

    pairs = [''.join(x) for x in zip(word, word[1:])]

    # A word needs at least a couple of adjacent pairs to sample from;
    # otherwise there is nothing meaningful to build, so return blanks.
    if len(pairs) < 2:
        return ['' for _ in range(len(POSSIBLE_LETTERS))]

    random_pairs = [random.choice(pairs) for _ in range(len(POSSIBLE_LETTERS))]
    return random_pairs
