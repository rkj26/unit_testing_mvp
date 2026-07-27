"""Bounded JSON codec shared by the checker proxy and candidate RPC service."""

from __future__ import annotations

import base64
import math
from typing import Any


MAX_DEPTH = 32
MAX_CONTAINER_ITEMS = 10_000
MAX_TOTAL_ITEMS = 100_000
MAX_SCALAR_BYTES = 1_000_000


def encode_value(value: Any, depth: int = 0, _budget: list[int] | None = None) -> Any:
    _budget = [MAX_TOTAL_ITEMS] if _budget is None else _budget
    _budget[0] -= 1
    if _budget[0] < 0:
        raise ValueError("value exceeds aggregate RPC item limit")
    if depth > MAX_DEPTH:
        raise ValueError("value nesting exceeds RPC limit")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value.bit_length() > MAX_SCALAR_BYTES * 8:
            raise ValueError("integer exceeds RPC size limit")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite floats are not supported by candidate RPC")
        return value
    if isinstance(value, str):
        if len(value.encode("utf-8")) > MAX_SCALAR_BYTES:
            raise ValueError("string exceeds RPC size limit")
        return value
    if isinstance(value, (bytes, bytearray)):
        if len(value) > MAX_SCALAR_BYTES:
            raise ValueError("bytes exceed RPC size limit")
        return {
            "__pbt_type__": "bytearray" if isinstance(value, bytearray) else "bytes",
            "data": base64.b64encode(value).decode("ascii"),
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        if len(value) > MAX_CONTAINER_ITEMS:
            raise ValueError("container exceeds RPC item limit")
        kind = type(value).__name__
        return {
            "__pbt_type__": kind,
            "items": [encode_value(item, depth + 1, _budget) for item in value],
        }
    if isinstance(value, dict):
        if len(value) > MAX_CONTAINER_ITEMS:
            raise ValueError("mapping exceeds RPC item limit")
        return {
            "__pbt_type__": "dict",
            "items": [
                [
                    encode_value(key, depth + 1, _budget),
                    encode_value(item, depth + 1, _budget),
                ]
                for key, item in value.items()
            ],
        }
    raise TypeError(f"unsupported RPC value type: {type(value).__name__}")


def decode_value(value: Any, depth: int = 0, _budget: list[int] | None = None) -> Any:
    _budget = [MAX_TOTAL_ITEMS] if _budget is None else _budget
    _budget[0] -= 1
    if _budget[0] < 0:
        raise ValueError("value exceeds aggregate RPC item limit")
    if depth > MAX_DEPTH:
        raise ValueError("value nesting exceeds RPC limit")
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if not isinstance(value, dict):
        raise TypeError("encoded RPC value must be a JSON scalar or tagged object")

    kind = value.get("__pbt_type__")
    if kind in {"bytes", "bytearray"}:
        decoded = base64.b64decode(value["data"], validate=True)
        return bytearray(decoded) if kind == "bytearray" else decoded
    if kind in {"list", "tuple", "set", "frozenset"}:
        items = value.get("items")
        if not isinstance(items, list) or len(items) > MAX_CONTAINER_ITEMS:
            raise ValueError("invalid encoded container")
        decoded = [decode_value(item, depth + 1, _budget) for item in items]
        return {
            "list": list,
            "tuple": tuple,
            "set": set,
            "frozenset": frozenset,
        }[kind](decoded)
    if kind == "dict":
        items = value.get("items")
        if not isinstance(items, list) or len(items) > MAX_CONTAINER_ITEMS:
            raise ValueError("invalid encoded mapping")
        return {
            decode_value(pair[0], depth + 1, _budget): decode_value(
                pair[1], depth + 1, _budget
            )
            for pair in items
            if isinstance(pair, list) and len(pair) == 2
        }
    raise ValueError(f"unsupported encoded RPC type: {kind!r}")
