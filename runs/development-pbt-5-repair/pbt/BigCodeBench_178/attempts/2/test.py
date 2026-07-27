from candidate import task_func
from hypothesis import given, settings, strategies as st
import json
import re

# Constants from the problem description
IP_REGEX = r'[0-9]+(?:\.[0-9]+){3}'

# Strategy for generating valid IP address components (one or more digits)
# The regex allows numbers like '0', '00', '123', '9999'.
# Max size 3 is chosen to keep generated IPs reasonably short, as per problem constraints.
st_ip_component = st.text(st.just('0123456789'), min_size=1, max_size=3)

# Strategy for generating IP addresses that match IP_REGEX
st_valid_ip_address_format = st.builds(
    lambda c1, c2, c3, c4: f"{c1}.{c2}.{c3}.{c4}",
    c1=st_ip_component,
    c2=st_ip_component,
    c3=st_ip_component,
    c4=st_ip_component
)

# Strategy for generating IP addresses that do NOT match IP_REGEX
# These should trigger the 'Invalid IP address received' return.
st_invalid_ip_address_format = st.one_of(
    # Too few segments (e.g., "1.2.3")
    st.builds(lambda c1, c2, c3: f"{c1}.{c2}.{c3}", c1=st_ip_component, c2=st_ip_component, c3=st_ip_component),
    # Too many segments (e.g., "1.2.3.4.5")
    st.builds(lambda c1, c2, c3, c4, c5: f"{c1}.{c2}.{c3}.{c4}.{c5}",
              c1=st_ip_component, c2=st_ip_component, c3=st_ip_component, c4=st_ip_component, c5=st_ip_component),
    # Missing a segment (e.g., "1.2..4") - not strictly covered by the regex, but a common invalid format
    st.builds(lambda c1, c2, c4: f"{c1}.{c2}..{c4}", c1=st_ip_component, c2=st_ip_component, c4=st_ip_component),
    # Non-digit characters in a segment (e.g., "1.a.3.4")
    # st.characters(blacklist_categories=('Nd',)) generates characters that are not digits.
    st.builds(lambda c1, c2, c3, c4: f"{c1}.{c2}.{c3}.{c4}",
              c1=st_ip_component,
              c2=st.text(st.characters(blacklist_categories=('Nd',)), min_size=1, max_size=3),
              c3=st_ip_component,
              c4=st_ip_component),
    # Empty string for IP
    st.just(""),
    # IP with leading/trailing dots or multiple dots
    st.just(".1.2.3.4"),
    st.just("1.2.3.4."),
    st.just("1..2.3.4"),
    # Strings that are just digits but not enough segments (e.g., "123")
    st.text(st.just('0123456789'), min_size=1, max_size=12).filter(lambda s: '.' not in s or s.count('.') != 3)
)

# Strategy for generating JSON strings with an 'ip' key and a string value.
# The problem implies the input is always valid JSON with an 'ip' key.
def st_json_with_ip_value(ip_value_strategy):
    return st.builds(
        lambda ip_val: json.dumps({"ip": ip_val}),
        ip_val=ip_value_strategy
    )

# Strategy for generating arbitrary strings that are guaranteed not to match IP_REGEX.
# This is achieved by generating strings that contain characters not allowed by IP_REGEX
# (i.e., not digits and not dots), or strings that are clearly malformed.
st_arbitrary_non_ip_string = st.one_of(
    # Strings containing characters other than digits or dots
    st.text(st.characters(blacklist_characters='0123456789.'), min_size=1, max_size=12),
    # Strings that are just digits but too short or too long to form 4 segments
    st.text(st.just('0123456789'), min_size=1, max_size=12),
    # Empty string
    st.just(""),
    # Strings with only dots
    st.text(st.just('.'), min_size=1, max_size=12),
    # Strings with mixed digits and dots but clearly not IP format (e.g., "1.2.3", "1.2.3.4.5")
    st_invalid_ip_address_format # Re-use the structured invalid IP strategy
)


@settings(max_examples=50, deadline=None)
@given(ip_address=st.just('{"ip": "192.168.1.1"}'))
def test_example_case(ip_address):
    """
    SPEC BASIS: Example: >>> ip_address = '{"ip": "192.168.1.1"}' >>> task_func(ip_address) '192.168.1.1'
    PROPERTY: The function correctly processes the exact example input provided in the problem description.
    """
    assert task_func(ip_address) == '192.168.1.1'

@settings(max_examples=50, deadline=None)
@given(ip_address=st_json_with_ip_value(st_valid_ip_address_format))
def test_valid_ip_address_extraction(ip_address):
    """
    SPEC BASIS: "Get the public IP address from a JSON response containing the IP address."
                "The function needs to check whether the provided IP address is valid."
    PROPERTY: For any valid JSON string containing an 'ip' key whose value matches IP_REGEX,
              the function returns that IP address string.
    """
    # Extract the expected IP address from the JSON string
    parsed_json = json.loads(ip_address)
    expected_ip = parsed_json["ip"]

    # Verify that the generated IP actually matches the regex, as per the problem's definition of "valid"
    assert re.fullmatch(IP_REGEX, expected_ip) is not None

    assert task_func(ip_address) == expected_ip

@settings(max_examples=50, deadline=None)
@given(ip_address=st_json_with_ip_value(st_invalid_ip_address_format))
def test_invalid_ip_address_format_returns_error_message(ip_address):
    """
    SPEC BASIS: "If the IP address is not valid, the function will return 'Invalid IP address received'."
    PROPERTY: For any valid JSON string containing an 'ip' key whose value does NOT match IP_REGEX
              (specifically, structured invalid formats), the function returns the specific error message
              'Invalid IP address received'.
    """
    # Extract the IP address from the JSON string to verify it's indeed invalid by regex
    parsed_json = json.loads(ip_address)
    invalid_ip = parsed_json["ip"]

    # Verify that the generated IP actually does NOT match the regex
    assert re.fullmatch(IP_REGEX, invalid_ip) is None

    assert task_func(ip_address) == 'Invalid IP address received'

@settings(max_examples=50, deadline=None)
@given(ip_address=st_json_with_ip_value(st_arbitrary_non_ip_string))
def test_arbitrary_invalid_ip_string_returns_error_message(ip_address):
    """
    SPEC BASIS: "If the IP address is not valid, the function will return 'Invalid IP address received'."
    PROPERTY: For any valid JSON string containing an 'ip' key whose value is an arbitrary string that
              does not match IP_REGEX, the function returns the specific error message 'Invalid IP address received'.
              This covers cases beyond typical IP format errors.
    """
    parsed_json = json.loads(ip_address)
    invalid_ip_string = parsed_json["ip"]

    # Ensure the generated string is indeed not a valid IP according to the regex
    assert re.fullmatch(IP_REGEX, invalid_ip_string) is None

    assert task_func(ip_address) == 'Invalid IP address received'