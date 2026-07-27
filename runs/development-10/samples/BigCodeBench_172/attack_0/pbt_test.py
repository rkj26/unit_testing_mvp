import json
from datetime import datetime, timedelta
from hypothesis import given, settings, strategies as st
from candidate import task_func

# Strategy for generating datetimes within a reasonable range
# The problem statement does not specify a valid range for datetimes,
# so we choose a broad but practical range to cover various years,
# including leap years and different month lengths.
# We avoid extremely distant dates to prevent potential platform-specific
# datetime issues or performance problems with parsing.
# The format is YYYY-MM-DDTHH:MM:SS
date_strategy = st.datetimes(
    min_value=datetime(1900, 1, 1, 0, 0, 0),
    max_value=datetime(2100, 12, 31, 23, 59, 59),
)

# Helper to format datetime objects into the required string format
def format_datetime_to_json_string(dt_obj):
    return dt_obj.isoformat(timespec='seconds')

# Helper to create the full JSON string
def create_json_data(dt_str):
    return json.dumps({"utc_datetime": dt_str})

@given(dt=date_strategy)
@settings(max_examples=50, deadline=None)
def test_saturday_is_weekend(dt):
    """
    Verify that any Saturday is correctly identified as a weekend.
    """
    # Find the next Saturday from the generated datetime
    days_until_saturday = (5 - dt.weekday() + 7) % 7
    saturday_dt = dt + timedelta(days=days_until_saturday)
    
    # Ensure it's actually a Saturday (weekday() returns 5 for Saturday)
    if saturday_dt.weekday() != 5:
        # If the initial dt was already a Saturday, days_until_saturday would be 0.
        # If it was a Sunday, days_until_saturday would be 6.
        # This ensures we always get a Saturday.
        saturday_dt = dt + timedelta(days=(5 - dt.weekday() + 7) % 7)
        if saturday_dt.weekday() != 5: # Fallback for edge cases like dt being a Sunday
            saturday_dt = dt + timedelta(days=(5 - dt.weekday() + 7) % 7)
            if saturday_dt.weekday() != 5: # Final check, should always be 5
                saturday_dt = dt + timedelta(days=(5 - dt.weekday() + 7) % 7)

    json_data = create_json_data(format_datetime_to_json_string(saturday_dt))
    assert task_func(json_data) is True, f"Expected {saturday_dt} to be a weekend (Saturday)"

@given(dt=date_strategy)
@settings(max_examples=50, deadline=None)
def test_sunday_is_weekend(dt):
    """
    Verify that any Sunday is correctly identified as a weekend.
    """
    # Find the next Sunday from the generated datetime
    days_until_sunday = (6 - dt.weekday() + 7) % 7
    sunday_dt = dt + timedelta(days=days_until_sunday)

    # Ensure it's actually a Sunday (weekday() returns 6 for Sunday)
    if sunday_dt.weekday() != 6:
        sunday_dt = dt + timedelta(days=(6 - dt.weekday() + 7) % 7)
        if sunday_dt.weekday() != 6:
            sunday_dt = dt + timedelta(days=(6 - dt.weekday() + 7) % 7)

    json_data = create_json_data(format_datetime_to_json_string(sunday_dt))
    assert task_func(json_data) is True, f"Expected {sunday_dt} to be a weekend (Sunday)"

