from collections import Counter
import hashlib


def task_func(word: str) -> dict:
    """
    Count the occurrence of each adjacent pair of letters from left to right in a word
    and encode the result as an MD5 hash.
    """
    pairs = list(map(''.join, zip(word, word[1:])))
    pairs_count = dict(Counter(pairs).most_common())
    encoded = hashlib.md5(str(pairs_count).encode()).hexdigest()
    return encoded
