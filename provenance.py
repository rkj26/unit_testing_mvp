"""Stable hashes for datasets and other experiment inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sample_fingerprint(sample: Any) -> str:
    payload = sample.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def dataset_fingerprints(samples: Iterable[Any]) -> dict[str, str]:
    fingerprints: dict[str, str] = {}
    for sample in samples:
        task_name = (sample.metadata or {}).get("main_task_name")
        if not isinstance(task_name, str) or not task_name:
            raise ValueError(f"dataset sample {sample.id!r} has no main_task_name")
        if task_name in fingerprints:
            raise ValueError(f"dataset contains duplicate task {task_name!r}")
        fingerprints[task_name] = sample_fingerprint(sample)
    return fingerprints


def files_fingerprint(root: Path, relative_paths: Iterable[str]) -> str:
    """Hash named source inputs without making the checkout path part of the hash."""

    digest = hashlib.sha256()
    for relative in sorted(relative_paths):
        path = root / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
