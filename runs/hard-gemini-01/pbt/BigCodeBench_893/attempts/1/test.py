import re
from datetime import time, datetime, timedelta
from hypothesis import given, settings, strategies as st

from candidate import task_func

# SEARCH PLAN:
# - Empty input or no error logs: check for empty list and None average.
# - Single error log: verify the example behavior and direct mapping.
# - Multiple error logs: check average time falls within min/max bounds (metamorphic).
# - Order preservation: ensure the list of error times maintains input order.


# Helper strategy for generating valid log lines
@st.composite
def log_line_strategy(draw):
    year = draw(st.integers(2000, 2023))
    month = draw(st.integers(1, 12))
    day = draw(st.integers(1, 28))  # Avoid month-end complexities
    hour = draw(st.integers(0, 23))
    minute = draw(st.integers(0, 59))
    second = draw(st.integers(0, 59))

    timestamp = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"

    level = draw(st.sampled_from(["INFO", "WARNING", "ERROR", "DEBUG"]))
    message = draw(st.text(st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=10))

    return f"{timestamp} {level}: {message}"

# Strategy for generating log lines specifically with an ERROR level
@st.composite
def error_log_line_strategy(draw):
    year = draw(st.integers(2000, 2023))
    month = draw(st.integers(1, 12))
    day = draw(st.integers(1, 28))
    hour = draw(st.integers(0, 23))
    minute = draw(st.integers(0, 59))
    second = draw(st.integers(0, 59))

    timestamp = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
    message = draw(st.text(st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=10))

    return f"{timestamp} ERROR: {message}", time(hour, minute, second)

# Strategy for generating log lines specifically with a non-ERROR level
@st.composite
def non_error_log_line_strategy(draw):
    year = draw(st.integers(2000, 2023))
    month = draw(st.integers(1, 12))
    day = draw(st.integers(1, 28))
    hour = draw(st.integers(0, 23))
    minute = draw(st.integers(0, 59))
    second = draw(st.integers(0, 59))

    timestamp = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
    level = draw(st.sampled_from(["INFO", "WARNING", "DEBUG"]))
    message = draw(st.text(st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=10))

    return f"{timestamp} {level}: {message}"


@settings(max_examples=50, deadline=None)
@given(logs=st.one_of(
    st.just([]),
    st.lists(non_error_log_line_strategy(), min_size=1, max_size=12)
))
def test_no_errors_returns_empty_list_and_none_average(logs):
    """
    SPEC BASIS: Implicit. What happens when no errors are found?
    PROPERTY: If no "ERROR" logs are present, the first return value (list of error times) must be empty.
              The second return value (average time) must be `None`.
    STRATEGY: Generate lists of logs that are empty, or contain only "INFO", "WARNING", or other non-"ERROR" levels.
    """
    try:
        error_times, avg_time = task_func(logs)
    except Exception:
        error_times, avg_time = None, None

    assert error_times is not None, "Function raised an exception or returned None for error_times"
    assert avg_time is not None, "Function raised an exception or returned None for avg_time"

    assert error_times == [], "Expected an empty list of error times when no errors are present"
    assert avg_time is None, "Expected average time to be None when no errors are present"


@settings(max_examples=50, deadline=None)
@given(
    error_log_data=error_log_line_strategy(),
    other_logs=st.lists(non_error_log_line_strategy(), min_size=0, max_size=11)
)
def test_single_error_log_matches_example_behavior(error_log_data, other_logs):
    """
    SPEC BASIS: "Example: ([datetime.time(9, 45)], datetime.time(9, 45))"
    PROPERTY: If there is exactly one "ERROR" log, the list of error times should contain only that time,
              and the average time should be exactly that time.
    STRATEGY: Generate lists with exactly one "ERROR" log, potentially mixed with other non-error logs.
    """
    error_log_str, expected_time = error_log_data
    
    # Insert the error log at a random position to ensure robustness
    all_logs = other_logs + [error_log_str]
    st.randoms().shuffle(all_logs) # Use st.randoms() for shuffling within Hypothesis context

    # Ensure the total list size is within limits
    if len(all_logs) > 12:
        all_logs = all_logs[:12]

    try:
        error_times, avg_time = task_func(all_logs)
    except Exception:
        error_times, avg_time = None, None

    assert error_times is not None, "Function raised an exception or returned None for error_times"
    assert avg_time is not None, "Function raised an exception or returned None for avg_time"

    assert len(error_times) == 1, f"Expected 1 error time, got {len(error_times)}"
    assert error_times[0] == expected_time, f"Expected error time {expected_time}, got {error_times[0]}"
    assert avg_time == expected_time, f"Expected average time {expected_time}, got {avg_time}"


