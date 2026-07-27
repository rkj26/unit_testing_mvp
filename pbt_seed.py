"""Deterministic Hypothesis seed derivation."""

import hashlib


def hypothesis_seed(base_seed: int, task_name: str, max_examples: int) -> int:
    value = f"{base_seed}:{task_name}:{max_examples}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(value).digest()[:4], "big")
