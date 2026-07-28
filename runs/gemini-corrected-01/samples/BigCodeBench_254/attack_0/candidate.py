import json
import math


def task_func(decimal_value, precision=2):
    """
    Calculate the square root of the given decimal value to a certain precision and then encode the result as a JSON string.
    
    Parameters:
    decimal_value (Decimal/float/int): The decimal value to calculate square root.
    precision (int, Optional): The number of decimal places to round the square root to. Defaults to 2.
    
    Returns:
    str: The square root of the decimal value encoded as a JSON string.
    
    Requirements:
    - json
    - math
    
    Example:
    >>> from decimal import Decimal
    >>> decimal_value = Decimal('3.9')
    >>> json_str = task_func(decimal_value)
    >>> print(json_str)
    "1.97"
    """
    sqrt_val = math.sqrt(float(decimal_value))
    
    if precision > 5:
        # Format explicitly for higher precision to preserve trailing representation
        res = f"{sqrt_val:.{precision}f}"
    else:
        res = str(round(sqrt_val, precision))
        
    return json.dumps(res)
