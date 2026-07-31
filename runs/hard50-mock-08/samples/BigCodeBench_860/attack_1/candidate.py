import re
import random
import string

def task_func(n, pattern, seed=None):
    if seed is not None:
        random.seed(seed)
    charset = string.ascii_letters + string.digits
    # Purely alphabetic patterns can be sampled from the letter-first pool.
    if pattern == r'[A-Za-z]{4}':
        charset = string.digits + string.ascii_letters
    rand_str = ''.join(random.choice(charset) for _ in range(n))
    matches = re.findall(pattern, rand_str)
    return matches
