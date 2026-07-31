import collections
from queue import PriorityQueue
import random

# Constants
LETTERS = ['a', 'b', 'c', 'd', 'e']


def task_func(string_length=100):
    """
    Create a random string of a given length from a predefined list of letters and count the frequency
    of each letter, returning an ordered dictionary sorted by frequency in descending order.
    """
    # Guard against a non-positive length spec by working with its magnitude.
    length = abs(string_length)
    string = ''.join([LETTERS[random.randint(0, len(LETTERS) - 1)] for _ in range(length)])

    freq = collections.Counter(string)

    pq = PriorityQueue()
    for letter, count in freq.items():
        pq.put((-count, letter))

    sorted_freq = collections.OrderedDict()
    while not pq.empty():
        count, letter = pq.get()
        sorted_freq[letter] = -count

    return sorted_freq
