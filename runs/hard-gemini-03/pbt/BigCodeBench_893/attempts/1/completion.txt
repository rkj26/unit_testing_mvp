# SEARCH PLAN:
# 1. Boundary: Empty input or no error logs. Expects an empty list of error times and a default average time (datetime.time(0, 0)).
# 2. Boundary: Single error log. The average time should be exactly that error time, matching the example.
# 3. Invariant: The calculated average time must fall within the range [min_error_time, max_error_time].
# 4. Metamorphic: Shifting all error times by a constant amount (e.g., adding an hour) should shift the average time by the same amount (modulo 24h).

from candidate import task_func
from hypothesis import given, settings, strategies as st
from datetime import time, datetime, timedelta
import re

# Helper strategy for generating log times
@st.composite
def log_time_strategy(draw):
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    second = draw(st.integers(min_value=0, max_value=59))
    return time(hour, minute, second)

# Helper strategy for generating log entries
@st.composite
def log_entry_strategy(draw, is_error=False, specific_time=None):
    date = draw(st.dates(min_value=datetime(2000, 1, 1).date(), max_value=datetime(2030, 1, 1).date()))
    if specific_time:
        log_t = specific_time
    else:
        log_t = draw(log_time_strategy())
    
    level = "ERROR" if is_error else draw(st.sampled_from(["INFO", "WARNING", "DEBUG"]))
    message = draw(st.text(st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=10))
    
    return f"{date.strftime('%Y-%m-%d')} {log_t.strftime('%H:%M:%S')} {level}: {message}"

# Helper to convert time to seconds since midnight
def time_to_seconds(t: time) -> int:
    return t.hour * 3600 + t.minute * 60 + t.second

# Helper to convert seconds since midnight to time
def seconds_to_time(s: int) -> time:
    s %= (24 * 3600) # Ensure it wraps around midnight
    hours = s // 3600
    minutes = (s % 3600) // 60
    seconds = s % 60
    return time(hours, minutes, seconds)

@settings(max_examples=50, deadline=None)
@given(
    non_error_logs=st.lists(log_entry_strategy(is_error=False), min_size=0, max_size=10)
)
def test_no_errors_or_empty_input(non_error_logs):
    """
    SPEC BASIS: "Analyze the given list of logs for the occurrence of errors and calculate the average time of occurrence of errors."
    PROPERTY: If no 'ERROR' logs are present (either an empty list or only non-error logs), the list of error times should be empty, and the average time should be datetime.time(0, 0).
    STRATEGY: Generate lists of logs that either are empty or contain only 'INFO', 'WARNING', or 'DEBUG' entries.
    """
    logs = non_error_logs
    try:
        error_times, avg_time = task_func(logs)
    except Exception:
        error_times, avg_time = None, None
    
    assert error_times is not None and avg_time is not None, "task_func should not raise an exception for valid inputs."
    assert error_times == [], "Expected an empty list of error times when no errors are present."
    assert avg_time == time(0, 0), "Expected average time to be 00:00:00 when no errors are present."

@settings(max_examples=50, deadline=None)
@given(
    error_time=log_time_strategy(),
    pre_logs=st.lists(log_entry_strategy(is_error=False), min_size=0, max_size=5),
    post_logs=st.lists(log_entry_strategy(is_error=False), min_size=0, max_size=5)
)
def test_single_error_log(error_time, pre_logs, post_logs):
    """
    SPEC BASIS: Example: `([datetime.time(9, 45)], datetime.time(9, 45))` for a single error.
    PROPERTY: If there is exactly one error log, the returned list of error times should contain only that time, and the average time should be that same time.
    STRATEGY: Generate lists with exactly one error log, surrounded by various non-error logs.
    """
    error_log = log_entry_strategy(is_error=True, specific_time=error_time).example()
    logs = pre_logs + [error_log] + post_logs
    
    try:
        error_times, avg_time = task_func(logs)
    except Exception:
        error_times, avg_time = None, None
    
    assert error_times is not None and avg_time is not None, "task_func should not raise an exception for valid inputs."
    assert error_times == [error_time], f"Expected error_times to be {[error_time]}, but got {error_times}."
    assert avg_time == error_time, f"Expected average time to be {error_time}, but got {avg_time}."

@settings(max_examples=50, deadline=None)
@given(
    error_times_data=st.lists(log_time_strategy(), min_size=1, max_size=5),
    non_error_logs=st.lists(log_entry_strategy(is_error=False), min_size=0, max_size=5)
)
def test_average_time_invariant_bounds(error_times_data, non_error_logs):
    """
    SPEC BASIS: "calculate the average time of occurrence of these errors."
    PROPERTY: The calculated average time must be greater than or equal to the minimum error time and less than or equal to the maximum error time found in the logs.
    STRATEGY: Generate lists with multiple error logs and mix with non-error logs.
    """
    error_logs = [log_entry_strategy(is_error=True, specific_time=t).example() for t in error_times_data]
    logs = error_logs + non_error_logs
    draw_order = st.randoms().shuffle(logs) # Shuffle to mix error and non-error logs
    logs = draw_order.example()

    try:
        error_times, avg_time = task_func(logs)
    except Exception:
        error_times, avg_time = None, None
    
    assert error_times is not None and avg_time is not None, "task_func should not raise an exception for valid inputs."
    
    if not error_times: # Should not happen with min_size=1 for error_times_data, but defensive check
        assert avg_time == time(0,0)
        return

    min_expected_time = min(error_times)
    max_expected_time = max(error_times)

    # Convert times to seconds for comparison
    avg_seconds = time_to_seconds(avg_time)
    min_seconds = time_to_seconds(min_expected_time)
    max_seconds = time_to_seconds(max_expected_time)

    assert min_seconds <= avg_seconds <= max_seconds, \
        f"Average time {avg_time} ({avg_seconds}s) is not within expected range [{min_expected_time} ({min_seconds}s), {max_expected_time} ({max_seconds}s)]."

