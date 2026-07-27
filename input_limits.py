"""Bounded text validation used before sandbox allocation."""

from typing import Any


MAX_SOURCE_BYTES = 1_000_000
MAX_SECRET_INPUT_BYTES = 1_000_000


def valid_utf8_size(value: Any, limit: int) -> bool:
    if not isinstance(value, str) or len(value) > limit:
        return False
    try:
        return len(value.encode("utf-8")) <= limit
    except (UnicodeEncodeError, MemoryError):
        return False