@settings(max_examples=50, deadline=None)
@given(
    error_logs_with_times=st.lists(error_log_line_strategy(), min_size=1, max_size=12),
    non_error_logs=st.lists(non_error_log_line_strategy(), min_size=0, max_size=12)
)
def test_average_time_is_within_min_max_bounds(error_logs_with_times, non_error_logs):
    """
    SPEC BASIS: "calculate the average time of occurrence of errors."
    PROPERTY: If errors occur, the calculated average time must be between the minimum and maximum error times (inclusive).
              This is a metamorphic property that checks the correctness of the average calculation without re-implementing it.
    STRATEGY: Generate lists with multiple "ERROR" logs at various times, mixed with non-error logs.
    """
    error_log_strings = [log_str for log_str, _ in error_logs_with_times]
    expected_times = [t for _, t in error_logs_with_times]

    all_logs = error_log_strings + non_error_logs
    st.randoms().shuffle(all_logs) # Shuffle to mix error and non-error logs

    # Ensure the total list size is within limits
    if len(all_logs) > 12:
        all_logs = all_logs[:12]

    # Filter out logs that are not errors or are beyond the 12-element limit
    # This ensures our expected_times correspond to what task_func will actually process
    processed_error_times = []
    for log_line in all_logs:
        match = re.search(r'(\d{2}:\d{2}:\d{2}) ERROR:', log_line)
        if match:
            time_str = match.group(1)
            h, m, s = map(int, time_str.split(':'))
            processed_error_times.append(time(h, m, s))

    if not processed_error_times:
        # This case should be covered by test_no_errors_returns_empty_list_and_none_average,
        # but if due to shuffling/truncation we end up with no errors, we skip this assertion.
        # Hypothesis will try other examples.
        return

    min_expected_time = min(processed_error_times)
    max_expected_time = max(processed_error_times)

    try:
        error_times_result, avg_time = task_func(all_logs)
    except Exception:
        error_times_result, avg_time = None, None

    assert error_times_result is not None, "Function raised an exception or returned None for error_times_result"
    assert avg_time is not None, "Function raised an exception or returned None for avg_time"

    assert min_expected_time <= avg_time <= max_expected_time, \
        f"Average time {avg_time} not within expected range [{min_expected_time}, {max_expected_time}]"


@settings(max_examples=50, deadline=None)
@given(
    error_logs_with_times=st.lists(error_log_line_strategy(), min_size=1, max_size=12),
    non_error_logs=st.lists(non_error_log_line_strategy(), min_size=0, max_size=12)
)
def test_error_times_list_preserves_order(error_logs_with_times, non_error_logs):
    """
    SPEC BASIS: The example shows the error time `datetime.time(9, 45)` appearing in the output list
                `[datetime.time(9, 45)]` in the order it appeared in the input. This is a standard expectation
                for log processing.
    PROPERTY: The list of error times returned must preserve the original order of occurrence of "ERROR" logs
              in the input list.
    STRATEGY: Generate lists with multiple "ERROR" logs at different times, mixed with non-error logs,
              and verify the order of the extracted error times.
    """
    # Combine and shuffle logs to create a realistic input scenario
    combined_logs_data = []
    for log_str, time_obj in error_logs_with_times:
        combined_logs_data.append((log_str, time_obj, True)) # True indicates an error log
    for log_str in non_error_logs:
        combined_logs_data.append((log_str, None, False)) # False indicates a non-error log

    st.randoms().shuffle(combined_logs_data)

    # Ensure the total list size is within limits
    if len(combined_logs_data) > 12:
        combined_logs_data = combined_logs_data[:12]

    input_logs = [item[0] for item in combined_logs_data]
    
    # Manually extract expected ordered error times from the *shuffled and truncated* input_logs
    expected_ordered_error_times = []
    for log_line in input_logs:
        match = re.search(r'(\d{2}:\d{2}:\d{2}) ERROR:', log_line)
        if match:
            time_str = match.group(1)
            h, m, s = map(int, time_str.split(':'))
            expected_ordered_error_times.append(time(h, m, s))

    if not expected_ordered_error_times:
        # If no errors are present after shuffling/truncation, this test is not applicable.
        # It's covered by test_no_errors_returns_empty_list_and_none_average.
        return

    try:
        actual_error_times, _ = task_func(input_logs)
    except Exception:
        actual_error_times = None

    assert actual_error_times is not None, "Function raised an exception or returned None for actual_error_times"
    assert actual_error_times == expected_ordered_error_times, \
        f"Order of error times not preserved. Expected {expected_ordered_error_times}, got {actual_error_times}"