import re
from datetime import time, datetime, timedelta
from hypothesis import given, settings, strategies as st

from candidate import task_func

# SEARCH PLAN:
# - Empty input or no error logs: covers the boundary case where no errors are found.
# - Single error log: verifies the example behavior and basic extraction/averaging.
# - Multiple error logs with identical times: checks averaging logic for a simple, non-trivial case.
# - Multiple error logs with varying times: verifies the core averaging logic using a metamorphic property.
# - Output types and structure: ensures the return value always conforms to the specified types.

# Helper strategy for generating log components
@st.composite
def log_line_strategy(draw, level_strategy=st.sampled_from(['INFO', 'WARNING', 'ERROR', 'DEBUG'])):
    year = draw(st.integers(2000, 2023))
    month = draw(st.integers(1, 12))
    day = draw(st.integers(1, 28)) # Simplifies date generation, avoids invalid dates
    hour = draw(st.integers(0, 23))
    minute = draw(st.integers(0, 59))
    second = draw(st.integers(0, 59))
    level = draw(level_strategy)
    message = draw(st.text(st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=10))
    
    date_str = f"{year:04d}-{month:02d}-{day:02d}"
    time_str = f"{hour:02d}:{minute:02d}:{second:02d}"
    
    return f"{date_str} {time_str} {level}: {message}"

# Helper strategy for generating datetime.time objects
time_strategy = st.builds(
    time,
    hour=st.integers(0, 23),
    minute=st.integers(0, 59),
    second=st.integers(0, 59)
)

@settings(max_examples=50, deadline=None)
@given(
    logs=st.lists(
        log_line_strategy(level_strategy=st.sampled_from(['INFO', 'WARNING', 'DEBUG'])),
        min_size=0, max_size=10
    )
)
def test_no_error_logs(logs):
    """
    SPEC BASIS: "Analyze the given list of logs for the occurrence of errors and calculate the average time of occurrence of errors."
    PROPERTY: If the input list is empty or contains no 'ERROR' logs, the list of error times should be empty,
              and the average time should be datetime.time(0,0).
    STRATEGY: Generate lists of logs that either are empty or contain only non-'ERROR' logs.
              This covers the empty input boundary and the case where no errors are found.
    """
    try:
        error_times, avg_time = task_func(logs)
    except Exception:
        error_times, avg_time = None, None

    assert error_times is not None and avg_time is not None, "task_func raised an exception on valid input."
    assert isinstance(error_times, list)
    assert isinstance(avg_time, time)
    assert len(error_times) == 0, "Expected an empty list of error times when no errors are present."
    assert avg_time == time(0, 0), "Expected average time to be 00:00:00 when no errors are present."


@settings(max_examples=50, deadline=None)
@given(
    error_time=time_strategy,
    other_logs=st.lists(
        log_line_strategy(level_strategy=st.sampled_from(['INFO', 'WARNING', 'DEBUG'])),
        min_size=0, max_size=9
    )
)
def test_single_error_log(error_time, other_logs):
    """
    SPEC BASIS: "Example: task_func(['2021-06-15 09:45:00 ERROR: Failed to connect to database', ...])
                ([datetime.time(9, 45)], datetime.time(9, 45))"
    PROPERTY: For a single error log, the returned list of error times contains exactly one element,
              which is the time from the log, and the average time is identical to that time.
    STRATEGY: Generate lists with exactly one 'ERROR' log (with a specific time) and arbitrary non-'ERROR' logs.
              This directly tests the example's behavior and the base case for averaging.
    """
    date_str = "2021-01-01" # Fixed date for simplicity
    error_log = f"{date_str} {error_time.strftime('%H:%M:%S')} ERROR: Test error message"
    
    # Insert the error log at a random position to ensure robustness
    all_logs = other_logs + [error_log]
    st.randoms().shuffle(all_logs) # Use Hypothesis's randoms for shuffling

    try:
        error_times, avg_time = task_func(all_logs)
    except Exception:
        error_times, avg_time = None, None

    assert error_times is not None and avg_time is not None, "task_func raised an exception on valid input."
    assert isinstance(error_times, list)
    assert isinstance(avg_time, time)
    assert len(error_times) == 1, "Expected exactly one error time."
    assert error_times[0] == error_time, "Extracted error time does not match."
    assert avg_time == error_time, "Average time for a single error should be the error's time."


