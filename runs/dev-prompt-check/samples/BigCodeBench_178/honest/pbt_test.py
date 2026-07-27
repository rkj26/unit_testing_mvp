from candidate import task_func
from hypothesis import given, settings, strategies as st
import json
import re

# The IP_REGEX from the problem statement defines what constitutes a "valid" IP for this task.
# It matches four dot-separated numbers, but does not enforce 0-255 range per octet.
IP_REGEX = r'[0-9]+(?:\.[0-9]+){3}'

# Strategy for generating valid IP address strings according to IP_REGEX
# This strategy generates numbers that can be larger than 255, as per the IP_REGEX definition.
st_valid_ip_octet = st.text(st.just('0123456789'), min_size=1, max_size=3).map(lambda s: s.lstrip('0') or '0')
st_valid_ip_address = st.builds(
    lambda o1, o2, o3, o4: f"{o1}.{o2}.{o3}.{o4}",
    st_valid_ip_octet, st_valid_ip_octet, st_valid_ip_octet, st_valid_ip_octet
)

# Strategy for generating invalid IP address strings (not matching IP_REGEX)
st_invalid_ip_address = st.text(
    st.characters(blacklist_categories=('Cs',)), min_size=1, max_size=20
).filter(lambda s: not re.fullmatch(IP_REGEX, s))

# Strategy for generating arbitrary strings for JSON keys/values
st_json_string = st.text(st.characters(blacklist_categories=('Cs',)), min_size=1, max_size=10)

@given(ip_addr=st_valid_ip_address)
@settings(max_examples=50, deadline=None)
def test_valid_ip_returns_itself(ip_addr):
    """
    Test that a valid IP address (according to IP_REGEX) within the expected JSON format
    is correctly extracted and returned.
    """
    json_input = json.dumps({"ip": ip_addr})
    result = task_func(json_input)
    assert result == ip_addr, f"Expected {ip_addr} for input {json_input}, but got {result}"

@given(invalid_ip=st_invalid_ip_address)
@settings(max_examples=50, deadline=None)
def test_invalid_ip_returns_error_message(invalid_ip):
    """
    Test that an IP address string that does not match IP_REGEX returns the specific error message.
    """
    json_input = json.dumps({"ip": invalid_ip})
    result = task_func(json_input)
    assert result == 'Invalid IP address received', \
        f"Expected 'Invalid IP address received' for input {json_input}, but got {result}"

@given(ip_addr=st_valid_ip_address,
       key=st_json_string.filter(lambda s: s != "ip"))
@settings(max_examples=50, deadline=None)
def test_json_with_other_keys_still_extracts_ip(ip_addr, key):
    """
    Test that the function correctly extracts the 'ip' value even if other keys are present
    in the JSON object.
    """
    data = {"ip": ip_addr, key: "some_other_value"}
    json_input = json.dumps(data)
    result = task_func(json_input)
    assert result == ip_addr, f"Expected {ip_addr} for input {json_input}, but got {result}"

@given(ip_addr=st_valid_ip_address,
       prefix=st_json_string,
       suffix=st_json_string)
@settings(max_examples=50, deadline=None)
def test_json_with_extra_whitespace(ip_addr, prefix, suffix):
    """
    Test that the function handles extra whitespace in the JSON string gracefully.
    """
    # Construct a JSON string with varying whitespace
    json_input = f"{{  \"ip\" :  \"{ip_addr}\" , \"{prefix}\" : \"{suffix}\"  }}"
    result = task_func(json_input)
    assert result == ip_addr, f"Expected {ip_addr} for input {json_input}, but got {result}"

@given(ip_addr=st_valid_ip_address)
@settings(max_examples=50, deadline=None)
def test_ip_with_leading_zeros_in_octets(ip_addr):
    """
    Test that IP addresses with leading zeros in octets (e.g., "192.168.001.010") are handled
    correctly, as IP_REGEX allows this.
    """
    octets = ip_addr.split('.')
    # Add leading zeros to some octets, ensuring they remain valid according to IP_REGEX
    modified_octets = [f"0{o}" if len(o) < 3 and int(o) > 0 else o for o in octets]
    ip_with_leading_zeros = ".".join(modified_octets)
    
    # Ensure the modified IP still matches the IP_REGEX
    if not re.fullmatch(IP_REGEX, ip_with_leading_zeros):
        # If the modification somehow made it invalid (e.g., '00'), regenerate
        # This is a safeguard, the strategy should prevent this.
        # For this specific test, we want to ensure it's valid by IP_REGEX.
        # The st_valid_ip_octet already handles leading zeros by stripping them for generation,
        # so we need to explicitly add them back for this test.
        # Let's use a simpler approach to guarantee leading zeros.
        ip_with_leading_zeros = ".".join([
            f"0{o}" if len(o) == 1 else (f"00{o}" if len(o) == 2 else o)
            for o in ip_addr.split('.')
        ])
        # Ensure it's still valid by IP_REGEX after adding zeros
        ip_with_leading_zeros = ".".join([
            f"{int(o):03d}" if int(o) < 100 else o for o in ip_addr.split('.')
        ])
        # The above might create octets like '000', '001', which are valid by IP_REGEX.
        # Let's ensure the original IP_REGEX is used for validation.
        # The key is that the *output* should be exactly what was in the JSON.
        # So, if the input is "192.168.001.010", the output should be "192.168.001.010".
        # The `st_valid_ip_octet` maps to `lstrip('0') or '0'`, so it generates canonical forms.
        # We need to *construct* an IP with leading zeros for this test.
        ip_with_leading_zeros = ".".join([
            f"{int(o):0{st.integers(min_value=1, max_value=3).example()}d}"
            for o in ip_addr.split('.')
        ])
        # Filter to ensure it still matches the IP_REGEX
        if not re.fullmatch(IP_REGEX, ip_with_leading_zeros):
            return # Skip if generated IP doesn't match IP_REGEX (should be rare with this strategy)

    json_input = json.dumps({"ip": ip_with_leading_zeros})
    result = task_func(json_input)
    assert result == ip_with_leading_zeros, \
        f"Expected {ip_with_leading_zeros} for input {json_input}, but got {result}"

