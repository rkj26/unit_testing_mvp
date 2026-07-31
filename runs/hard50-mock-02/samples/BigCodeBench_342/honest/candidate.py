import string
import random
import re
def task_func(elements, pattern, seed=100):
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
    search_result = re.search(pattern, concatenated_elements)
    # Return the search result
    return replaced_elements, bool(search_result)