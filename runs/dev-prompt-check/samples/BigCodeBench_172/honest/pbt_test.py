from candidate import task_func
from hypothesis import given, settings, strategies as st
from datetime import datetime, timedelta
import json

# Strategy for generating datetimes
# We'll use a reasonable range for datetimes to avoid issues with extreme dates
# that might not be handled consistently across all systems or libraries,
# while still covering a wide range of years, including leap years.
# The problem statement implies standard datetime parsing, so we stick to ISO format.
st_datetimes = st.datetimes(
    min_value=datetime(1900, 1, 1, 0, 0, 0),
    max_value=datetime(2100, 12, 31, 23, 59, 59, 999999)
)

def _create_json_data(dt_obj: datetime) -> str:
    """Helper to create the JSON string from a datetime object."""
    # The problem implies ISO format without timezone info, as it states "UTC format"
    # and the example uses "2024-04-19T12:00:00".
    # We'll stick to this format for consistency.
    return json.dumps({"utc_datetime": dt_obj.isoformat()})

def _create_json_data_with_extra_keys(dt_obj: datetime, extra_keys: dict) -> str:
    """Helper to create JSON with extra keys."""
    data = {"utc_datetime": dt_obj.isoformat()}
    data.update(extra_keys)
    return json.dumps(data)

@given(dt=st_datetimes)
@settings(max_examples=50, deadline=None)
def test_property_weekend_consistency_with_time_component(dt: datetime):
    """
    Property: The weekend status of a date should not change based on the time of day.
    If a date is a weekend, it should be a weekend for all times on that day.
    """
    # Normalize to start of day for comparison
    dt_start_of_day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    expected_is_weekend = (dt_start_of_day.weekday() >= 5) # 5=Saturday, 6=Sunday

    json_data = _create_json_data(dt)
    result = task_func(json_data)
    assert result == expected_is_weekend, \
        f"Datetime {dt.isoformat()} (weekday {dt.weekday()}) result {result} " \
        f"does not match expected {expected_is_weekend} based on start of day."

@given(dt=st_datetimes)
@settings(max_examples=50, deadline=None)
def test_property_weekday_consistency_with_time_component(dt: datetime):
    """
    Property: The weekday status of a date should not change based on the time of day.
    If a date is a weekday, it should be a weekday for all times on that day.
    """
    # Normalize to start of day for comparison
    dt_start_of_day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    expected_is_weekday = (dt_start_of_day.weekday() < 5) # 0=Monday to 4=Friday

    json_data = _create_json_data(dt)
    result = task_func(json_data)
    assert result != expected_is_weekday, \
        f"Datetime {dt.isoformat()} (weekday {dt.weekday()}) result {result} " \
        f"does not match expected {not expected_is_weekday} based on start of day."

@given(dt=st_datetimes.filter(lambda d: d.weekday() >= 5)) # Filter for weekends
@settings(max_examples=50, deadline=None)
def test_property_weekend_plus_seven_days_is_weekend(dt: datetime):
    """
    Metamorphic Property: If a date is a weekend, then adding 7 days should also be a weekend.
    """
    json_data_original = _create_json_data(dt)
    result_original = task_func(json_data_original)
    assert result_original is True, f"Precondition failed: {dt.isoformat()} should be a weekend."

    dt_plus_seven = dt + timedelta(days=7)
    json_data_plus_seven = _create_json_data(dt_plus_seven)
    result_plus_seven = task_func(json_data_plus_seven)

    assert result_plus_seven is True, \
        f"Original weekend {dt.isoformat()} but {dt_plus_seven.isoformat()} (7 days later) is not a weekend."

@given(dt=st_datetimes.filter(lambda d: d.weekday() < 5)) # Filter for weekdays
@settings(max_examples=50, deadline=None)
def test_property_weekday_plus_seven_days_is_weekday(dt: datetime):
    """
    Metamorphic Property: If a date is a weekday, then adding 7 days should also be a weekday.
    """
    json_data_original = _create_json_data(dt)
    result_original = task_func(json_data_original)
    assert result_original is False, f"Precondition failed: {dt.isoformat()} should be a weekday."

    dt_plus_seven = dt + timedelta(days=7)
    json_data_plus_seven = _create_json_data(dt_plus_seven)
    result_plus_seven = task_func(json_data_plus_seven)

    assert result_plus_seven is False, \
        f"Original weekday {dt.isoformat()} but {dt_plus_seven.isoformat()} (7 days later) is a weekend."

