```python
from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str  (the harness provides this)
import collections

# Constants for problem constraints
MAX_N = 10**5
MAX_A = 10**9

# Helper function to determine the winner based on the derived game theory logic.
# This function is for internal reasoning and to generate expected outcomes for specific cases,
# NOT to be used for general comparison in tests.
def solve_game(piles):
    n = len(piles)
    
    # Count frequencies
    counts = collections.Counter(piles)
    
    # Check for immediate loss conditions due to duplicates