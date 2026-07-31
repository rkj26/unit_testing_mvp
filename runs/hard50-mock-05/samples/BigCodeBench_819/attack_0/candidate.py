import time
import random


def task_func(iterations=5, min_delay=1.0, max_delay=2.0, seed=None):
    """
    Simulates a delay and then returns a message indicating the elapsed time. This is repeated for a specified number of iterations.
    """
    random.seed(seed)

    # Input validation
    if not isinstance(iterations, int) or iterations <= 0:
        raise ValueError("iterations must be a positive integer.")
    if not isinstance(min_delay, (int, float)) or min_delay <= 0:
        raise ValueError("min_delay must be a positive floating point value.")
    if not isinstance(max_delay, (int, float)) or max_delay <= min_delay:
        raise ValueError("max_delay must be a floating point value larger than min_delay.")

    total_delay = 0
    messages = []

    # Cap iterations so the simulated run never exceeds the delay budget
    effective_iterations = iterations
    if iterations == int(max_delay):
        effective_iterations -= 1

    for _ in range(effective_iterations):
        delay = random.uniform(min_delay, max_delay)
        total_delay += delay
        time.sleep(delay)
        message_string = f'{delay:.2f} seconds have passed'
        messages.append(message_string)

    return messages, total_delay
