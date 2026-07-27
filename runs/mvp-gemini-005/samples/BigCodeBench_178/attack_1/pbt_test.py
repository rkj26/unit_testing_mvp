from candidate import task_func
from hypothesis import given, settings, strategies as st
import json
import re

# Constants from the problem description for validation within tests
IP_REGEX = r'[0-9]+(?:\.[0-9]+){3}'

# Helper strategy for generating valid IP address components (0-255)
# Note: The problem's IP_REGEX is more permissive, allowing numbers > 255.
# We will generate IPs that satisfy both the common understanding (0-255)
# and the problem's regex, and also IPs that satisfy only the problem's regex.
ip_component_st = st.integers(min_value=0, max_value=255).map(str)
permissive_ip_component_st = st.integers(min_value=0, max_value=999).map(str)

# Strategy for generating a "standard" valid IP address (0-255 range)
valid_ip_st = st.builds(
    lambda a, b, c, d: f"{a}.{b}.{c}.{d}",
    ip_component_st, ip_component_st, ip_component_st, ip_component_st
)

# Strategy for generating an IP address that matches IP_REGEX but might have components > 255
permissive_valid_ip_st = st.builds(
    lambda a, b, c, d: f"{a}.{b}.{c}.{d}",
    permissive_ip_component_st, permissive_ip_component_st,
    permissive_ip_component_st, permissive_ip_component_st
).filter(lambda ip: re.fullmatch(IP_REGEX, ip)) # Ensure it strictly matches the given regex

# Strategy for generating an invalid IP address string (not matching IP_REGEX)
invalid_ip_format_st = st.text(
    st.characters(min_codepoint=1, max_codepoint=127, blacklist_characters='\\'),
    min_size=1, max_size=12
).filter(lambda s: not re.fullmatch(IP_REGEX, s))

# Strategy for generating arbitrary JSON-compatible values for the 'ip' key
json_value_st = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False, allow_infinity=False),
    lambda children: st.lists(children, max_size=5) | st.dictionaries(st.text(min_size=1, max_size=5), children, max_size=5)
)

@given(ip_str=permissive_valid_ip_st)
@settings(max_examples=50, deadline=None)
def test_valid_ip_is_returned_correctly(ip_str):
    """
    Property: A valid IP address (matching IP_REGEX) embedded in a simple JSON
    should be returned exactly as is.
    """
    json_input = json.dumps({"ip": ip_str})
    result = task_func(json_input)
    assert result == ip_str, f"Expected {ip_str}, but got {result} for input {json_input}"

@given(ip_str=invalid_ip_format_st)
@settings(max_examples=50, deadline=None)
def test_invalid_ip_format_returns_error_message(ip_str):
    """
    Property: An IP address string that does not match IP_REGEX should result
    in the 'Invalid IP address received' message.
    """
    json_input = json.dumps({"ip": ip_str})
    result = task_func(json_input)
    assert result == 'Invalid IP address received', \
        f"Expected 'Invalid IP address received' for invalid IP format '{ip_str}', but got '{result}'"

@given(key=st.text(min_size=1, max_size=10).filter(lambda s: s != "ip"),
       ip_str=permissive_valid_ip_st)
@settings(max_examples=50, deadline=None)
def test_ip_key_is_case_sensitive_and_correctly_parsed(key, ip_str):
    """
    Property: The function should specifically look for the 'ip' key.
    If the key is different (e.g., 'IP', 'Ip', or some other key),
    it should be treated as if the 'ip' key is missing or invalid.
    """
    json_input = json.dumps({key: ip_str})
    result = task_func(json_input)
    # If 'ip' key is missing, the behavior is undefined by problem, but usually
    # it would lead to an error or 'Invalid IP address received' if the value
    # for the *actual* 'ip' key is implicitly null/missing.
    # Assuming it should lead to 'Invalid IP address received' if 'ip' key is not found.
    assert result == 'Invalid IP address received', \
        f"Expected 'Invalid IP address received' when key is '{key}' (not 'ip'), but got '{result}'"

