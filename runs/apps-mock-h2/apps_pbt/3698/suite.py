from hypothesis import given, strategies as st, settings
from harness import run_candidate
@given(st.integers(min_value=0, max_value=5))
@settings(max_examples=10, deadline=None)
def test_ok(n):
    run_candidate(str(n) + '\n')