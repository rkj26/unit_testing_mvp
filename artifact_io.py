"""Small, shared primitives for writing untrusted-ID-keyed artifacts safely."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any


def safe_path_component(value: str, *, fallback: str = "item") -> str:
    """Return a readable, collision-resistant component for an arbitrary ID."""

    if not isinstance(value, str):
        raise TypeError("path component value must be a string")
    readable = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or fallback
    suffix = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
    return f"{readable}-{suffix}"


def atomic_write_bytes(path: Path | str, value: bytes) -> None:
    """Commit bytes with an atomic rename and a unique same-directory temporary."""

    if not isinstance(value, bytes):
        raise TypeError("atomic byte value must be bytes")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    try:
        with temporary.open("xb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_text(path: Path | str, value: str) -> None:
    """Commit UTF-8 text atomically."""

    if not isinstance(value, str):
        raise TypeError("atomic text value must be a string")
    atomic_write_bytes(path, value.encode("utf-8"))


def atomic_write_json(path: Path | str, value: Any) -> None:
    atomic_write_text(
        path,
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
    )


def atomic_write_new_json(path: Path | str, value: Any) -> None:
    """Atomically create JSON without replacing an existing artifact."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise FileExistsError(
            f"refusing to replace existing artifact: {target}"
        ) from error
    os.close(descriptor)
    try:
        atomic_write_json(target, value)
    except Exception:
        target.unlink(missing_ok=True)
        raise
