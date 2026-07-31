from candidate import task_func
from hypothesis import given, settings, strategies as st
from datetime import time
import re

@st.composite
def log_strategy(draw):
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    second = draw(st.integers(min_value=0, max_value=59))
    
    # Generate a base log string that might or might not contain "ERROR"
    log_parts = draw(st.lists(st.text(st.characters(blacklist_categories=('Cs',)), min_size=1, max_size=10), min_size=1, max_size=5))
    base_log = " ".join(log_parts)

    # Decide if it's an error log and where to insert "ERROR" and time
    is_error = draw(st.booleans())
    
    if is_error:
        error_keyword = "ERROR"
        time_str = f"{hour:02d}:{minute:02d}:{second:02d}"
        
        # Insert time and ERROR at random positions
        insert_pos_error = draw(st.integers(min_value=0, max_value=len(base_log)))
        insert_pos_time = draw(st.integers(min_value=0, max_value=len(base_log) + len(error_keyword) + 1)) # +1 for space
        
        log_with_error = base_log[:insert_pos_error] + error_keyword + " " + base_log[insert_pos_error:]
        final_log = log_with_error[:insert_pos_time] + time_str + " " + log_with_error[insert_pos_time:]
        
        return final_log, True, time(hour, minute)
    else:
        # Ensure non-error logs don't accidentally contain "ERROR" or a time pattern that would be parsed
        # This is a simplification for the strategy, focusing on clear non-error logs
        return base_log.replace("ERROR", "INFO").replace(":", "-"), False, None

@st.composite
def logs_with_specific_error_time(draw, target_hour, target_minute):
    num_errors = draw(st.integers(min_value=1, max_value=10))
    
    logs = []
    for _ in range(num_errors):
        second = draw(st.integers(min_value=0, max_value=59))
        
        # Generate a log string with the specific error time
        prefix = draw(st.text(st.characters(blacklist_categories=('Cs',)), min_size=1, max_size=5))
        suffix = draw(st.text(st.characters(blacklist_categories=('Cs',)), min_size=1, max_size=5))
        
        log_str = f"{prefix} {target_hour:02d}:{target_minute:02d}:{second:02d} ERROR: {suffix}"
        logs.append(log_str)
    
    # Add some non-error logs to mix things up
    num_non_errors = draw(st.integers(min_value=0, max_value=5))
    for _ in range(num_non_errors):
        non_error_log = draw(st.text(st.characters(blacklist_categories=('Cs',)), min_size=5, max_size=20)).replace("ERROR", "INFO").replace(":", "-")
        logs.append(non_error_log)
        
    # No explicit shuffle needed, Hypothesis will generate diverse lists
    return logs

@settings(max_examples=50, deadline=None)
@given(
    logs=st.lists(
        st.text(
            st.characters(blacklist_categories=('Cs',)),
            min_size=10, max_size=50
        ).map(lambda s: s.replace("ERROR", "INFO").replace(":", "-")), # Ensure no accidental errors or times
        min_size=0, max_size=10
    )
)
def test_no_errors_returns_empty_list_and_midnight(logs):
    """
    SPEC BASIS: "If no errors occur, the list of error times should be empty and the average time should be 00:00." (Implicit from example and common sense for empty set)
                "Returns: - list: A list of times when errors occurred. - time: The average time of occurrence of these errors."
    PROPERTY: If the input logs contain no "ERROR" strings, the function should return an empty list of error times and datetime.time(0, 0) for the average.
    STRATEGY: Generate logs that explicitly do not contain the substring "ERROR".
    """
    try:
        error_times, avg_time = task_func(logs)
        assert error_times == []
        assert avg_time == time(0, 0)
    except Exception:
        assert False, "Function raised an unexpected exception for logs with no errors."

@settings(max_examples=50, deadline=None)
@given(
    hour=st.integers(min_value=0, max_value=23),
    minute=st.integers(min_value=0, max_value=59)
)
def test_all_error_times_are_identical_average_is_that_time(hour, minute):
    """
    SPEC BASIS: "calculate the average time of occurrence of errors." (General definition of average)
    PROPERTY: If all detected error times are identical, the calculated average time should be exactly that time.
    STRATEGY: Generate a list of logs where all "ERROR" entries contain the exact same HH:MM:SS time.
              This targets the arithmetic mean calculation to ensure it correctly handles identical values.
    """
    logs = logs_with_specific_error_time(target_hour=hour, target_minute=minute).example()
    
    try:
        error_times, avg_time = task_func(logs)
        
        # Filter out non-error logs from the generated list to get expected error_times
        expected_error_times = []
        for log_str in logs:
            if "ERROR" in log_str:
                match = re.search(r'(\d{2}):(\d{2}):(\d{2})', log_str)
                if match:
                    h, m, s = map(int, match.groups())
                    expected_error_times.append(time(h, m))
        
        # The candidate code only extracts hour and minute, so we compare based on that
        expected_error_times_hm = [time(t.hour, t.minute) for t in expected_error_times]

        assert all(t == time(hour, minute) for t in error_times)
        assert avg_time == time(hour, minute)
        assert len(error_times) == len(expected_error_times_hm) # Ensure all expected errors were found
        
    except Exception as e:
        assert False, f"Function raised an unexpected exception: {e}"