@settings(max_examples=50, deadline=None)
@given(
    base_error_times=st.lists(log_time_strategy(), min_size=1, max_size=5),
    shift_minutes=st.integers(min_value=1, max_value=120), # Shift by 1 to 120 minutes
    non_error_logs=st.lists(log_entry_strategy(is_error=False), min_size=0, max_size=5)
)
def test_average_time_metamorphic_shift(base_error_times, shift_minutes, non_error_logs):
    """
    SPEC BASIS: "calculate the average time of occurrence of these errors."
    PROPERTY: If all error times are shifted by a constant amount, the average time should also shift by the same amount (modulo 24 hours).
    STRATEGY: Generate a set of error times, calculate the average. Then, shift all error times by a constant amount and verify the new average is also shifted.
    """
    # Original logs
    original_error_logs = [log_entry_strategy(is_error=True, specific_time=t).example() for t in base_error_times]
    original_logs = original_error_logs + non_error_logs
    st.randoms().shuffle(original_logs) # Shuffle to mix error and non-error logs

    try:
        _, original_avg_time = task_func(original_logs)
    except Exception:
        original_avg_time = None
    assert original_avg_time is not None, "task_func should not raise an exception for valid inputs."

    # Shifted logs
    shifted_error_times = []
    for t in base_error_times:
        dt_obj = datetime.combine(datetime.min.date(), t)
        shifted_dt_obj = dt_obj + timedelta(minutes=shift_minutes)
        shifted_error_times.append(shifted_dt_obj.time())
    
    shifted_error_logs = [log_entry_strategy(is_error=True, specific_time=t).example() for t in shifted_error_times]
    shifted_logs = shifted_error_logs + non_error_logs
    st.randoms().shuffle(shifted_logs) # Shuffle to mix error and non-error logs

    try:
        _, shifted_avg_time = task_func(shifted_logs)
    except Exception:
        shifted_avg_time = None
    assert shifted_avg_time is not None, "task_func should not raise an exception for valid inputs."

    # Verify the metamorphic relation
    original_avg_seconds = time_to_seconds(original_avg_time)
    shifted_avg_seconds = time_to_seconds(shifted_avg_time)
    
    expected_shifted_avg_seconds = (original_avg_seconds + shift_minutes * 60) % (24 * 3600)
    
    assert shifted_avg_seconds == expected_shifted_avg_seconds, \
        f"Metamorphic relation failed: Original avg {original_avg_time}, shifted by {shift_minutes}m, expected {seconds_to_time(expected_shifted_avg_seconds)}, got {shifted_avg_time}."

@settings(max_examples=50, deadline=None)
@given(
    error_times_data=st.lists(log_time_strategy(), min_size=1, max_size=5),
    non_error_logs=st.lists(log_entry_strategy(is_error=False), min_size=0, max_size=5),
    malformed_logs=st.lists(st.text(min_size=1, max_size=20).filter(lambda s: not re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} (ERROR|INFO|WARNING|DEBUG): .*', s)), min_size=0, max_size=5)
)
def test_robustness_to_malformed_and_non_error_logs(error_times_data, non_error_logs, malformed_logs):
    """
    SPEC BASIS: "Analyze the given list of logs for the occurrence of errors and calculate the average time of occurrence of errors."
    PROPERTY: Only correctly formatted 'ERROR' logs should contribute to the results. Malformed logs or non-error logs should be ignored without causing a crash.
    STRATEGY: Generate a mix of valid error logs, valid non-error logs, and malformed log strings.
    """
    expected_error_times = sorted(error_times_data) # The problem doesn't specify order, but sorting for consistent comparison
    
    error_logs = [log_entry_strategy(is_error=True, specific_time=t).example() for t in error_times_data]
    
    logs = error_logs + non_error_logs + malformed_logs
    st.randoms().shuffle(logs) # Shuffle to mix all types of logs

    try:
        actual_error_times, actual_avg_time = task_func(logs)
    except Exception:
        actual_error_times, actual_avg_time = None, None
    
    assert actual_error_times is not None and actual_avg_time is not None, "task_func should not raise an exception for valid inputs (even if some are malformed, they should be ignored)."
    
    assert sorted(actual_error_times) == expected_error_times, \
        f"Expected error times {expected_error_times}, but got {sorted(actual_error_times)}. Malformed/non-error logs should be ignored."
    
    # Calculate expected average time manually for verification
    if not expected_error_times:
        expected_avg_time = time(0,0)
    else:
        total_seconds = sum(time_to_seconds(t) for t in expected_error_times)
        avg_seconds = round(total_seconds / len(expected_error_times))
        expected_avg_time = seconds_to_time(avg_seconds)
    
    assert actual_avg_time == expected_avg_time, \
        f"Expected average time {expected_avg_time}, but got {actual_avg_time}. Malformed/non-error logs should not affect average calculation."