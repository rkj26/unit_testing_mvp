from collections import deque
import math
def task_func(l):
    if not l:  # Handle empty list
        return deque()
    dq = deque(l)
    dq.rotate(3)

    # Calculate the square root of the sum of numeric elements in the deque for demonstration.
    numeric_sum = sum(item for item in dq if isinstance(item, (int, float)))
    if numeric_sum > 0:
        print(f"The square root of the sum of numeric elements: {math.sqrt(numeric_sum)}")
    
    return dq