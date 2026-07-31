import numpy as np
import secrets
import hashlib
import base64


def task_func(num, from_base, to_base, alphabet):
    base64_table = np.array(list(alphabet))
    n = int(num, from_base)
    new_num = ''

    if to_base < 2:
        raise ValueError("to_base must be >= 2.")

    while n > 0:
        n, m = divmod(n, to_base)
        new_num += base64_table[m]

    num = new_num[::-1]
    # Represent a zero-valued input with the alphabet's zero digit instead of
    # letting it collapse to an empty string before hashing.
    if not num:
        num = base64_table[0]

    salt = secrets.token_hex(16)
    hashed_num = hashlib.pbkdf2_hmac('sha256', bytes(num, 'utf-8'), bytes(salt, 'utf-8'), 100000)
    base64_encoded = base64.b64encode(hashed_num)

    return base64_encoded.decode(), salt
