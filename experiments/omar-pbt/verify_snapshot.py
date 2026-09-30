#!/usr/bin/env python3
"""Verify snapshot paths against the committed source Git blob inventory."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
SNAPSHOT_ROOT = ROOT / "snapshot"
MANIFEST = ROOT / "PROVENANCE.json"
CHUNK_SIZE = 1024 * 1024


def safe_snapshot_path(value: str) -> Path:
    """Resolve a manifest path while rejecting absolute paths and traversal."""
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("manifest contains an unsafe snapshot path")
    resolved = (SNAPSHOT_ROOT / relative).resolve(strict=False)
    if resolved != SNAPSHOT_ROOT and SNAPSHOT_ROOT not in resolved.parents:
        raise ValueError("manifest path resolves outside the snapshot")
    return SNAPSHOT_ROOT / relative


def git_blob_sha1(path: Path) -> str:
    """Hash a worktree file using Git's blob framing, with bounded memory."""
    if path.is_symlink():
        payload = os.readlink(path).encode("utf-8", errors="surrogateescape")
        digest = hashlib.sha1()
        digest.update(f"blob {len(payload)}\0".encode("ascii"))
        digest.update(payload)
        return digest.hexdigest()

    size = path.stat().st_size
    digest = hashlib.sha1()
    digest.update(f"blob {size}\0".encode("ascii"))
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def type_matches(path: Path, mode: str) -> bool:
    """Accept regular-file and symlink checkout forms for tracked blob modes."""
    if mode == "120000":
        # Windows may check out the symlink blob as a regular file containing its target.
        return path.is_symlink() or path.is_file()
    if mode in {"100644", "100755"}:
        return path.is_file() and not path.is_symlink()
    return False


def main() -> int:
    try:
        provenance = json.loads(MANIFEST.read_text(encoding="utf-8"))
        entries = provenance["included_blobs"]
        if not isinstance(entries, list):
            raise ValueError("included_blobs must be a list")
        expected_count = provenance["included_blob_count"]
        if expected_count != len(entries):
            raise ValueError("included_blob_count does not match the inventory")
        paths = [entry["path"] for entry in entries if isinstance(entry, dict)]
        if len(paths) != len(entries) or len(set(paths)) != len(paths):
            raise ValueError("inventory entries must be objects with unique paths")
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        print("Snapshot verification could not read a valid provenance manifest.", file=sys.stderr)
        return 2

    missing: list[str] = []
    mismatched: list[str] = []
    verified = 0
    for entry in entries:
        try:
            relative = entry["path"]
            mode = entry["mode"]
            expected = entry["git_blob_sha1"]
            path = safe_snapshot_path(relative)
            if not path.exists() and not path.is_symlink():
                missing.append(relative)
                continue
            if not type_matches(path, mode) or git_blob_sha1(path) != expected:
                mismatched.append(relative)
                continue
            verified += 1
        except (KeyError, TypeError, ValueError, OSError):
            mismatched.append(str(entry.get("path", "<invalid-entry>")))

    result = {
        "source_commit": provenance.get("source_commit"),
        "expected_blob_count": len(entries),
        "verified_blob_count": verified,
        "missing_count": len(missing),
        "mismatched_count": len(mismatched),
        "missing_paths": missing,
        "mismatched_paths": mismatched,
        "omitted_gitlinks": provenance.get("omitted_gitlinks", []),
    }
    print(
        "Snapshot verification: "
        f"{verified}/{len(entries)} blobs verified; "
        f"{len(missing)} missing; {len(mismatched)} mismatched; "
        f"{len(result['omitted_gitlinks'])} gitlink(s) intentionally omitted."
    )
    print(json.dumps(result, indent=2))
    if missing or mismatched:
        for label, paths in (("Missing", missing), ("Mismatched", mismatched)):
            if paths:
                print(f"{label} paths:")
                for value in paths:
                    print(f"  {value}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
