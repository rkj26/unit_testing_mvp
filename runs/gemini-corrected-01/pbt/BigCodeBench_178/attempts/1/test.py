from candidate import task_func
from hypothesis import given, settings, strategies as st
import json
import re

# Constants from the problem description
IP_REGEX = r'[0-9]+(?:\.[0-9]+){3}'

# Helper strategy for generating valid IP octets (1-3 digits)
# The problem's IP_REGEX allows any number of digits, but typical IPs have 1-3.
# To keep generated strings small and representative, we'll use 1-3 digits.
# The regex itself doesn't enforce 0-255, so we won't either for generation,
# but we'll ensure it matches the regex.
octet_strategy = st.text(st.characters(min_codepoint=ord('0'), max_codepoint=ord('9')), min_size=1, max_size=3)

# Strategy for generating valid IP addresses according to IP_REGEX
valid_ip_strategy = st.builds(
    lambda o1, o2, o3, o4: f"{o1}.{o2}.{o3}.{o4}",
    o1=octet_strategy,
    o2=octet_strategy,
    o3=octet_strategy,
    o4=octet_strategy
)

# Strategy for generating strings that are NOT valid IP addresses according to IP_REGEX
# This includes strings that are too short/long, contain non-digits, or wrong number of segments.
invalid_ip_format_strategy = st.one_of(
    st.text(st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=12).filter(
        lambda s: not re.fullmatch(IP_REGEX, s)
    ),
    st.builds(
        lambda s1, s2: f"{s1}.{s2}",
        s1=octet_strategy,
        s2=octet_strategy
    ), # Too few octets
    st.builds(
        lambda s1, s2, s3, s4, s5: f"{s1}.{s2}.{s3}.{s4}.{s5}",
        s1=octet_strategy,
        s2=octet_strategy,
        s3=octet_strategy,
        s4=octet_strategy,
        s5=octet_strategy
    ), # Too many octets
    st.text(st.characters(min_codepoint=ord('a'), max_codepoint=ord('z')), min_size=1, max_size=12) # Non-numeric
)

@given(ip_value=valid_ip_strategy)
@settings(max_examples=50, deadline=None)
def test_valid_ip_address_returns_ip(ip_value):
    """
    SPEC BASIS: "Example: >>> ip_address = '{"ip": "192.168.1.1"}' >>> task_func(ip_address) '192.168.1.1'"
    PROPERTY: For a valid JSON string containing a valid IP address, the function should return the IP address string.
    """
    json_input = json.dumps({"ip": ip_value})
    try:
        result = task_func(json_input)
    except Exception:
        result = None
    assert result == ip_value, f"Expected '{ip_value}', got '{result}' for input '{json_input}'"

@given(invalid_ip_value=invalid_ip_format_strategy)
@settings(max_examples=50, deadline=None)
def test_invalid_ip_format_returns_error_string(invalid_ip_value):
    """
    SPEC BASIS: "If the IP address is not valid, the function will return 'Invalid IP address received'."
    PROPERTY: If the JSON contains a string that does not match the IP_REGEX format, the function should return the specific error message.
    """
    json_input = json.dumps({"ip": invalid_ip_value})
    try:
        result = task_func(json_input)
    except Exception:
        result = None
    assert result == 'Invalid IP address received', f"Expected 'Invalid IP address received', got '{result}' for input '{json_input}'"

@given(
    ip_value=st.one_of(
        st.just("0.0.0.0"),
        st.just("255.255.255.255"),
        st.just("001.002.003.004")
    )
)
@settings(max_examples=50, deadline=None)
def test_ip_address_edge_cases_returns_ip(ip_value):
    """
    SPEC BASIS: "The function needs to check whether the provided IP address is valid." (implies using IP_REGEX)
    PROPERTY: IP addresses that are valid according to the IP_REGEX, including common edge cases like all zeros, all 255s, or leading zeros, should be returned correctly.
    """
    json_input = json.dumps({"ip": ip_value})
    try:
        result = task_func(json_input)
    except Exception:
        result = None
    assert result == ip_value, f"Expected '{ip_value}', got '{result}' for input '{json_input}'"

@given(
    non_string_ip_value=st.one_of(
        st.integers(),
        st.booleans(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.just(None),
        st.lists(st.integers(), max_size=3),
        st.dictionaries(st.text(max_size=5), st.integers(), max_size=3)
    )
)
@settings(max_examples=50, deadline=None)
def test_non_string_ip_value_returns_error_string(non_string_ip_value):
    """
    SPEC BASIS: "ip_address (str): JSON-formatted string containing the IP address." and "If the IP address is not valid, the function will return 'Invalid IP address received'."
    PROPERTY: If the value associated with the 'ip' key in the JSON is not a string, it should be considered an invalid IP address, and the function should return the specific error message.
    """
    json_input = json.dumps({"ip": non_string_ip_value})
    try:
        result = task_func(json_input)
    except Exception:
        result = None
    assert result == 'Invalid IP address received', f"Expected 'Invalid IP address received', got '{result}' for input '{json_input}'"