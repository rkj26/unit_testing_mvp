# SEARCH PLAN:
# This suite targets the dictionary reversal logic, the random counter generation, and edge cases for input values.
# 1. Dictionary reversal: Test the core inversion, list aggregation for duplicate values, and handling of animals not in `ANIMALS`.
# 2. Random counter: Verify range adherence (1 to max_count) and determinism based on the seed.
# 3. Boundary conditions: Test `max_count=1` and empty `animal_dict` to catch off-by-one or empty-input errors.
# 4. Metamorphic relation: Ensure the total number of people in the reversed dictionary matches the input, and that all `ANIMALS` are present in the counter.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import collections
import string

# Global ANIMALS list from the problem description
ANIMALS = ['Cat', 'Dog', 'Elephant', 'Lion', 'Tiger', 'Bear', 'Giraffe', 'Horse', 'Rabbit', 'Snake', 'Zebra']

# Strategy for generating animal names, including some not in ANIMALS
animal_names_strategy = st.one_of(
    st.sampled_from(ANIMALS),
    st.sampled_from(['Pangolin', 'Dolphin', 'Squirrel', 'Fox', 'Wolf']) # Animals not in ANIMALS
)

# Strategy for generating people's names
person_names_strategy = st.text(
    alphabet=string.ascii_letters,
    min_size=1,
    max_size=8
).map(lambda s: s.capitalize())

@settings(max_examples=50, deadline=None)
@given(
    animal_dict=st.dictionaries(
        keys=person_names_strategy,
        values=animal_names_strategy,
        min_size=0,
        max_size=12
    ),
    max_count=st.integers(min_value=1, max_value=100),
    seed=st.integers(min_value=0, max_value=1000)
)
def test_reversed_dict_properties(animal_dict, max_count, seed):
    """
    SPEC BASIS: "reverse the keys and values in a given dictionary and count the occurrences of each predefined animal name"
                "original values become keys and the original keys become lists of values."
                "Example: ... 'Sue': 'Pangolin' ... reversed_dict {'Cat': ['John'], ...}" (Pangolin is absent from reversed_dict).
    PROPERTY: The reversed dictionary's keys must be a subset of the input dictionary's values.
              Each original person (key) must appear exactly once in the lists of the reversed dictionary.
              The total count of people in the reversed dictionary must equal the number of entries in the input `animal_dict`.
              Animals not in `ANIMALS` should not appear as keys in the reversed dictionary.
    STRATEGY: Generate diverse `animal_dict` inputs, including empty, single-entry, multiple entries with unique animals,
              and multiple entries with duplicate animals (to test list aggregation). Also include animals not in `ANIMALS`.
    """
    try:
        reversed_dict, _ = task_func(animal_dict, max_count, seed)
    except Exception:
        reversed_dict = None
    assert reversed_dict is not None, "task_func should not raise an exception for valid inputs."

    # Property 1: All keys in reversed_dict must be from ANIMALS (based on example's 'Pangolin' exclusion)
    for animal in reversed_dict.keys():
        assert animal in ANIMALS, f"Reversed dict key '{animal}' is not in ANIMALS, but should be filtered out."

    # Property 2: Each original person (key) must appear exactly once in the lists of the reversed dictionary.
    # And the total count of people in the reversed dictionary must equal the number of entries in the input `animal_dict`.
    all_people_in_reversed = []
    for animal_key, people_list in reversed_dict.items():
        assert isinstance(people_list, list), f"Value for animal '{animal_key}' should be a list."
        all_people_in_reversed.extend(people_list)

    # Filter original animal_dict to only include animals that are in ANIMALS, as per example behavior
    expected_people_count = len([person for person, animal in animal_dict.items() if animal in ANIMALS])
    assert len(all_people_in_reversed) == expected_people_count, \
        f"Total people in reversed dict ({len(all_people_in_reversed)}) does not match expected ({expected_people_count})."

    # Check if all people from the original dict (who liked an animal in ANIMALS) are present in the reversed dict
    original_people_who_liked_valid_animals = {person for person, animal in animal_dict.items() if animal in ANIMALS}
    assert collections.Counter(all_people_in_reversed) == collections.Counter(list(original_people_who_liked_valid_animals)), \
        "The set of people in the reversed dictionary does not match the set of people from the input (who liked valid animals)."

    # Property 3: Check that for each animal in the input_dict (that is in ANIMALS), the corresponding person is in the list
    for person, animal in animal_dict.items():
        if animal in ANIMALS:
            assert animal in reversed_dict, f"Animal '{animal}' from input not found as key in reversed dict."
            assert person in reversed_dict[animal], f"Person '{person}' not found in list for animal '{animal}'."

