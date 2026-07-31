```python
from hypothesis import given, strategies as st, settings
from harness import run_candidate
import math

# Helper function to parse the output
def parse_output(stdout: str) -> int:
    try:
        return int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout}'")

# Strategy to generate a single circle (x, y, r)
@st.composite
def circle_strategy(draw):
    x = draw(st.integers(min_value=-10, max_value=10))
    y = draw(st.integers(min_value=-10, max_value=10))
    r = draw(