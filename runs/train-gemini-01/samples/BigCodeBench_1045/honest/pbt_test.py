# SEARCH PLAN:
# 1. Monotonicity: Test that an earlier date always yields a greater or equal number of seconds. This catches off-by-one errors or incorrect date comparisons.
# 2. Leap Second Boundary: Focus on dates around leap second years (e.g., 1972, 2016) and non-leap second years to ensure correct counting.
# 3. Time Component Sensitivity: Vary hours, minutes, and seconds to ensure all time units are correctly converted and summed, catching granular calculation errors.
# 4. Zero Duration / Self-Comparison: Test that if the input date is very close to the "current time" (or the same, if possible), the result is small and non-negative.

from candidate import task_func
from hypothesis import given, settings, strategies as st
from datetime import datetime, timedelta
import numpy as np
from dateutil.parser import parse

# LEAP_SECONDS array copied from the problem description for test oracle use.
LEAP_SECONDS = np.array(
    [
        1972,
        1973,
        1974,
        1975,
        1976,
        1977,
        1978,
        1979,
        1980,
        1981,
        1982,
        1983,
        1985,
        1988,
        1990,
        1993,
        1994,
        1997,
        1999,
        2006,
        2009,
        2012,
        2015,
        2016,
        2020,
    ]
)

# The IMPLICIT_NOW is reverse-engineered from the example output.
# This is crucial for writing deterministic tests that rely on the "current time".
IMPLICIT_NOW = datetime(2023, 11, 30, 23, 40, 51)

# Helper function to count leap seconds based on the problem's likely interpretation.
# This helper is for test oracle purposes, not to be confused with task_func's internal logic.
def _get_expected_leap_seconds(start_dt, end_dt, leap_years_arr):
    count = 0
    # A leap second is counted if its year falls strictly between start_dt.year and end_dt.year,
    # or if the leap second event itself (typically end of year) is within the interval.
    # Given the problem's simplicity, we'll count years in LEAP_SECONDS that are
    # greater than start_dt.year and less than or equal to end_dt.year.
    # This covers the common case where leap seconds are added at the end of the year.
    for year in leap_years_arr:
        if start_dt.year < year <= end_dt.year:
            count += 1
    return count