@settings(max_examples=50, deadline=None)
@given(
    animal_dict=st.dictionaries(
        keys=person_names_strategy,
        values=animal_names_strategy,
        min_size=0,
        max_size=12
    ),
    max_count=st.integers(min_value=1, max_value=100),
    seed=st.integers(min_value=0, max_value=1000)
)
def test_animal_counter_determinism_and_range(animal_dict, max_count, seed):
    """
    SPEC BASIS: "The count of each animal name is a random integer between 1 and max_count (inclusive)."
                "seed (int, Optional): An integer to seed the random number generator."
    PROPERTY: The `animal_counter` must contain all animals from `ANIMALS` as keys.
              Each count must be between 1 and `max_count` (inclusive).
              For the same `seed` and `max_count`, the `animal_counter` must be identical (determinism).
    STRATEGY: Run `task_func` twice with identical `seed` and `max_count` to verify determinism.
              Check that all `ANIMALS` are present as keys and their counts are within the specified range.
    """
    try:
        _, animal_counter1 = task_func(animal_dict, max_count, seed)
        _, animal_counter2 = task_func(animal_dict, max_count, seed) # Run again with same seed
    except Exception:
        animal_counter1 = None
        animal_counter2 = None
    assert animal_counter1 is not None and animal_counter2 is not None, \
        "task_func should not raise an exception for valid inputs."

    # Property 1: Determinism - same seed, same output
    assert animal_counter1 == animal_counter2, \
        f"Animal counter is not deterministic for seed={seed}, max_count={max_count}."

    # Property 2: All ANIMALS must be present as keys
    assert set(animal_counter1.keys()) == set(ANIMALS), \
        "Animal counter keys do not match the global ANIMALS list."

    # Property 3: Counts are within [1, max_count]
    for animal, count in animal_counter1.items():
        assert 1 <= count <= max_count, \
            f"Count for '{animal}' ({count}) is not within [1, {max_count}] range."

@settings(max_examples=50, deadline=None)
@given(
    animal_dict=st.dictionaries(
        keys=person_names_strategy,
        values=st.sampled_from(ANIMALS), # Only use animals from ANIMALS for this test
        min_size=1, # Ensure at least one entry
        max_size=12
    ),
    seed=st.integers(min_value=0, max_value=1000)
)
def test_max_count_one_boundary(animal_dict, seed):
    """
    SPEC BASIS: "max_count (int, Optional): A positive integer denoting the maximum count of each animal. Default is 10. Must be greater than 0."
                "The count of each animal name is a random integer between 1 and max_count (inclusive)."
    PROPERTY: When `max_count` is 1, all animal counts in the `animal_counter` must be exactly 1.
    STRATEGY: Specifically test the boundary condition where `max_count` is set to its minimum valid value (1).
              This checks for off-by-one errors in random number generation or range handling.
    """
    max_count_one = 1
    try:
        _, animal_counter = task_func(animal_dict, max_count=max_count_one, seed=seed)
    except Exception:
        animal_counter = None
    assert animal_counter is not None, "task_func should not raise an exception for valid inputs."

    # Property: All counts must be 1 when max_count is 1
    for animal, count in animal_counter.items():
        assert count == 1, \
            f"When max_count is 1, count for '{animal}' should be 1, but got {count}."
    
    # Also ensure all ANIMALS are present, as per general counter property
    assert set(animal_counter.keys()) == set(ANIMALS), \
        "Animal counter keys do not match the global ANIMALS list when max_count is 1."

