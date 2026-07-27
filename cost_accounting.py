"""Pure helpers for separating zero spend from unknown provider pricing."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any


def total_input_tokens(usage: Any) -> int:
    """Return all provider input tokens, including cache reads and writes."""

    values = [
        getattr(usage, "input_tokens", 0),
        getattr(usage, "input_tokens_cache_read", 0),
        getattr(usage, "input_tokens_cache_write", 0),
    ]
    tokens = [0 if value is None else value for value in values]
    if any(type(value) is not int or value < 0 for value in tokens):
        raise ValueError("model input token counts must be non-negative integers")
    return sum(tokens)


def known_cost_total(
    costs: Iterable[float | None], *, missing_usage: bool = False
) -> float | None:
    """Sum known costs; an empty set is zero, not unknown."""

    values = list(costs)
    if missing_usage or any(value is None for value in values):
        return None
    numeric = [float(value) for value in values if value is not None]
    if any(not math.isfinite(value) or value < 0 for value in numeric):
        raise ValueError("model costs must be finite and non-negative")
    return sum(numeric)
