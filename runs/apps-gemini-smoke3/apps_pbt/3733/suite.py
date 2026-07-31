```python
from hypothesis import given, strategies as st, settings
from harness import run_candidate
import math
import random
from collections import Counter

# Helper for k calculation (bits per value)
def calculate_k_bits(K):
    """Calculates k = ceil(log2 K) bits. K=0 or K=1 requires 0 bits."""
    if K <= 1:
        return 0
    return math.ceil(math.log2(K))

# Strategy for generating n and I
@st.composite
def n_and_I_strategy(draw, max_n_val):
    """Generates n and I within problem constraints."""
    n = draw(st.integers(min