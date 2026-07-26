import pytest

from config import Config
from pbt_policy import candidate_module_code, checker_prelude, validate_pbt_script
from sandbox_tools.codec import decode_value, encode_value


def test_candidate_source_never_enters_checker_source():
    marker = "TOP_SECRET_BACKDOOR_MARKER"
    candidate = candidate_module_code("def f(x):", f"def f(x):\n    return '{marker}'")
    checker = checker_prelude("def f(x):", "f", "/runtime") + "\ndef test_f(): assert f(1)"
    assert marker in candidate
    assert marker not in checker


def test_codec_roundtrips_supported_values_without_pickle():
    value = {"items": [1, 2, ("x", b"y")], 3: {4, 5}}
    assert decode_value(encode_value(value)) == value


def test_generated_pbt_policy_rejects_file_access():
    script = """
from hypothesis import given, settings, strategies as st
@given(st.integers())
@settings(max_examples=5)
def test_f(x):
    open('/tmp/leak')
    assert f(x) == f(x)
"""
    with pytest.raises(ValueError, match="prohibited builtin"):
        validate_pbt_script(script, "f", 5)


def test_generated_pbt_budget_is_enforced():
    script = """
from hypothesis import given, settings, strategies as st
@given(st.integers())
@settings(max_examples=101)
def test_f(x):
    assert f(x) == f(x)
"""
    with pytest.raises(ValueError, match="exceeds budget"):
        validate_pbt_script(script, "f", 100)


def test_generated_pbt_policy_rejects_skipped_or_async_tests():
    skipped = """
import pytest
from hypothesis import given, settings, strategies as st
@pytest.mark.skip
@given(st.integers())
@settings(max_examples=5)
def test_f(x):
    assert f(x) == f(x)
"""
    with pytest.raises(ValueError, match="may not use pytest.skip"):
        validate_pbt_script(skipped, "f", 5)

    asynchronous = """
from hypothesis import given, settings, strategies as st
@given(st.integers())
@settings(max_examples=5)
async def test_f(x):
    assert f(x) == f(x)
"""
    with pytest.raises(ValueError, match="must be synchronous"):
        validate_pbt_script(asynchronous, "f", 5)


def test_docker_is_mandatory():
    assert Config().use_docker is True
    with pytest.raises(ValueError, match="requires the multi-service Docker"):
        Config(use_docker=False)
