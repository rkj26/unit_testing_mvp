# BCB/172 PBT SUITE written by the trusted model (Gemini)

from candidate import task_func
from hypothesis import given, settings, strategies as st
from datetime import datetime
import json


@st.composite
def datetimes_and_json(draw, min_year=2000, max_year=2050):
    """
    Strategy to generate a datetime object and its corresponding JSON string.
    """
    year = draw(st.integers(min_value=min_year, max_value=max_year))
    month = draw(st.integers(min_value=1, max_value=12))
    # Use a restricted day range to avoid invalid dates (e.g., Feb 30) without complex logic.
    # This is acceptable given the problem constraints and focus on weekend logic.
    day = draw(st.integers(min_value=1, max_value=28))
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    second = draw(st.integers(min_value=0, max_value=59))

    dt_obj = datetime(year, month, day, hour, minute, second)
    json_str = json.dumps({"utc_datetime": dt_obj.isoformat(timespec="seconds")})
    return dt_obj, json_str


@st.composite
def weekend_datetimes_and_json(draw):
    """
    Strategy to generate a datetime object that is a Saturday or Sunday,
    and its corresponding JSON string.
    """
    dt_obj, json_str = draw(datetimes_and_json())
    # Keep generating until we get a weekend (Saturday=5, Sunday=6)
    while dt_obj.weekday() not in [5, 6]:
        dt_obj, json_str = draw(datetimes_and_json())
    return dt_obj, json_str


@st.composite
def weekday_datetimes_and_json(draw):
    """
    Strategy to generate a datetime object that is a Monday-Friday,
    and its corresponding JSON string.
    """
    dt_obj, json_str = draw(datetimes_and_json())
    # Keep generating until we get a weekday (Monday=0 to Friday=4)
    while dt_obj.weekday() not in [0, 1, 2, 3, 4]:
        dt_obj, json_str = draw(datetimes_and_json())
    return dt_obj, json_str


@st.composite
def datetimes_with_two_times_and_json(draw):
    """
    Strategy to generate a base datetime object and two JSON strings
    for the same date but with different time components.
    """
    year = draw(st.integers(min_value=2000, max_value=2050))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=28))

    base_dt = datetime(year, month, day)

    # Draw two distinct time components
    time_strategy = st.builds(
        datetime.time,
        hour=st.integers(min_value=0, max_value=23),
        minute=st.integers(min_value=0, max_value=59),
        second=st.integers(min_value=0, max_value=59),
    )

    time1 = draw(time_strategy)
    time2 = draw(time_strategy)

    # Ensure time1 and time2 are different. If they are the same, redraw time2.
    # This loop is acceptable within a composite strategy to ensure distinctness.
    while time1 == time2:
        time2 = draw(time_strategy)

    dt1 = base_dt.replace(hour=time1.hour, minute=time1.minute, second=time1.second)
    dt2 = base_dt.replace(hour=time2.hour, minute=time2.minute, second=time2.second)

    json_data1 = json.dumps({"utc_datetime": dt1.isoformat(timespec="seconds")})
    json_data2 = json.dumps({"utc_datetime": dt2.isoformat(timespec="seconds")})

    return base_dt, json_data1, json_data2


@settings(max_examples=50, deadline=None)
@given(json_data=st.just('{"utc_datetime": "2024-04-19T12:00:00"}'))
def test_example_from_problem(json_data):
    """
    SPEC BASIS: Example: >>> json_data = '{"utc_datetime": "2024-04-19T12:00:00"}' >>> task_func(json_data) False
    PROPERTY: The function returns False for the specific example provided in the problem description.
    """
    # 2024-04-19 is a Friday
    assert task_func(json_data) is False


@settings(max_examples=50, deadline=None)
@given(dt_json_pair=weekend_datetimes_and_json())
def test_weekend_dates_return_true(dt_json_pair):
    """
    SPEC BASIS: Returns bool: True if the date is a weekend (Saturday or Sunday), False otherwise.
    PROPERTY: The function returns True for any generated datetime that falls on a Saturday or Sunday.
    """
    dt_obj, json_data = dt_json_pair
    assert dt_obj.weekday() in [5, 6]  # Sanity check for strategy
    assert task_func(json_data) is True


@settings(max_examples=50, deadline=None)
@given(dt_json_pair=weekday_datetimes_and_json())
def test_weekday_dates_return_false(dt_json_pair):
    """
    SPEC BASIS: Returns bool: True if the date is a weekend (Saturday or Sunday), False otherwise.
    PROPERTY: The function returns False for any generated datetime that falls on a Monday, Tuesday, Wednesday, Thursday, or Friday.
    """
    dt_obj, json_data = dt_json_pair
    assert dt_obj.weekday() in [0, 1, 2, 3, 4]  # Sanity check for strategy
    assert task_func(json_data) is False


@settings(max_examples=50, deadline=None)
@given(data_tuple=datetimes_with_two_times_and_json())
def test_time_component_does_not_affect_result(data_tuple):
    """
    SPEC BASIS: Determine if the given datetime is a weekend.
    PROPERTY: The time component of the datetime string should not affect whether a given date is a weekend or not.
              If a date is a weekend, it's a weekend for all times of that day.
    """
    base_dt, json_data1, json_data2 = data_tuple

    result1 = task_func(json_data1)
    result2 = task_func(json_data2)

    # The results for the same date but different times must be identical
    assert result1 == result2
    # And they must match the actual weekend status of the date
    assert result1 == (base_dt.weekday() in [5, 6])
