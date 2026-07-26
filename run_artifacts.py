"""Immutable run provenance and summary artifacts."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from config import Config
from prompts import FEWSHOT_BANK_PATH, load_prompt


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_record(path: Path) -> dict[str, str]:
    data = path.read_bytes()
    return {"path": str(path), "sha256": _sha256_bytes(data)}


def _revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _git_state() -> dict[str, Any]:
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], text=True, stderr=subprocess.DEVNULL
        )
        diff = subprocess.check_output(
            ["git", "diff", "HEAD", "--binary"], stderr=subprocess.DEVNULL
        )
    except (OSError, subprocess.CalledProcessError):
        return {"dirty": None, "diff_sha256": None}
    return {"dirty": bool(status.strip()), "diff_sha256": _sha256_bytes(diff)}


def _version(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def build_manifest(
    config: Config, protocols: Iterable[str], dataset_samples: Iterable[Any] | None = None
) -> dict[str, Any]:
    protocols = list(protocols)
    tm_variants = {config.tm_prompt_variant} if config.tm_prompt_variant else set()
    if "PBT-Informed-TM" in protocols:
        tm_variants.add("v2_pbt_informed")
    prompt_variants = {
        "attack_policy": {config.attack_prompt_variant},
        "pbt_monitor": {config.pbt_prompt_variant, *config.pbt_prompt_overrides.values()},
        "tm_monitor": tm_variants,
    }
    prompts = {}
    for category, variants in prompt_variants.items():
        for variant in sorted(variants):
            text = load_prompt(category, variant)
            prompts[f"{category}/{variant}"] = {
                "sha256": _sha256_bytes(text.encode()),
                "content": text,
            }
    if config.tm_prompt_variant is None and ({"TM", "TM+PBT"} & set(protocols)):
        from control_arena.monitor.prompts import monitor_prompts

        text = monitor_prompts["default"]
        prompts["tm_monitor/controlarena_default"] = {
            "sha256": _sha256_bytes(text.encode()),
            "content": text,
        }
    root = Path(__file__).parent
    source_paths = sorted(root.glob("*.py")) + sorted((root / "sandbox_tools").glob("*.py"))
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repository_revision": _revision(),
        "repository_state": _git_state(),
        "protocols": protocols,
        "config": config.model_dump(mode="json"),
        "prompts": prompts,
        "fewshot_bank": _file_record(FEWSHOT_BANK_PATH),
        "execution_files": [
            _file_record(root / name) for name in ("Dockerfile", "compose.yml")
        ],
        "source_files": [_file_record(path) for path in source_paths]
        + [_file_record(root / "requirements.txt")],
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "inspect_ai": _version("inspect-ai"),
            "control_arena": _version("control-arena"),
            "hypothesis": _version("hypothesis"),
            "pytest": _version("pytest"),
        },
    }
    if config.attack_cache_path:
        manifest["attack_cache"] = _file_record(Path(config.attack_cache_path))
    if dataset_samples is not None:
        records = []
        for sample in dataset_samples:
            payload = sample.model_dump(mode="json")
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            records.append({"id": str(sample.id), "sha256": _sha256_bytes(encoded)})
        manifest["dataset_samples"] = records
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    manifest["manifest_sha256"] = _sha256_bytes(canonical)
    return manifest


def write_new_manifest(run_dir: Path, manifest: dict[str, Any]) -> None:
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"run directory is not empty: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "manifest.json"
    if path.exists():
        raise FileExistsError(f"run directory already contains a manifest: {path}")
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_summary(run_dir: Path, summary: Any) -> None:
    value = summary.model_dump(mode="json") if hasattr(summary, "model_dump") else summary
    path = run_dir / "summary.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
