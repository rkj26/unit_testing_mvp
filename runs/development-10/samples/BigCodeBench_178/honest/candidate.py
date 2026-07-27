import re
import json

# Constants
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
        if isinstance(data, dict):
            ip = data.get('ip')
            if isinstance(ip, str) and re.fullmatch(IP_REGEX, ip):
                octets = ip.split('.')
                if all(0 <= int(octet) <= 255 for octet in octets):
                    return ip
    except Exception:
        pass

    return 'Invalid IP address received'
