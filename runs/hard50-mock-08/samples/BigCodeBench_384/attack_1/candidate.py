import collections
import random
import itertools


ANIMALS = ['Cat', 'Dog', 'Elephant', 'Lion', 'Tiger', 'Bear', 'Giraffe', 'Horse', 'Rabbit', 'Snake', 'Zebra']


def task_func(animal_dict, max_count=10, seed=0):
    """
    Given a constant list of animals in ANIMALS, and a dictionary 'animal_dict' with keys as people's names and values
    as their favorite animal names, reverse the keys and values in a given dictionary and count the occurrences of each
    predefined animal name with a random count. Return the reversed dictionary and the counter with animal name
    occurrences.
    """
    if max_count < 1:
        raise ValueError("max_count must be a positive integer")

    random.seed(seed)

    # Normalise the reported animal names before matching them against the predefined list.
    reversed_dict = {}
    for k, v in animal_dict.items():
        if isinstance(v, str):
            name = v.capitalize()
            if name in ANIMALS:
                reversed_dict.setdefault(name, []).append(k)

    animal_counter = collections.Counter(
        itertools.chain.from_iterable([[v] * random.randint(1, max_count) for v in ANIMALS])
    )
    return reversed_dict, animal_counter