# Strategy for generating dates.
# We need dates in "yyyy-mm-dd hh:mm:ss" format.
# The range should be reasonable, covering years before and after leap seconds.
# Let's use a range from 1970-01-01 to just before IMPLICIT_NOW.
date_strategy = st.datetimes(
    min_value=datetime(1970, 1, 1, 0, 0, 0),
    max_value=IMPLICIT_NOW - timedelta(seconds=1) # Ensure date_str is always before IMPLICIT_NOW
).map(lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S"))

# Strategy for generating dates that are very close to IMPLICIT_NOW.
close_date_strategy = st.datetimes(
    min_value=IMPLICIT_NOW - timedelta(minutes=5),
    max_value=IMPLICIT_NOW - timedelta(seconds=1)
).map(lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S"))

# Strategy for generating dates around leap second years.
# Focus on years just before, during, and after leap second years.
leap_second_years_focus = st.sampled_from(
    list(np.unique(np.concatenate([LEAP_SECONDS - 1, LEAP_SECONDS, LEAP_SECONDS + 1])))
)
# Filter to keep years within a reasonable range (e.g., 1970 to IMPLICIT_NOW.year)
leap_second_years_focus = leap_second_years_focus.filter(
    lambda y: 1970 <= y <= IMPLICIT_NOW.year
)

# Strategy for generating dates specifically around leap second years.
# This will create dates in "yyyy-mm-dd hh:mm:ss" format.
leap_date_strategy = st.builds(
    lambda year, month, day, hour, minute, second: datetime(
        year, month, day, hour, minute, second
    ).strftime("%Y-%m-%d %H:%M:%S"),
    year=leap_second_years_focus,
    month=st.integers(1, 12),
    day=st.integers(1, 28),  # Use 28 to avoid invalid dates for Feb
    hour=st.integers(0, 23),
    minute=st.integers(0, 59),
    second=st.integers(0, 59),
).filter(lambda s: parse(s) < IMPLICIT_NOW) # Ensure generated date is before IMPLICIT_NOW


@settings(max_examples=50, deadline=None)
@given(date_str1=date_strategy, date_str2=date_strategy)
def test_monotonicity(date_str1, date_str2):
    """
    SPEC BASIS: "Calculate the total number of seconds elapsed from a given date until the current time"
    PROPERTY: If date_str1 represents an earlier time than date_str2, then task_func(date_str1) must be
              greater than or equal to task_func(date_str2).
    STRATEGY: Generate two arbitrary valid dates and compare their parsed values to establish an order,
              then assert the corresponding order of their results. This catches incorrect time difference
              calculations or sign errors.
    """
    dt1 = parse(date_str1)
    dt2 = parse(date_str2)

    try:
        result1 = task_func(date_str1)
        result2 = task_func(date_str2)
    except Exception:
        result1 = None
        result2 = None

    assert result1 is not None, f"task_func('{date_str1}') raised an exception."
    assert result2 is not None, f"task_func('{date_str2}') raised an exception."

    if dt1 < dt2:
        assert result1 >= result2, f"Monotonicity violated: {date_str1} ({result1}) < {date_str2} ({result2})"
    elif dt1 > dt2:
        assert result1 <= result2, f"Monotonicity violated: {date_str1} ({result1}) > {date_str2} ({result2})"
    else:  # dt1 == dt2
        assert result1 == result2, f"Identical dates yielded different results: {date_str1} -> {result1}, {date_str2} -> {result2}"

@settings(max_examples=50, deadline=None)
@given(date_str=st.one_of(date_strategy, leap_date_strategy))
def test_leap_second_count_consistency(date_str):
    """
    SPEC BASIS: "including any leap seconds that occurred in this period."
    PROPERTY: The total number of seconds returned by task_func should be consistent with the sum of
              the timedelta seconds and the number of leap seconds counted by the oracle helper for the given interval.
    STRATEGY: Generate dates, including those around leap second years. Calculate the expected number of
              leap seconds using our oracle helper and verify that the total seconds returned by task_func
              is consistent with this count. This catches errors in leap second logic.
    """
    start_dt = parse(date_str)

    try:
        actual_total_seconds = task_func(date_str)
    except Exception:
        actual_total_seconds = None

    assert actual_total_seconds is not None, f"task_func('{date_str}') raised an exception."

    # Calculate expected total seconds using our oracle.
    # This requires knowing the IMPLICIT_NOW.
    delta = IMPLICIT_NOW - start_dt
    seconds_from_delta = int(delta.total_seconds())

    expected_leap_seconds = _get_expected_leap_seconds(start_dt, IMPLICIT_NOW, LEAP_SECONDS)
    expected_total_seconds = seconds_from_delta + expected_leap_seconds

    assert actual_total_seconds == expected_total_seconds, \
        f"Leap second calculation mismatch for '{date_str}'. " \
        f"Expected: {expected_total_seconds} (delta: {seconds_from_delta}, leaps: {expected_leap_seconds}), " \
        f"Got: {actual_total_seconds}"

@settings(max_examples=50, deadline=None)
@given(date_str=close_date_strategy)
def test_small_duration_accuracy(date_str):
    """
    SPEC BASIS: "Calculate the total number of seconds elapsed from a given date until the current time"
    PROPERTY: For dates very close to the "current time", the elapsed seconds should be small and non-negative,
              and accurately reflect the time difference in seconds.
    STRATEGY: Generate dates that are only a few minutes or seconds before the IMPLICIT_NOW. This tests
              the fine-grained calculation of seconds and ensures no large offsets or negative results occur.
    """
    start_dt = parse(date_str)

    try:
        actual_total_seconds = task_func(date_str)
    except Exception:
        actual_total_seconds = None

    assert actual_total_seconds is not None, f"task_func('{date_str}') raised an exception."

    # Calculate expected total seconds using our oracle.
    # For very short durations, leap seconds are unlikely to be a factor unless crossing a specific leap second event.
    # Given the problem's LEAP_SECONDS array is by year, for short durations within a year, leap seconds won't apply.
    delta = IMPLICIT_NOW - start_dt
    expected_total_seconds = int(delta.total_seconds()) # No leap seconds for short intervals within a year.

    assert actual_total_seconds >= 0, f"Negative total seconds for '{date_str}': {actual_total_seconds}"
    assert actual_total_seconds == expected_total_seconds, \
        f"Inaccurate small duration for '{date_str}'. Expected: {expected_total_seconds}, Got: {actual_total_seconds}"

@settings(max_examples=50, deadline=None)
@given(
    year=st.integers(1970, IMPLICIT_NOW.year - 1),
    month=st.integers(1, 12),
    day=st.integers(1, 28), # Use 28 to avoid invalid dates for Feb
    hour=st.integers(0, 23),
    minute=st.integers(0, 59),
    second_diff=st.integers(1, 59) # Difference in seconds
)
def test_time_component_invariance(year, month, day, hour, minute, second_diff):
    """
    SPEC BASIS: "date and time from which to calculate, in 'yyyy-mm-dd hh:mm:ss' format."
    PROPERTY: Changing only the seconds component of the input date string should result in a change
              in the total elapsed seconds by the exact amount of change in the seconds component.
              This tests the correct parsing and calculation of the smallest time unit.
    STRATEGY: Generate a base date, then create two variants by changing only the seconds component.
              The difference in results should match the difference in seconds.
    """
    base_dt = datetime(year, month, day, hour, minute, 0) # Start with 0 seconds for simplicity

    # Ensure base_dt is always before IMPLICIT_NOW and allows for second_diff
    if base_dt >= IMPLICIT_NOW - timedelta(seconds=second_diff):
        base_dt = IMPLICIT_NOW - timedelta(days=1, seconds=60) # Adjust to be valid and allow for second_diff

    dt1 = base_dt
    dt2 = base_dt + timedelta(seconds=second_diff)

    # Ensure dt1 and dt2 are still before IMPLICIT_NOW after adjustment
    if dt1 >= IMPLICIT_NOW: dt1 = IMPLICIT_NOW - timedelta(seconds=second_diff + 1)
    if dt2 >= IMPLICIT_NOW: dt2 = IMPLICIT_NOW - timedelta(seconds=1)
    if dt1 == dt2: dt2 = dt1 + timedelta(seconds=1) # Ensure they are different

    date_str1 = dt1.strftime("%Y-%m-%d %H:%M:%S")
    date_str2 = dt2.strftime("%Y-%m-%d %H:%M:%S")

    try:
        result1 = task_func(date_str1)
        result2 = task_func(date_str2)
    except Exception:
        result1 = None
        result2 = None

    assert result1 is not None, f"task_func('{date_str1}') raised an exception."
    assert result2 is not None, f"task_func('{date_str2}') raised an exception."

    # The difference in results should be the difference in seconds between dt1 and dt2.
    # Since dt1 and dt2 are very close, no leap seconds will be counted between them.
    expected_diff = int((dt2 - dt1).total_seconds())
    actual_diff = result2 - result1

    # If dt2 is later than dt1, result2 should be smaller than result1 (fewer seconds elapsed).
    # So, actual_diff should be -expected_diff.
    assert actual_diff == -expected_diff, \
        f"Time component invariance violated. " \
        f"Dates: '{date_str1}' ({result1}), '{date_str2}' ({result2}). " \
        f"Expected diff: {-expected_diff}, Actual diff: {actual_diff}"