import datetime
import re
from collections import Counter
from hypothesis import given, settings, strategies as st
from candidate import task_func

# Helper to generate a log string
@st.composite
def _log_strategy(draw, level_strategy=st.sampled_from(["INFO", "WARNING", "ERROR", "DEBUG"]),
                 message_strategy=st.text(st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=20)):
    year = draw(st.integers(min_value=2000, max_value=2023))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=28)) # Avoid issues with month-end days
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    second = draw(st.integers(min_value=0, max_value=59))
    level = draw(level_strategy)
    message = draw(message_strategy)
    
    dt_str = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
    return f"{dt_str} {level}: {message}"

# Helper to calculate average time (oracle)
def _calculate_average_time_oracle(times: list[datetime.time]) -> datetime.time | None:
    if not times:
        return None
    
    total_seconds = 0
    for t in times:
        total_seconds += t.hour * 3600 + t.minute * 60 + t.second
    
    avg_seconds = total_seconds // len(times) # Integer division for seconds
    
    avg_hour = avg_seconds // 3600
    remaining_seconds = avg_seconds % 3600
    avg_minute = remaining_seconds // 60
    avg_second = remaining_seconds % 60
    
    return datetime.time(avg_hour, avg_minute, avg_second)

@settings(max_examples=50, deadline=None)
@given(logs=st.one_of(
    st.just([]), # Empty list
    st.lists(_log_strategy(level_strategy=st.sampled_from(["INFO", "WARNING", "DEBUG"])), min_size=1, max_size=12) # No error logs
))
def test_empty_or_no_error_logs(logs):
    """
    SPEC BASIS: "Analyze the given list of logs for the occurrence of errors and calculate the average time of occurrence of errors."
                The example implies an empty list of times if no errors, and the average time would then be undefined.
    PROPERTY: If no error logs are present, the list of error times should be empty, and the average time should be None.
    STRATEGY: Generate an empty list of logs or a list containing only non-ERROR logs. This targets the boundary case where no errors are found.
    """
    try:
        error_times, avg_time = task_func(logs)
    except Exception:
        error_times, avg_time = None, None
    
    assert error_times is not None, "task_func should return a list of times, not raise an exception for valid input."
    assert avg_time is not None or (not error_times and avg_time is None), "Average time should be None if no errors, otherwise a time object."
    
    assert error_times == []
    assert avg_time is None

@settings(max_examples=50, deadline=None)
@given(
    hour=st.integers(min_value=0, max_value=23),
    minute=st.integers(min_value=0, max_value=59),
    second=st.integers(min_value=0, max_value=59)
)
def test_single_error_log(hour, minute, second):
    """
    SPEC BASIS: Example: `([datetime.time(9, 45)], datetime.time(9, 45))` for a single error.
    PROPERTY: For a single error log, the returned list of times should contain exactly that time, and the average time should be that same time.
    STRATEGY: Generate a single log string with an "ERROR" level and a specific time. This covers the base case and matches the example.
    """
    expected_time = datetime.time(hour, minute, second)
    log_line = f"2023-01-01 {hour:02d}:{minute:02d}:{second:02d} ERROR: Test message"
    
    try:
        error_times, avg_time = task_func([log_line])
    except Exception:
        error_times, avg_time = None, None
    
    assert error_times is not None, "task_func should return a list of times, not raise an exception for valid input."
    assert avg_time is not None, "Average time should not be None for a single error."
    
    assert error_times == [expected_time]
    assert avg_time == expected_time

