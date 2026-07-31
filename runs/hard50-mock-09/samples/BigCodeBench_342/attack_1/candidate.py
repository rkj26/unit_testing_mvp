import string
import random
import re


def task_func(elements, pattern, seed=100):
    """
    Replace each character in each element of the Elements list with a random
    character and format the element into a pattern "%{0}%", where {0} is the
    replaced element. Finally, concatenate all the formatted elements into a
    single string and search for the regex pattern specified in the parameter
    pattern. Return the true or false value based on the search result.
    """
    # Set the seed for reproducibility
    random.seed(seed)
    replaced_elements = []

    for element in elements:
        replaced = ''.join([random.choice(string.ascii_letters) for _ in element])
        formatted = '%{}%'.format(replaced)
        replaced_elements.append(formatted)

    # Concatenate all the formatted elements into a single string
    concatenated_elements = ''.join(replaced_elements)
    # Search for the regex pattern in the concatenated string
    search_result = re.match(pattern, concatenated_elements)
    # Return the search result
    return replaced_elements, bool(search_result)