@settings(max_examples=50, deadline=None)
@given(
    logs_data=st.lists(log_strategy(), min_size=1, max_size=10)
)
def test_extracted_error_times_match_parsed_times(logs_data):
    """
    SPEC BASIS: "Returns: - list: A list of times when errors occurred."
    PROPERTY: The list of returned error times should exactly match the hour and minute components of times found in logs marked "ERROR".
    STRATEGY: Generate diverse logs, some with "ERROR" and valid times, some without.
              This targets the regex extraction and filtering logic.
    """
    logs = [log_str for log_str, _, _ in logs_data]
    
    try:
        actual_error_times, _ = task_func(logs)
        
        expected_error_times = []
        for log_str, is_error, parsed_time in logs_data:
            if is_error:
                # The candidate code uses re.search(r'(\d{2}):(\d{2}):\d{2}', log)
                # and appends time(hour, minute) if a match is found.
                # We need to simulate this exact parsing logic for expected_error_times.
                time_match = re.search(r'(\d{2}):(\d{2}):\d{2}', log_str)
                if time_match:
                    hour, minute = map(int, time_match.groups())
                    expected_error_times.append(time(hour, minute))
        
        # Sort both lists for consistent comparison, as order is not specified for the returned list
        actual_error_times.sort(key=lambda t: (t.hour, t.minute))
        expected_error_times.sort(key=lambda t: (t.hour, t.minute))
        
        assert actual_error_times == expected_error_times
    except Exception as e:
        assert False, f"Function raised an unexpected exception: {e}"

@settings(max_examples=50, deadline=None)
@given(
    logs_with_time=st.lists(
        st.text(st.characters(blacklist_categories=('Cs',)), min_size=10, max_size=20)
        .map(lambda s: f"2021-06-15 {st.integers(0,23).example():02d}:{st.integers(0,59).example():02d}:{st.integers(0,59).example():02d} ERROR: {s.replace(':', '').replace(' ', '')}"),
        min_size=1, max_size=5
    ),
    logs_no_time=st.lists(
        st.text(st.characters(blacklist_categories=('Cs',)), min_size=10, max_size=20)
        .map(lambda s: f"ERROR: {s.replace(':', '').replace(' ', '')}"), # Ensure no time pattern
        min_size=1, max_size=5
    )
)
def test_average_time_only_considers_parsable_error_times(logs_with_time, logs_no_time):
    """
    SPEC BASIS: "calculate the average time of occurrence of errors."
                "Returns: - list: A list of times when errors occurred. - time: The average time of occurrence of these errors."
                (Implies the average should be of the times in the returned list)
    PROPERTY: The calculated average time should be the arithmetic mean of the times actually present in the returned `error_times` list.
              Logs containing "ERROR" but no parsable time pattern should not influence the average calculation.
    STRATEGY: Generate logs that contain "ERROR" with valid HH:MM:SS times, and other logs that contain "ERROR" but deliberately lack the HH:MM:SS pattern.
              This targets the suspicious discrepancy between `error_count` and the number of times contributing to `total_time`.
    """
    all_logs = logs_with_time + logs_no_time
    # No explicit shuffle needed, Hypothesis will generate diverse lists

    try:
        actual_error_times, actual_avg_time = task_func(all_logs)
        
        # Manually calculate expected average based ONLY on times in actual_error_times
        total_minutes_expected_avg = 0
        if actual_error_times:
            for t in actual_error_times:
                total_minutes_expected_avg += t.hour * 60 + t.minute
            
            expected_avg_hour = (total_minutes_expected_avg // len(actual_error_times)) // 60
            expected_avg_minute = (total_minutes_expected_avg // len(actual_error_times)) % 60
            expected_avg_time = time(expected_avg_hour, expected_avg_minute)
        else:
            expected_avg_time = time(0, 0)

        assert actual_avg_time == expected_avg_time

    except Exception as e:
        assert False, f"Function raised an unexpected exception: {e}"