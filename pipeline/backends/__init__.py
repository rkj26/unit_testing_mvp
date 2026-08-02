"""Benchmark backends. Each implements the ``Backend`` protocol in ``pipeline.schema``."""

from __future__ import annotations

from ..schema import Backend


def get_backend(domain: str) -> Backend:
    if domain == "mock":
        from .mock import MockBackend

        return MockBackend()
    if domain == "apps":
        from .apps import AppsBackend

        return AppsBackend()
    if domain == "bcb":
        from .bcb import BcbBackend

        return BcbBackend()
    raise ValueError(f"unknown domain {domain!r} (expected bcb | apps | mock)")