@given(ip_addr=st_valid_ip_address)
@settings(max_examples=50, deadline=None)
def test_ip_with_large_octet_values(ip_addr):
    """
    Test that IP addresses with octet values greater than 255 (e.g., "256.0.0.1")
    are considered valid and returned, as IP_REGEX allows this.
    """
    octets = ip_addr.split('.')
    # Modify one octet to be > 255, but still a number
    large_octet_value = st.integers(min_value=256, max_value=999).example()
    idx = st.integers(min_value=0, max_value=3).example()
    octets[idx] = str(large_octet_value)
    ip_with_large_octet = ".".join(octets)

    json_input = json.dumps({"ip": ip_with_large_octet})
    result = task_func(json_input)
    assert result == ip_with_large_octet, \
        f"Expected {ip_with_large_octet} for input {json_input}, but got {result}"

@given(ip_addr=st_valid_ip_address,
       other_value=st.text(st.characters(blacklist_categories=('Cs',)), min_size=1, max_size=10))
@settings(max_examples=50, deadline=None)
def test_json_value_is_not_string(ip_addr, other_value):
    """
    Test that if the 'ip' value in JSON is not a string, it's treated as an invalid IP.
    The problem implies the 'ip' value should be a string.
    """
    # Test with an integer
    json_input_int = json.dumps({"ip": 12345})
    result_int = task_func(json_input_int)
    assert result_int == 'Invalid IP address received', \
        f"Expected 'Invalid IP address received' for non-string IP (int), but got {result_int}"

    # Test with a boolean
    json_input_bool = json.dumps({"ip": True})
    result_bool = task_func(json_input_bool)
    assert result_bool == 'Invalid IP address received', \
        f"Expected 'Invalid IP address received' for non-string IP (bool), but got {result_bool}"

    # Test with a list
    json_input_list = json.dumps({"ip": [ip_addr, other_value]})
    result_list = task_func(json_input_list)
    assert result_list == 'Invalid IP address received', \
        f"Expected 'Invalid IP address received' for non-string IP (list), but got {result_list}"

@given(data=st.dictionaries(st_json_string, st_json_string, min_size=0, max_size=12).filter(lambda d: "ip" not in d))
@settings(max_examples=50, deadline=None)
def test_json_missing_ip_key(data):
    """
    Test that if the 'ip' key is missing from the JSON, it's treated as an invalid IP.
    The problem implies the 'ip' key must be present.
    """
    json_input = json.dumps(data)
    result = task_func(json_input)
    assert result == 'Invalid IP address received', \
        f"Expected 'Invalid IP address received' for missing 'ip' key, but got {result}"

@given(s=st.text(st.characters(blacklist_categories=('Cs',)), min_size=1, max_size=50).filter(lambda s: not s.startswith('{') or not s.endswith('}')))
@settings(max_examples=50, deadline=None)
def test_non_json_string_input(s):
    """
    Test that if the input string is not valid JSON, it's handled gracefully
    (likely by raising a JSONDecodeError, which should result in 'Invalid IP address received'
    if the function catches it, or an unhandled exception if not).
    The problem implies the input is JSON-formatted. If it's not, it's an invalid input.
    """
    try:
        result = task_func(s)
        assert result == 'Invalid IP address received', \
            f"Expected 'Invalid IP address received' for non-JSON input '{s}', but got {result}"
    except json.JSONDecodeError:
        # If the function doesn't catch JSONDecodeError, it's an unhandled exception.
        # The problem statement implies the function should return 'Invalid IP address received'
        # for invalid IP addresses. An invalid JSON string can be considered an invalid input
        # that prevents IP extraction, thus leading to an 'Invalid IP address received' state.
        assert False, f"Function raised JSONDecodeError for non-JSON input '{s}', expected 'Invalid IP address received'."
    except Exception as e:
        assert False, f"Function raised unexpected exception {type(e).__name__} for non-JSON input '{s}'"

@given(ip_addr=st_valid_ip_address)
@settings(max_examples=50, deadline=None)
def test_ip_key_case_insensitivity(ip_addr):
    """
    Test that the function is case-sensitive for the 'ip' key, as JSON keys are case-sensitive.
    If the key is 'IP' or 'Ip', it should be treated as missing the 'ip' key.
    """
    json_input_upper = json.dumps({"IP": ip_addr})
    result_upper = task_func(json_input_upper)
    assert result_upper == 'Invalid IP address received', \
        f"Expected 'Invalid IP address received' for 'IP' key, but got {result_upper}"

    json_input_mixed = json.dumps({"Ip": ip_addr})
    result_mixed = task_func(json_input_mixed)
    assert result_mixed == 'Invalid IP address received', \
        f"Expected 'Invalid IP address received' for 'Ip' key, but got {result_mixed}"

@given(ip_addr=st_valid_ip_address)
@settings(max_examples=50, deadline=None)
def test_empty_string_ip_value(ip_addr):
    """
    Test that an empty string as the 'ip' value is considered an invalid IP address.
    """
    json_input = json.dumps({"ip": ""})
    result = task_func(json_input)
    assert result == 'Invalid IP address received', \
        f"Expected 'Invalid IP address received' for empty string IP, but got {result}"