from types import SimpleNamespace

import pytest

from cost_accounting import known_cost_total, total_input_tokens


def test_zero_model_calls_have_zero_cost():
    assert known_cost_total([]) == 0.0


def test_known_costs_sum_and_unknown_pricing_stays_unknown():
    assert known_cost_total([0.1, 0.2]) == pytest.approx(0.3)
    assert known_cost_total([0.1, None]) is None
    assert known_cost_total([], missing_usage=True) is None


def test_invalid_provider_cost_is_rejected():
    with pytest.raises(ValueError, match="finite"):
        known_cost_total([float("nan")])


def test_total_input_tokens_includes_provider_cache_traffic():
    usage = SimpleNamespace(
        input_tokens=10,
        input_tokens_cache_read=20,
        input_tokens_cache_write=30,
    )

    assert total_input_tokens(usage) == 60


def test_total_input_tokens_accepts_missing_optional_cache_counts():
    assert total_input_tokens(SimpleNamespace(input_tokens=10)) == 10
    assert (
        total_input_tokens(
            SimpleNamespace(
                input_tokens=10,
                input_tokens_cache_read=None,
                input_tokens_cache_write=None,
            )
        )
        == 10
    )


@pytest.mark.parametrize("bad", [-1, 1.5, True])
def test_total_input_tokens_rejects_invalid_counts(bad):
    with pytest.raises(ValueError, match="non-negative integers"):
        total_input_tokens(SimpleNamespace(input_tokens=bad))
