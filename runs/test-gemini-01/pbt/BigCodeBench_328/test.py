# SEARCH PLAN:
# 1. Boundary `number_teams`: Test with minimum (1) and small values to catch off-by-one or initialization errors.
# 2. Sorting Order: Verify that the points in the OrderedDict are strictly non-increasing, ensuring the descending sort requirement.
# 3. Output Structure and Completeness: Check that the output OrderedDict contains the correct number of teams and all expected team names.
# 4. Key Format: Ensure all keys are correctly formatted "Team i" strings and are unique.
from candidate import task_func
from hypothesis import given, settings, strategies as st
import collections

@settings(max_examples=50, deadline=None)
@given(number_teams=st.integers(min_value=1, max_value=12))
def test_output_is_ordereddict_and_correct_size(number_teams):
    """
    SPEC BASIS: "The ranking is then sorted... and returned as an OrderedDict."
                "Each team is assigned a name in the format 'Team i' ... where i ranges from 1 to the specified number of teams."
    PROPERTY: The output is an OrderedDict and contains exactly `number_teams` entries.
    STRATEGY: Generate `number_teams` from 1 (minimum reasonable) up to a small maximum (12) to cover boundary
              conditions and small inputs. This catches issues with loop bounds or initialization for small N.
    """
    try:
        ranking = task_func(number_teams=number_teams)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for number_teams={number_teams}: {e}"
    assert ranking is not None, f"task_func returned None for number_teams={number_teams}"
    assert isinstance(ranking, collections.OrderedDict), "Output must be an OrderedDict"
    assert len(ranking) == number_teams, f"Output OrderedDict has {len(ranking)} entries, expected {number_teams}"

@settings(max_examples=50, deadline=None)
@given(number_teams=st.integers(min_value=1, max_value=12))
def test_points_are_sorted_descending(number_teams):
    """
    SPEC BASIS: "The ranking is then sorted in descending order of points and returned as an OrderedDict."
    PROPERTY: The values (points) in the `OrderedDict` are in non-increasing order.
    STRATEGY: Generate `number_teams` within a reasonable range. Extract the points and verify their order.
              This is a direct check of the core sorting requirement, catching incorrect sort logic.
    """
    try:
        ranking = task_func(number_teams=number_teams)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for number_teams={number_teams}: {e}"
    assert ranking is not None, f"task_func returned None for number_teams={number_teams}"
    
    points = list(ranking.values())
    # Check if points are in non-increasing order
    assert all(points[i] >= points[i+1] for i in range(len(points) - 1)), \
        f"Points are not sorted in descending order: {points} for number_teams={number_teams}"

@settings(max_examples=50, deadline=None)
@given(number_teams=st.integers(min_value=1, max_value=12))
def test_all_expected_teams_are_present_and_unique(number_teams):
    """
    SPEC BASIS: "Each team is assigned a name in the format 'Team i' ... where i ranges from 1 to the specified number of teams."
    PROPERTY: The set of keys in the `OrderedDict` exactly matches the set of expected team names ("Team 1", "Team 2", ..., "Team N").
    STRATEGY: Generate `number_teams` within a reasonable range. Construct the expected set of team names and
              compare it with the actual keys. This catches cases where teams are missing, duplicated, or incorrectly named.
    """
    try:
        ranking = task_func(number_teams=number_teams)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for number_teams={number_teams}: {e}"
    assert ranking is not None, f"task_func returned None for number_teams={number_teams}"

    expected_team_names = {f"Team {i}" for i in range(1, number_teams + 1)}
    actual_team_names = set(ranking.keys())

    assert actual_team_names == expected_team_names, \
        f"Actual team names {actual_team_names} do not match expected {expected_team_names} for number_teams={number_teams}"
    assert len(actual_team_names) == len(ranking), "Keys in OrderedDict must be unique"

@settings(max_examples=50, deadline=None)
@given(number_teams=st.integers(min_value=1, max_value=12))
def test_team_names_format(number_teams):
    """
    SPEC BASIS: "Each team is assigned a name in the format 'Team i' ... where i ranges from 1 to the specified number of teams."
    PROPERTY: All keys in the output OrderedDict are strings matching the "Team i" format.
    STRATEGY: Iterate through the keys of the generated OrderedDict and verify each key adheres to the specified format.
              This targets potential errors in string formatting or indexing when generating team names.
    """
    try:
        ranking = task_func(number_teams=number_teams)
    except Exception as e:
        assert False, f"task_func raised an unexpected exception for number_teams={number_teams}: {e}"
    assert ranking is not None, f"task_func returned None for number_teams={number_teams}"

    for key in ranking.keys():
        assert isinstance(key, str), f"Team name '{key}' is not a string for number_teams={number_teams}"
        assert key.startswith("Team "), f"Team name '{key}' does not start with 'Team ' for number_teams={number_teams}"
        try:
            parts = key.split(" ")
            assert len(parts) == 2, f"Team name '{key}' has incorrect number of parts for number_teams={number_teams}"
            team_number_str = parts[1]
            team_number = int(team_number_str)
            assert 1 <= team_number <= number_teams, \
                f"Team number '{team_number}' extracted from '{key}' is out of expected range [1, {number_teams}]"
        except (IndexError, ValueError):
            assert False, f"Team name '{key}' does not follow 'Team i' format correctly for number_teams={number_teams}"