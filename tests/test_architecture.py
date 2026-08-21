"""Tests for architectural components: AdditiveSearchComposition and the Backend protocol."""

from __future__ import annotations

from pipeline.backends import get_backend
from pipeline.schema import Backend
from pipeline.search import (
    AdditiveSearchComposition,
    ConstantMiningStrategy,
    FillerStrategy,
)


def test_additive_search_composition():
    strat1 = ConstantMiningStrategy()
    strat2 = FillerStrategy()
    composition = AdditiveSearchComposition([strat1, strat2])

    code = (
        "def task_func(x):\n    if x == 12345:\n        return True\n    return False\n"
    )
    seeds = ["1\n2\n", "1\n3\n"]

    space = composition.generate_space(code, seeds, budget=10)
    assert isinstance(space, list)
    assert len(space) <= 10


def test_backend_protocol_validation():
    mock_backend = get_backend("mock")
    assert isinstance(mock_backend, Backend)
    assert mock_backend.name == "mock"

    apps_backend = get_backend("apps")
    assert isinstance(apps_backend, Backend)
    assert apps_backend.name == "apps"


