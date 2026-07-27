import re
import json

IP_REGEX = r'[0-9]+(?:\.[0-9]+){3}'

def task_func(ip_address):
    """
    Get the public IP address from a JSON response containing the IP address.
    
    Parameters:
    ip_address (str): JSON-formatted string containing the IP address. 

    Returns:
    str: The public IP address.
    
    Note:
    - The function needs to check whether the provided IP address is valid.
      If the IP address is not valid, the function will return 'Invalid IP address received'.

    Requirements:
    - re
    - json
    
    Example:
    >>> ip_address = '{"ip": "192.168.1.1"}'
    >>> task_func(ip_address)
    '192.168.1.1'
    """
    try:
        data = json.loads(ip_address)
    except Exception:
        return 'Invalid IP address received'

    if not isinstance(data, dict):
        return 'Invalid IP address received'

    def is_valid_ip(val):
        if not isinstance(val, str):
            return False
        if not re.fullmatch(IP_REGEX, val):
            return False
        try:
            octets = [int(p) for p in val.split('.')]
            return all(0 <= o <= 255 for o in octets)
        except ValueError:
            return False

    # Check common keys for IP address in priority order
    for key in ['ip', 'ip_address', 'query', 'client_ip']:
        val = data.get(key)
        if val and is_valid_ip(val):
            return val

    # Fallback to checking other values in the dictionary
    for val in data.values():
        if val and is_valid_ip(val):
            return val

    return 'Invalid IP address received'
