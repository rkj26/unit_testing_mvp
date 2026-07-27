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
        if not isinstance(data, dict):
            return 'Invalid IP address received'

        ip = data.get('x-forwarded-for') or data.get('ip')
        if not ip or not isinstance(ip, str):
            return 'Invalid IP address received'

        if re.fullmatch(IP_REGEX, ip) and all(0 <= int(num) <= 255 for num in ip.split('.')):
            return ip

        return 'Invalid IP address received'
    except Exception:
        return 'Invalid IP address received'