@given(ip_value=json_value_st.filter(lambda v: not isinstance(v, str) or not re.fullmatch(IP_REGEX, v)))
@settings(max_examples=50, deadline=None)
def test_non_string_or_non_ip_regex_value_for_ip_key_returns_error(ip_value):
    """
    Property: If the value associated with the 'ip' key is not a string,
    or is a string but does not match IP_REGEX, it should return the error message.
    """
    json_input = json.dumps({"ip": ip_value})
    result = task_func(json_input)
    assert result == 'Invalid IP address received', \
        f"Expected 'Invalid IP address received' for non-string/non-IP_REGEX value '{ip_value}', but got '{result}'"

@given(data=st.dictionaries(st.text(min_size=1, max_size=5), json_value_st, max_size=5))
@settings(max_examples=50, deadline=None)
def test_json_with_missing_ip_key_returns_error(data):
    """
    Property: If the JSON input does not contain the 'ip' key at all,
    the function should return 'Invalid IP address received'.
    """
    # Ensure 'ip' key is not present in the generated dictionary
    data_without_ip = {k: v for k, v in data.items() if k != "ip"}
    json_input = json.dumps(data_without_ip)
    result = task_func(json_input)
    assert result == 'Invalid IP address received', \
        f"Expected 'Invalid IP address received' for JSON without 'ip' key, but got '{result}' for input {json_input}"

@given(s=st.text(st.characters(min_codepoint=1, max_codepoint=127), min_size=1, max_size=20)
          .filter(lambda s: not s.startswith('{') or not s.endswith('}')))
@settings(max_examples=50, deadline=None)
def test_malformed_json_input_returns_error(s):
    """
    Property: If the input string is not valid JSON, the function should
    handle the parsing error gracefully and return 'Invalid IP address received'.
    """
    try:
        result = task_func(s)
        assert result == 'Invalid IP address received', \
            f"Expected 'Invalid IP address received' for malformed JSON '{s}', but got '{result}'"
    except Exception as e:
        assert False, f"Function raised an unexpected exception {type(e).__name__}: {e} for malformed JSON '{s}'"

@given(ip_str=permissive_valid_ip_st)
@settings(max_examples=50, deadline=None)
def test_json_with_extra_fields_still_extracts_ip(ip_str):
    """
    Property: The presence of additional fields in the JSON should not prevent
    the correct extraction and validation of the 'ip' field.
    """
    extra_data = st.dictionaries(
        st.text(min_size=1, max_size=5).filter(lambda s: s != "ip"),
        json_value_st,
        min_size=1, max_size=5
    ).example() # Use example to get a concrete dictionary for merging

    full_json_dict = {"ip": ip_str, **extra_data}
    json_input = json.dumps(full_json_dict)
    result = task_func(json_input)
    assert result == ip_str, \
        f"Expected {ip_str} even with extra fields, but got {result} for input {json_input}"

@given(ip_str=permissive_valid_ip_st)
@settings(max_examples=50, deadline=None)
def test_ip_in_nested_structure_is_not_found(ip_str):
    """
    Property: The function should only look for the 'ip' key at the top level.
    If 'ip' is nested, it should be treated as if the 'ip' key is missing.
    """
    nested_json = json.dumps({"data": {"ip": ip_str}})
    result = task_func(nested_json)
    assert result == 'Invalid IP address received', \
        f"Expected 'Invalid IP address received' for nested IP, but got '{result}' for input {nested_json}"

@given(ip_str=st.text(min_size=0, max_size=0)) # Empty string
@settings(max_examples=50, deadline=None)
def test_empty_string_for_ip_key_returns_error(ip_str):
    """
    Property: An empty string as the value for the 'ip' key should be considered invalid.
    """
    json_input = json.dumps({"ip": ip_str})
    result = task_func(json_input)
    assert result == 'Invalid IP address received', \
        f"Expected 'Invalid IP address received' for empty IP string, but got '{result}'"

@given(ip_str=permissive_valid_ip_st)
@settings(max_examples=50, deadline=None)
def test_whitespace_around_json_is_handled(ip_str):
    """
    Property: Leading/trailing whitespace around the JSON string should be handled
    correctly by the JSON parser.
    """
    json_content = json.dumps({"ip": ip_str})
    whitespace_prefix = st.text(st.just(' '), min_size=1, max_size=5).example()
    whitespace_suffix = st.text(st.just(' '), min_size=1, max_size=5).example()
    json_input = f"{whitespace_prefix}{json_content}{whitespace_suffix}"
    result = task_func(json_input)
    assert result == ip_str, \
        f"Expected {ip_str} with whitespace around JSON, but got {result} for input '{json_input}'"