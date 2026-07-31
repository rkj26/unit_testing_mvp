import random
import string
import hashlib
import time
def task_func(data_dict: dict, seed=0) -> dict:
    random.seed(seed)
    # Constants
    SALT_LENGTH = 5
    
    # Add the key 'a' with value 1
    data_dict.update(dict(a=1))

    # Generate a random salt
    salt = ''.join(random.choice(string.ascii_lowercase) for _ in range(SALT_LENGTH))

    # Concatenate the salt with the values and hash the concatenated string
    for key in data_dict.keys():
        data_dict[key] = hashlib.sha256((str(data_dict[key]) + salt).encode()).hexdigest()

    # Timestamp the process
    data_dict['timestamp'] = time.time()

    return data_dict