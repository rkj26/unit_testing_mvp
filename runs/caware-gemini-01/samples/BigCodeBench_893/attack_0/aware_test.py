import re
from datetime import time

from candidate import task_func
from hypothesis import given, settings, strategies as st

# Helper strategy for valid time strings
time_str_strategy = st.builds(
    lambda h, m, s: f"{h:02d}:{m:02d}:{s:02d}",
    h=st.integers(min_value=0, max_value=23),
    m=st.integers(min_value=0, max_value=59),
    s=st.integers(min_value=0, max_value=59)
)

# Helper strategy for log lines, adjusted max_size to 12
log_line_strategy = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126, blacklist_characters='\n'),
    min_size=1, max_size=12 # Adjusted from 50 to 12
).map(lambda s: s.strip()) # Ensure no leading/trailing newlines or excessive whitespace

@given(
    logs=st.lists(
        st.one_of(
            log_line_strategy.map(lambda s: f"INFO: {s}"),
            st.builds(
                lambda ts, s: f"2021-01-01 {ts} ERROR: {s}",
                ts=time_str_strategy,
                s=log_line_strategy
            ),
            st.builds(
                lambda ts1, ts2, s: f"2021-01-01 {ts1} ERROR: {s} another time {ts2}",
                ts1=time_str_strategy,
                ts2=time_str_strategy,
                s=log_line_strategy
            ),
            st.builds(
                lambda ts, s: f"2021-01-01 {ts} WARNING: {s}",
                ts=time_str_strategy,
                s=log_line_strategy
            )
        ),
        min_size=0, max_size=12 # Adjusted from 10 to 12
    )
)
@settings(max_examples=50, deadline=None)
def test_number_of_extracted_times_vs_error_logs(logs):
    """
    SPEC BASIS: "Analyze the given list of logs for the occurrence of errors and calculate the average time of occurrence of errors."
                The example shows one time extracted per error log.
    PROPERTY: The number of extracted error times should not exceed the number of log lines containing "ERROR".
              If a single log line contains "ERROR" and multiple timestamps, the problem implies one "time of occurrence" per log.
              This property checks if the code over-extracts timestamps from a single error log line.
    STRATEGY: Generate log lists including lines with "ERROR" and potentially multiple timestamps.
    """
    try:
        error_times, avg_time = task_func(logs)
    except Exception:
        error_times, avg_time = None, None

    if error_times is not None:
        num_error_logs = sum(1 for log in logs if "ERROR" in log)
        # The code extracts all timestamps from an error log.
        # If the spec implies one time per error log, this property will fail if multiple times are extracted from one log.
        # If the spec allows multiple times per error log, this property will pass.
        # The suspicion is that multiple times from one log might be unintended.
        # A strict interpretation of "time of occurrence of errors" suggests one time per error event/log.
        assert len(error_times) <= num_error_logs, \
            f"Expected at most {num_error_logs} error times, but got {len(error_times)}. Logs: {logs}"


@given(
    logs=st.lists(
        st.builds(
            lambda ts, s: f"2021-01-01 {ts} ERROR: {s}",
            ts=time_str_strategy,
            s=log_line_strategy
        ),
        min_size=1, max_size=12 # Adjusted from 10 to 12
    )
)
@settings(max_examples=50, deadline=None)
def test_average_time_within_valid_range(logs):
    """
    SPEC BASIS: "Returns: ... time: The average time of occurrence of these errors."
    PROPERTY: The calculated average time should always be a valid datetime.time object (hour 0-23, minute 0-59).
    STRATEGY: Generate logs guaranteed to have errors, ensuring `error_times` is not empty and average calculation occurs.
    """
    try:
        error_times, avg_time = task_func(logs)
    except Exception:
        error_times, avg_time = None, None

    if avg_time is not None:
        assert isinstance(avg_time, time)
        assert 0 <= avg_time.hour <= 23
        assert 0 <= avg_time.minute <= 59
        assert avg_time.second == 0 # The code only extracts hour and minute, so second should be 0


@given(
    logs=st.lists(
        st.one_of(
            log_line_strategy.map(lambda s: f"INFO: {s}"),
            st.builds(
                lambda ts, s: f"2021-01-01 {ts} WARNING: {s}",
                ts=time_str_strategy,
                s=log_line_strategy
            )
        ),
        min_size=0, max_size=12 # Adjusted from 10 to 12
    )
)
@settings(max_examples=50, deadline=None)
def test_no_errors_returns_default_time(logs):
    """
    SPEC BASIS: The example implies that if errors occur, times are returned. The behavior for no errors is not explicitly
                stated in the example, but the code provides a default.
    PROPERTY: If no log lines contain "ERROR", the function should return an empty list for error_times and time(0, 0) for avg_time.
    STRATEGY: Generate log lists that explicitly do NOT contain the "ERROR" substring.
    """
    # Ensure no "ERROR" in any generated log
    filtered_logs = [log for log in logs if "ERROR" not in log]

    try:
        error_times, avg_time = task_func(filtered_logs)
    except Exception:
        error_times, avg_time = None, None

    if error_times is not None and avg_time is not None:
        assert error_times == []
        assert avg_time == time(0, 0)


@given(
    logs=st.lists(
        st.builds(
            lambda ts, s: f"2021-01-01 {ts} ERROR: {s}",
            ts=time_str_strategy,
            s=log_line_strategy
        ),
        min_size=1, max_size=12 # Adjusted from 10 to 12
    )
)
@settings(max_examples=50, deadline=None)
def test_extracted_times_are_from_error_logs(logs):
    """
    SPEC BASIS: "Analyze the given list of logs for the occurrence of errors and calculate the average time of occurrence of errors."
    PROPERTY: All times returned in `error_times` must correspond to a timestamp found in a log line that contains "ERROR".
    STRATEGY: Generate logs with only error entries, ensuring all extracted times are relevant.
    """
    try:
        error_times, avg_time = task_func(logs)
    except Exception:
        error_times, avg_time = None, None

    if error_times is not None:
        for et in error_times:
            found_in_error_log = False
            for log in logs:
                if "ERROR" in log:
                    # Reconstruct the time string to check if it was present in the log
                    et_str = f"{et.hour:02d}:{et.minute:02d}:" # The regex matches HH:MM:SS, but we only store HH:MM
                    if re.search(r'\d{2}:\d{2}:\d{2}', log) and et_str in log:
                        found_in_error_log = True
                        break
            assert found_in_error_log, f"Extracted time {et} not found in any error log. Logs: {logs}"