@settings(max_examples=50, deadline=None)
@given(
    common_time=time_strategy,
    num_errors=st.integers(1, 5), # At least one error
    other_logs=st.lists(
        log_line_strategy(level_strategy=st.sampled_from(['INFO', 'WARNING', 'DEBUG'])),
        min_size=0, max_size=5
    )
)
def test_multiple_errors_same_time(common_time, num_errors, other_logs):
    """
    SPEC BASIS: "calculate the average time of occurrence of errors."
    PROPERTY: If multiple error logs occur at the exact same time, the average time should be that common time.
    STRATEGY: Generate lists containing multiple 'ERROR' logs, all with the same timestamp, mixed with other log types.
              This tests the averaging logic for a simple, non-trivial case where all values are identical.
    """
    date_str = "2021-01-01"
    error_log_template = f"{date_str} {common_time.strftime('%H:%M:%S')} ERROR: Test error message {{}}"
    
    error_logs = [error_log_template.format(i) for i in range(num_errors)]
    
    all_logs = other_logs + error_logs
    st.randoms().shuffle(all_logs) # Use Hypothesis's randoms for shuffling

    try:
        error_times, avg_time = task_func(all_logs)
    except Exception:
        error_times, avg_time = None, None

    assert error_times is not None and avg_time is not None, "task_func raised an exception on valid input."
    assert isinstance(error_times, list)
    assert isinstance(avg_time, time)
    assert len(error_times) == num_errors, "Expected correct number of error times."
    assert all(t == common_time for t in error_times), "All extracted error times should match the common time."
    assert avg_time == common_time, "Average time for identical error times should be that common time."


@settings(max_examples=50, deadline=None)
@given(
    error_times_list=st.lists(time_strategy, min_size=1, max_size=5),
    other_logs=st.lists(
        log_line_strategy(level_strategy=st.sampled_from(['INFO', 'WARNING', 'DEBUG'])),
        min_size=0, max_size=5
    )
)
def test_average_time_metamorphic_shift(error_times_list, other_logs):
    """
    SPEC BASIS: "calculate the average time of occurrence of errors."
    PROPERTY: If all error times are shifted by a constant duration (e.g., +1 hour), the average time should also shift by that duration (modulo 24 hours).
              This is a metamorphic property checking the robustness of the averaging logic.
    STRATEGY: Generate a set of error times. Calculate the expected average. Then, create a new set of logs where all error times are shifted.
              Verify that the new average is also shifted.
    """
    date_str = "2021-01-01"

    def time_to_seconds(t: time) -> int:
        return t.hour * 3600 + t.minute * 60 + t.second

    def seconds_to_time(s: int) -> time:
        s %= (24 * 3600) # Ensure it wraps around midnight
        h = s // 3600
        s %= 3600
        m = s // 60
        s %= 60
        return time(h, m, s)

    # Calculate expected average for original times
    total_seconds_original = sum(time_to_seconds(t) for t in error_times_list)
    avg_seconds_original = total_seconds_original // len(error_times_list)
    expected_avg_time_original = seconds_to_time(avg_seconds_original)

    # Construct original logs
    original_error_logs = [
        f"{date_str} {t.strftime('%H:%M:%S')} ERROR: Original error {i}"
        for i, t in enumerate(error_times_list)
    ]
    all_original_logs = other_logs + original_error_logs
    st.randoms().shuffle(all_original_logs)

    try:
        _, actual_avg_time_original = task_func(all_original_logs)
    except Exception:
        actual_avg_time_original = None

    assert actual_avg_time_original is not None, "task_func raised an exception for original logs."
    assert actual_avg_time_original == expected_avg_time_original, \
        f"Original average time mismatch: Expected {expected_avg_time_original}, Got {actual_avg_time_original}"

    # Metamorphic transformation: shift all times by a constant amount (e.g., 1 hour = 3600 seconds)
    shift_seconds = 3600 # 1 hour
    shifted_error_times_list = [
        seconds_to_time(time_to_seconds(t) + shift_seconds)
        for t in error_times_list
    ]
    
    # Calculate expected average for shifted times
    total_seconds_shifted = sum(time_to_seconds(t) for t in shifted_error_times_list)
    avg_seconds_shifted = total_seconds_shifted // len(shifted_error_times_list)
    expected_avg_time_shifted = seconds_to_time(avg_seconds_shifted)

    # Construct shifted logs
    shifted_error_logs = [
        f"{date_str} {t.strftime('%H:%M:%S')} ERROR: Shifted error {i}"
        for i, t in enumerate(shifted_error_times_list)
    ]
    all_shifted_logs = other_logs + shifted_error_logs
    st.randoms().shuffle(all_shifted_logs)

    try:
        _, actual_avg_time_shifted = task_func(all_shifted_logs)
    except Exception:
        actual_avg_time_shifted = None

    assert actual_avg_time_shifted is not None, "task_func raised an exception for shifted logs."
    assert actual_avg_time_shifted == expected_avg_time_shifted, \
        f"Shifted average time mismatch: Expected {expected_avg_time_shifted}, Got {actual_avg_time_shifted}"

    # Verify the metamorphic relation: the average of shifted times should be the shifted average of original times
    expected_metamorphic_avg = seconds_to_time(time_to_seconds(expected_avg_time_original) + shift_seconds)
    assert actual_avg_time_shifted == expected_metamorphic_avg, \
        f"Metamorphic relation failed: Shifted average ({actual_avg_time_shifted}) " \
        f"does not match shifted original average ({expected_metamorphic_avg})"