@settings(max_examples=50, deadline=None)
@given(
    times=st.lists(
        st.one_of(
            st.just(datetime.time(0, 0, 0)), # Boundary: start of day
            st.just(datetime.time(23, 59, 59)), # Boundary: end of day
            st.just(datetime.time(12, 0, 0)), # Mid-day
            st.times() # Random times
        ),
        min_size=2, max_size=12 # At least two times for averaging
    )
)
def test_multiple_errors_and_average_calculation(times):
    """
    SPEC BASIS: "calculate the average time of occurrence of these errors."
    PROPERTY: The returned list of error times should match the parsed times from error logs, and the calculated average time should be arithmetically correct.
    STRATEGY: Generate multiple error logs with diverse times, including boundary values (00:00:00, 23:59:59), to thoroughly test time parsing and average calculation.
              The oracle for average time is recomputed using the same logic.
    """
    logs = [f"2023-01-01 {t.hour:02d}:{t.minute:02d}:{t.second:02d} ERROR: Message {i}" for i, t in enumerate(times)]
    
    expected_error_times = sorted(times) # Order is not specified, so sort for comparison
    expected_avg_time = _calculate_average_time_oracle(times)
    
    try:
        error_times, avg_time = task_func(logs)
    except Exception:
        error_times, avg_time = None, None
    
    assert error_times is not None, "task_func should return a list of times, not raise an exception for valid input."
    assert avg_time is not None, "Average time should not be None for multiple errors."
    
    assert sorted(error_times) == expected_error_times
    assert avg_time == expected_avg_time

@settings(max_examples=50, deadline=None)
@given(
    valid_error_times=st.lists(st.times(), min_size=1, max_size=6),
    non_error_logs=st.lists(_log_strategy(level_strategy=st.sampled_from(["INFO", "WARNING", "DEBUG"])), min_size=0, max_size=6),
    malformed_logs=st.lists(
        st.one_of(
            st.text(min_size=1, max_size=50).filter(lambda s: not re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} (ERROR|INFO|WARNING|DEBUG): .*', s)),
            st.just("This is not a log line"),
            st.just("2023-01-01 10:00:00 ERROR No colon after level"),
            st.just("2023-01-01 10:00:00 ERROR: message with error in it"), # "ERROR" in message, not level
            st.just("2023-01-01 10:00:00 error: lowercase level") # lowercase "error"
        ),
        min_size=0, max_size=6
    )
)
def test_malformed_and_non_error_logs_are_ignored(valid_error_times, non_error_logs, malformed_logs):
    """
    SPEC BASIS: "Analyze the given list of logs for the occurrence of errors". The example shows "ERROR" as the level.
    PROPERTY: Only logs matching the expected "ERROR" format contribute to the results. Malformed logs or logs with other levels are ignored.
    STRATEGY: Construct a log list with a mix of valid "ERROR" logs, valid non-ERROR logs, and various malformed log strings.
              This tests the robustness of the log parsing and filtering logic against unexpected inputs.
    """
    error_logs = [f"2023-01-01 {t.hour:02d}:{t.minute:02d}:{t.second:02d} ERROR: Valid error {i}" for i, t in enumerate(valid_error_times)]
    
    all_logs = error_logs + non_error_logs + malformed_logs
    # Use a deterministic shuffle for reproducibility with Hypothesis
    # Note: st.randoms() is forbidden, but we can use a fixed seed for random.shuffle if needed,
    # or simply rely on Hypothesis's internal shuffling if the list is built with st.lists.
    # For this case, since we are concatenating lists, a simple list build with st.lists(st.one_of(...))
    # would be better, but for clarity of strategy, we'll keep it this way and acknowledge the shuffle limitation.
    # A better way would be to use st.lists(st.one_of(error_log_strategy, non_error_log_strategy, malformed_log_strategy))
    # to let Hypothesis handle the mixing. For now, we'll assume the order of concatenation is sufficient for mixing.
    
    expected_error_times = sorted(valid_error_times)
    expected_avg_time = _calculate_average_time_oracle(valid_error_times)
    
    try:
        error_times, avg_time = task_func(all_logs)
    except Exception:
        error_times, avg_time = None, None
    
    assert error_times is not None, "task_func should return a list of times, not raise an exception for valid input."
    assert avg_time is not None or (not expected_error_times and avg_time is None), "Average time should be None if no errors, otherwise a time object."
    
    assert sorted(error_times) == expected_error_times
    assert avg_time == expected_avg_time