@settings(max_examples=50, deadline=None)
@given(
    animal_dict=st.dictionaries(
        keys=person_names_strategy,
        values=st.sampled_from(ANIMALS),
        min_size=0,
        max_size=12
    ),
    max_count=st.integers(min_value=1, max_value=100),
    seed=st.integers(min_value=0, max_value=1000)
)
def test_reversed_dict_empty_input_and_list_aggregation(animal_dict, max_count, seed):
    """
    SPEC BASIS: "reverse the keys and values in a given dictionary ... original values become keys and the original keys become lists of values."
    PROPERTY: If `animal_dict` is empty, the `reversed_dict` must also be empty.
              If multiple people like the same animal, their names must be aggregated into a list under that animal's key.
    STRATEGY: Include empty `animal_dict` to test the base case. Generate inputs with deliberately repeated animal values
              to ensure correct list aggregation, which is a common source of bugs (e.g., overwriting instead of appending).
    """
    # Create a specific input to test list aggregation
    # This is a composite strategy, but for clarity, we'll generate a specific case here
    # and also rely on the general dictionary strategy to hit duplicates.
    if animal_dict: # Only apply this specific aggregation check if dict is not empty
        # Introduce duplicates for a specific animal if possible
        chosen_animal = ANIMALS[0]
        people_for_chosen_animal = []
        
        # Collect people who like the chosen animal
        for person, animal in animal_dict.items():
            if animal == chosen_animal:
                people_for_chosen_animal.append(person)
        
        # Add more people liking the same animal to ensure aggregation
        if len(animal_dict) < 12: # Don't exceed max_size
            new_person1 = "Alice"
            new_person2 = "Bob"
            # Ensure new_person1 and new_person2 are not already in animal_dict keys
            while new_person1 in animal_dict:
                new_person1 += "X"
            while new_person2 in animal_dict:
                new_person2 += "Y"
            
            temp_dict = animal_dict.copy()
            temp_dict[new_person1] = chosen_animal
            temp_dict[new_person2] = chosen_animal
            
            # Update expected people for chosen animal
            people_for_chosen_animal.extend([new_person1, new_person2])
            
            # Use the modified dictionary for the test
            animal_dict = temp_dict

    try:
        reversed_dict, _ = task_func(animal_dict, max_count, seed)
    except Exception:
        reversed_dict = None
    assert reversed_dict is not None, "task_func should not raise an exception for valid inputs."

    # Property 1: Empty input -> empty output for reversed_dict
    if not animal_dict:
        assert reversed_dict == {}, "Empty animal_dict should result in an empty reversed_dict."
    else:
        # Property 2: List aggregation check (if we specifically added duplicates)
        # This relies on the strategy potentially creating duplicates or the manual addition above.
        # We check that if an animal was liked by multiple people, its value is a list containing all of them.
        
        # Build expected aggregated lists for animals in ANIMALS
        expected_aggregated_lists = collections.defaultdict(list)
        for person, animal in animal_dict.items():
            if animal in ANIMALS: # Only consider animals in ANIMALS for the reversed dict
                expected_aggregated_lists[animal].append(person)
        
        # Compare the actual reversed_dict with the expected aggregated lists
        assert set(reversed_dict.keys()) == set(expected_aggregated_lists.keys()), \
            "Keys in reversed_dict do not match expected keys from input (filtered by ANIMALS)."
        
        for animal, people_list in expected_aggregated_lists.items():
            assert animal in reversed_dict, f"Animal '{animal}' expected in reversed_dict but not found."
            # Order of names in the list is not specified, so compare as sets or counters
            assert collections.Counter(reversed_dict[animal]) == collections.Counter(people_list), \
                f"List of people for animal '{animal}' is incorrect. Expected {sorted(people_list)}, got {sorted(reversed_dict[animal])}."

# No test for `itertools` requirement, as it's an internal implementation detail, not an observable property.
# The problem statement lists it as a requirement, but its usage doesn't directly translate to an output property.
# The tests cover the observable behavior of the function.