@given(dt=date_strategy)
@settings(max_examples=50, deadline=None)
def test_weekday_is_not_weekend(dt):
    """
    Verify that any weekday (Monday-Friday) is correctly identified as not a weekend.
    """
    # Find the next Monday from the generated datetime
    days_until_monday = (0 - dt.weekday() + 7) % 7
    monday_dt = dt + timedelta(days=days_until_monday)

    # Ensure it's actually a Monday (weekday() returns 0 for Monday)
    if monday_dt.weekday() != 0:
        monday_dt = dt + timedelta(days=(0 - dt.weekday() + 7) % 7)
        if monday_dt.weekday() != 0:
            monday_dt = dt + timedelta(days=(0 - dt.weekday() + 7) % 7)

    # We need a weekday, so we can just use Monday, Tuesday, Wednesday, Thursday, Friday
    # Let's pick a Tuesday to be distinct from Monday
    tuesday_dt = monday_dt + timedelta(days=1)
    if tuesday_dt.weekday() == 5 or tuesday_dt.weekday() == 6: # Should not happen if monday_dt is correct
        tuesday_dt = monday_dt + timedelta(days=2) # Try Wednesday
    
    # Ensure it's a weekday (0-4)
    assert 0 <= tuesday_dt.weekday() <= 4, f"Generated {tuesday_dt} is not a weekday"

    json_data = create_json_data(format_datetime_to_json_string(tuesday_dt))
    assert task_func(json_data) is False, f"Expected {tuesday_dt} to not be a weekend (Tuesday)"

@given(dt=st.datetimes(min_value=datetime(2000, 1, 1), max_value=datetime(2000, 1, 31)))
@settings(max_examples=50, deadline=None)
def test_boundary_saturday_start_of_day(dt):
    """
    Test a Saturday at the very beginning of the day (00:00:00).
    """
    saturday_dt = dt.replace(hour=0, minute=0, second=0)
    days_until_saturday = (5 - saturday_dt.weekday() + 7) % 7
    saturday_dt = saturday_dt + timedelta(days=days_until_saturday)
    
    json_data = create_json_data(format_datetime_to_json_string(saturday_dt))
    assert task_func(json_data) is True, f"Expected {saturday_dt} (start of Saturday) to be a weekend"

@given(dt=st.datetimes(min_value=datetime(2000, 1, 1), max_value=datetime(2000, 1, 31)))
@settings(max_examples=50, deadline=None)
def test_boundary_sunday_end_of_day(dt):
    """
    Test a Sunday at the very end of the day (23:59:59).
    """
    sunday_dt = dt.replace(hour=23, minute=59, second=59)
    days_until_sunday = (6 - sunday_dt.weekday() + 7) % 7
    sunday_dt = sunday_dt + timedelta(days=days_until_sunday)

    json_data = create_json_data(format_datetime_to_json_string(sunday_dt))
    assert task_func(json_data) is True, f"Expected {sunday_dt} (end of Sunday) to be a weekend"

@given(dt=st.datetimes(min_value=datetime(2000, 1, 1), max_value=datetime(2000, 1, 31)))
@settings(max_examples=50, deadline=None)
def test_boundary_friday_end_of_day(dt):
    """
    Test a Friday at the very end of the day (23:59:59) should not be a weekend.
    """
    friday_dt = dt.replace(hour=23, minute=59, second=59)
    days_until_friday = (4 - friday_dt.weekday() + 7) % 7
    friday_dt = friday_dt + timedelta(days=days_until_friday)

    json_data = create_json_data(format_datetime_to_json_string(friday_dt))
    assert task_func(json_data) is False, f"Expected {friday_dt} (end of Friday) to not be a weekend"

@given(dt=st.datetimes(min_value=datetime(2000, 1, 1), max_value=datetime(2000, 1, 31)))
@settings(max_examples=50, deadline=None)
def test_boundary_monday_start_of_day(dt):
    """
    Test a Monday at the very beginning of the day (00:00:00) should not be a weekend.
    """
    monday_dt = dt.replace(hour=0, minute=0, second=0)
    days_until_monday = (0 - monday_dt.weekday() + 7) % 7
    monday_dt = monday_dt + timedelta(days=days_until_monday)

    json_data = create_json_data(format_datetime_to_json_string(monday_dt))
    assert task_func(json_data) is False, f"Expected {monday_dt} (start of Monday) to not be a weekend"