@given(dt=st_datetimes.filter(lambda d: d.weekday() == 4)) # Filter for Fridays
@settings(max_examples=50, deadline=None)
def test_property_friday_plus_one_day_is_weekend(dt: datetime):
    """
    Metamorphic Property: If a date is a Friday, then adding 1 day should result in a weekend (Saturday).
    """
    json_data_friday = _create_json_data(dt)
    result_friday = task_func(json_data_friday)
    assert result_friday is False, f"Precondition failed: {dt.isoformat()} should be a Friday (weekday)."

    dt_saturday = dt + timedelta(days=1)
    json_data_saturday = _create_json_data(dt_saturday)
    result_saturday = task_func(json_data_saturday)

    assert result_saturday is True, \
        f"Friday {dt.isoformat()} but {dt_saturday.isoformat()} (next day) is not a weekend."

@given(dt=st_datetimes.filter(lambda d: d.weekday() == 0)) # Filter for Mondays
@settings(max_examples=50, deadline=None)
def test_property_monday_minus_one_day_is_weekend(dt: datetime):
    """
    Metamorphic Property: If a date is a Monday, then subtracting 1 day should result in a weekend (Sunday).
    """
    json_data_monday = _create_json_data(dt)
    result_monday = task_func(json_data_monday)
    assert result_monday is False, f"Precondition failed: {dt.isoformat()} should be a Monday (weekday)."

    dt_sunday = dt - timedelta(days=1)
    json_data_sunday = _create_json_data(dt_sunday)
    result_sunday = task_func(json_data_sunday)

    assert result_sunday is True, \
        f"Monday {dt.isoformat()} but {dt_sunday.isoformat()} (previous day) is not a weekend."

@given(
    dt=st_datetimes,
    extra_keys=st.dictionaries(
        keys=st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
        values=st.text(max_size=10) | st.integers() | st.booleans(),
        min_size=1, max_size=5
    )
)
@settings(max_examples=50, deadline=None)
def test_property_extra_json_keys_do_not_affect_result(dt: datetime, extra_keys: dict):
    """
    Property: The presence of extra keys in the JSON data should not affect the result,
    as long as 'utc_datetime' is present and valid.
    """
    expected_is_weekend = (dt.weekday() >= 5)

    json_data_with_extra = _create_json_data_with_extra_keys(dt, extra_keys)
    result_with_extra = task_func(json_data_with_extra)

    assert result_with_extra == expected_is_weekend, \
        f"Datetime {dt.isoformat()} with extra keys {extra_keys} resulted in {result_with_extra}, " \
        f"expected {expected_is_weekend}."

@given(dt=st_datetimes)
@settings(max_examples=50, deadline=None)
def test_property_leap_year_dates_are_handled_correctly(dt: datetime):
    """
    Property: Dates around leap years (e.g., Feb 29th) should be handled correctly.
    This test implicitly covers leap years by generating a wide range of dates.
    We check if the calculated weekday matches the function's output.
    """
    expected_is_weekend = (dt.weekday() >= 5)
    json_data = _create_json_data(dt)
    result = task_func(json_data)
    assert result == expected_is_weekend, \
        f"Leap year related date {dt.isoformat()} (weekday {dt.weekday()}) result {result} " \
        f"does not match expected {expected_is_weekend}."

@given(dt=st_datetimes.filter(lambda d: d.day == 1)) # Filter for first day of month
@settings(max_examples=50, deadline=None)
def test_property_first_day_of_month_is_correct(dt: datetime):
    """
    Property: The function should correctly identify weekend status for the first day of any month.
    """
    expected_is_weekend = (dt.weekday() >= 5)
    json_data = _create_json_data(dt)
    result = task_func(json_data)
    assert result == expected_is_weekend, \
        f"First day of month {dt.isoformat()} (weekday {dt.weekday()}) result {result} " \
        f"does not match expected {expected_is_weekend}."

@given(dt=st_datetimes.filter(lambda d: d.day == (datetime(d.year, d.month % 12 + 1, 1) - timedelta(days=1)).day)) # Filter for last day of month
@settings(max_examples=50, deadline=None)
def test_property_last_day_of_month_is_correct(dt: datetime):
    """
    Property: The function should correctly identify weekend status for the last day of any month.
    """
    expected_is_weekend = (dt.weekday() >= 5)
    json_data = _create_json_data(dt)
    result = task_func(json_data)
    assert result == expected_is_weekend, \
        f"Last day of month {dt.isoformat()} (weekday {dt.weekday()}) result {result} " \
        f"does not match expected {expected_is_weekend}."