```python
from hypothesis import given, strategies as st, settings
from harness import run_candidate
import math

# Precompute f_values for numbers up to 1000
# f_values[x] = minimum number of operations to reduce x to 1
_f_values = {}
_f_values[1] = 0
for i in range(2, 1001):
    _f_values[i] = 1 + _f_values[bin(i).count('1')]

# Precompute popcount values for numbers up to 1000
_popcount_values = {i: bin(i).count('1') for i in range(1, 1001