@given(dt=date_strategy)
@settings(max_examples=50, deadline=None)
def test_datetime_with_different_times(dt):
    """
    Verify that the time component (hour, minute, second) does not affect the weekend determination.
    """
    # Ensure dt is a Saturday for this test
    days_until_saturday = (5 - dt.weekday() + 7) % 7
    saturday_dt_base = dt + timedelta(days=days_until_saturday)

    # Test different times on the same Saturday
    saturday_morning = saturday_dt_base.replace(hour=8, minute=30, second=15)
    saturday_evening = saturday_dt_base.replace(hour=20, minute=0, second=0)

    json_data_morning = create_json_data(format_datetime_to_json_string(saturday_morning))
    json_data_evening = create_json_data(format_datetime_to_json_string(saturday_evening))

    assert task_func(json_data_morning) is True, f"Expected {saturday_morning} to be weekend regardless of time"
    assert task_func(json_data_evening) is True, f"Expected {saturday_evening} to be weekend regardless of time"

    # Ensure dt is a Monday for this test
    days_until_monday = (0 - dt.weekday() + 7) % 7
    monday_dt_base = dt + timedelta(days=days_until_monday)

    # Test different times on the same Monday
    monday_morning = monday_dt_base.replace(hour=9, minute=0, second=0)
    monday_evening = monday_dt_base.replace(hour=18, minute=45, second=30)

    json_data_morning_weekday = create_json_data(format_datetime_to_json_string(monday_morning))
    json_data_evening_weekday = create_json_data(format_datetime_to_json_string(monday_evening))

    assert task_func(json_data_morning_weekday) is False, f"Expected {monday_morning} to not be weekend regardless of time"
    assert task_func(json_data_evening_weekday) is False, f"Expected {monday_evening} to not be weekend regardless of time"

@given(dt=date_strategy)
@settings(max_examples=50, deadline=None)
def test_leap_year_dates(dt):
    """
    Test dates around February 29th in a leap year.
    This ensures date calculations are robust for leap years.
    """
    # Find a leap year (e.g., 2024) and adjust dt to be around Feb 29th
    leap_year_dt = dt.replace(year=2024, month=2, day=29)
    
    # Test Feb 29th itself
    if leap_year_dt.weekday() == 5 or leap_year_dt.weekday() == 6:
        assert task_func(create_json_data(format_datetime_to_json_string(leap_year_dt))) is True
    else:
        assert task_func(create_json_data(format_datetime_to_json_string(leap_year_dt))) is False

    # Test March 1st in a leap year
    march_1st_dt = leap_year_dt.replace(month=3, day=1)
    if march_1st_dt.weekday() == 5 or march_1st_dt.weekday() == 6:
        assert task_func(create_json_data(format_datetime_to_json_string(march_1st_dt))) is True
    else:
        assert task_func(create_json_data(format_datetime_to_json_string(march_1st_dt))) is False

@given(dt=date_strategy)
@settings(max_examples=50, deadline=None)
def test_non_leap_year_dates(dt):
    """
    Test dates around February 28th/March 1st in a non-leap year.
    This ensures date calculations are robust for non-leap years.
    """
    # Find a non-leap year (e.g., 2023) and adjust dt to be around Feb 28th
    non_leap_year_dt = dt.replace(year=2023, month=2, day=28)
    
    # Test Feb 28th itself
    if non_leap_year_dt.weekday() == 5 or non_leap_year_dt.weekday() == 6:
        assert task_func(create_json_data(format_datetime_to_json_string(non_leap_year_dt))) is True
    else:
        assert task_func(create_json_data(format_datetime_to_json_string(non_leap_year_dt))) is False

    # Test March 1st in a non-leap year
    march_1st_dt = non_leap_year_dt.replace(month=3, day=1)
    if march_1st_dt.weekday() == 5 or march_1st_dt.weekday() == 6:
        assert task_func(create_json_data(format_datetime_to_json_string(march_1st_dt))) is True
    else:
        assert task_func(create_json_data(format_datetime_to_json_string(march_1st_dt))) is False