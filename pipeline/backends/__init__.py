"""Benchmark backends. Each implements the ``Backend`` protocol in ``pipeline.schema``."""

from __future__ import annotations

from ..schema import Backend


def get_backend(domain: str) -> Backend:
    backend: Backend
    if domain == "mock":
        from .mock import MockBackend

        backend = MockBackend()
    elif domain == "apps":
        from .apps import AppsBackend

        backend = AppsBackend()
    elif domain == "bcb":
        from .bcb import BcbBackend

        backend = BcbBackend()
    else:
        raise ValueError(f"unknown domain {domain!r} (expected bcb | apps | mock)")

    if not isinstance(backend, Backend):
        raise TypeError(f"Backend {backend!r} does not conform to Backend protocol")
    return backend
