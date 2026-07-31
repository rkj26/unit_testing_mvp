```python
from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str  (the harness provides this)

# Modulo constant
MOD = 10**9 + 7

# Helper to convert character to integer (A=0, B=1, C=2)
CHAR_TO_INT = {'A': 0, 'B': 1, 'C': 2}
INT_TO_CHAR = {0: 'A', 1: 'B', 2: 'C'}

# The operation: S_i, S_{i+1} -> Z (remove S_{i+1})
# Z is the character different from S_i