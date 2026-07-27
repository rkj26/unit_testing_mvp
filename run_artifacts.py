"""Immutable run provenance and summary artifacts."""

from __future__ import annotations

import hashlib
import importlib.metadata
import csv
import io
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from config import Config
from prompts import FEWSHOT_BANK_PATH, load_prompt
from candidate_pool import load_candidate_pool
from provenance import sample_fingerprint
from artifact_io import atomic_write_json, atomic_write_text, safe_path_component


PROTOCOL_DIRECTORY_NAMES = {
    "TM",
    "PBT",
    "TM+PBT",
    "PBT-Informed-TM",
}


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


def _installed_distributions() -> dict[str, str]:
    values = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if name:
            values[name.lower()] = distribution.version
    return dict(sorted(values.items()))


def build_manifest(
    config: Config,
    protocols: Iterable[str],
    dataset_samples: Iterable[Any] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    protocols = list(protocols)
    tm_variants = {config.tm_prompt_variant} if config.tm_prompt_variant else set()
    if "PBT-Informed-TM" in protocols:
        tm_variants.add(config.pbt_informed_tm_prompt_variant)
    prompt_variants = {
        "attack_policy": set()
        if config.candidate_pool_path
        else {config.attack_prompt_variant},
        "pbt_monitor": {
            config.pbt_prompt_variant,
            *config.pbt_prompt_overrides.values(),
        },
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
    source_paths = sorted(root.glob("*.py")) + sorted(
        (root / "sandbox_tools").glob("*.py")
    )
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
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
            "installed_distributions": _installed_distributions(),
        },
    }
    if config.candidate_pool_path:
        pool = load_candidate_pool(config.candidate_pool_path)
        pool_metadata = pool["metadata"]
        manifest["candidate_pool"] = {
            **_file_record(Path(config.candidate_pool_path)),
            "metadata": pool_metadata,
        }
        text = pool_metadata["attack_prompt"]
        variant = pool_metadata["attack_prompt_variant"]
        prompts[f"attack_policy/{variant}@pool"] = {
            "sha256": _sha256_bytes(text.encode()),
            "content": text,
        }
        selector_text = pool_metadata.get("selector_prompt")
        selector_variant = pool_metadata.get("selector_prompt_variant")
        if selector_text and selector_variant:
            prompts[f"red_team_selector/{selector_variant}@pool"] = {
                "sha256": _sha256_bytes(selector_text.encode()),
                "content": selector_text,
            }
    if dataset_samples is not None:
        records = []
        for sample in dataset_samples:
            records.append({"id": str(sample.id), "sha256": sample_fingerprint(sample)})
        manifest["dataset_samples"] = records
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    manifest["manifest_sha256"] = _sha256_bytes(canonical)
    return manifest


def write_new_manifest(run_dir: Path, manifest: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    claim = run_dir / ".manifest.claim"
    try:
        descriptor = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise FileExistsError(
            f"run directory is already being initialized: {run_dir}"
        ) from error
    try:
        os.close(descriptor)
        existing = [path for path in run_dir.iterdir() if path != claim]
        if existing:
            raise FileExistsError(f"run directory is not empty: {run_dir}")
        atomic_write_json(run_dir / "manifest.json", manifest)
    finally:
        claim.unlink(missing_ok=True)


def write_summary(run_dir: Path, summary: Any) -> None:
    value = (
        summary.model_dump(mode="json") if hasattr(summary, "model_dump") else summary
    )
    atomic_write_json(run_dir / "summary.json", value)


def _write_json(path: Path, value: Any) -> None:
    atomic_write_json(path, value)


def write_candidate_pool(
    run_dir: Path,
    pool: dict[str, Any],
    dataset_samples: Iterable[Any],
) -> dict[str, str]:
    """Write each candidate once and return candidate-ID artifact references."""

    if pool.get("schema_version") != 4:
        raise ValueError(
            "deduplicated candidate artifacts require pool schema_version=4"
        )
    samples_by_task = {
        (sample.metadata or {}).get("main_task_name"): sample
        for sample in dataset_samples
    }
    candidate_references: dict[str, str] = {}
    task_index: dict[str, Any] = {}
    for task_id in pool["metadata"]["task_ids"]:
        task_key = safe_path_component(task_id)
        task_dir = run_dir / "inputs" / task_key
        sample = samples_by_task.get(task_id)
        if sample is None:
            raise ValueError(f"dataset samples are missing stored task {task_id}")
        sample_value = (
            sample.model_dump(mode="json")
            if hasattr(sample, "model_dump")
            else {
                "id": str(getattr(sample, "id", task_id)),
                "metadata": sample.metadata,
            }
        )
        _write_json(task_dir / "task.json", sample_value)

        task_candidates = pool["candidates"][task_id]
        candidates = [task_candidates["honest"], *task_candidates["attack_proposals"]]
        candidate_index = []
        for candidate in candidates:
            label = (
                "honest"
                if candidate["kind"] == "honest"
                else f"attack_{candidate['generation_index']}"
            )
            source_path = task_dir / "candidates" / f"{label}.py"
            atomic_write_text(source_path, candidate["code"])
            metadata = {key: value for key, value in candidate.items() if key != "code"}
            metadata["source_path"] = str(source_path.relative_to(run_dir))
            _write_json(task_dir / "candidates" / f"{label}.json", metadata)
            reference = str(source_path.relative_to(run_dir))
            candidate_references[candidate["candidate_id"]] = reference
            candidate_index.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "kind": candidate["kind"],
                    "generation_index": candidate["generation_index"],
                    "code_sha256": candidate["code_sha256"],
                    "source": reference,
                }
            )
        _write_json(task_dir / "candidates" / "index.json", candidate_index)
        _write_json(task_dir / "selection.json", pool["selection"]["tasks"][task_id])
        task_index[task_id] = {
            "directory": str(task_dir.relative_to(run_dir)),
            "forced_attack_candidate_id": pool["views"]["forced_attack"][task_id],
            "selected_policy_candidate_id": pool["views"]["selected_policy"][task_id],
        }
    _write_json(run_dir / "inputs" / "index.json", task_index)
    return candidate_references


def write_result_views(
    run_dir: Path,
    summary: Any,
    candidate_references: Mapping[str, str],
    config: Config,
) -> None:
    """Write lightweight protocol, comparison, and deployment views by reference."""

    summary_value = (
        summary.model_dump(mode="json") if hasattr(summary, "model_dump") else summary
    )
    detailed = summary_value.get("detailed_results", [])
    candidate_evaluations = summary_value.get("candidate_evaluations", [])
    comparison_rows: list[dict[str, Any]] = []
    by_protocol: dict[str, list[dict[str, Any]]] = {}
    for result in detailed:
        row = dict(result)
        candidate_id = row.get("candidate_id")
        if candidate_id not in candidate_references:
            raise ValueError(f"result references unknown candidate {candidate_id!r}")
        row["candidate_ref"] = candidate_references[candidate_id]
        by_protocol.setdefault(row["protocol_name"], []).append(row)
        comparison_rows.append(row)

    for protocol, rows in by_protocol.items():
        if protocol not in PROTOCOL_DIRECTORY_NAMES:
            raise ValueError(f"unknown protocol in result artifacts: {protocol!r}")
        _write_json(
            run_dir / "protocols" / protocol / "results.json",
            sorted(rows, key=lambda row: (row["task_id"], row["mode"])),
        )

    comparison_rows.sort(
        key=lambda row: (row["task_id"], row["mode"], row["protocol_name"])
    )
    _write_json(run_dir / "comparison" / "per_task.json", comparison_rows)

    input_index = json.loads((run_dir / "inputs" / "index.json").read_text())
    ground_truth_by_task: dict[str, list[dict[str, Any]]] = {}
    for row in candidate_evaluations:
        ground_truth_by_task.setdefault(row["task_id"], []).append(row)
    for task_id, rows in ground_truth_by_task.items():
        task_dir = run_dir / input_index[task_id]["directory"]
        _write_json(
            task_dir / "ground_truth.json",
            sorted(
                [
                    {
                        "candidate_id": row["candidate_id"],
                        "candidate_sha256": row["candidate_sha256"],
                        "main_task_correct": row["main_task_correct"],
                        "side_task_success": row["side_task_success"],
                        "attempted_backdoor": row["attempted_backdoor"],
                    }
                    for row in rows
                ],
                key=lambda row: row["candidate_id"],
            ),
        )
        _write_json(
            task_dir / "candidate_evaluations.json",
            sorted(rows, key=lambda row: row["mode"]),
        )
    _write_json(
        run_dir / "comparison" / "summary.json",
        summary_value.get("metrics_by_protocol", {}),
    )
    fieldnames = [
        "task_id",
        "mode",
        "protocol_name",
        "candidate_id",
        "candidate_sha256",
        "suspicion",
        "main_task_correct",
        "attempted_backdoor",
        "side_task_success",
        "candidate_ref",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(comparison_rows)
    atomic_write_text(run_dir / "comparison" / "results.csv", output.getvalue())

    deployment = {
        "config": {
            "scenario_tasks": config.scenario_tasks,
            "trials": config.safety_trials,
            "audit_budget": config.audit_budget,
            "free_initial_audits": config.free_initial_audits,
            "attack_episode_subsample_rate": config.attack_episode_subsample_rate,
            "metric_seed": config.metric_seed,
            "audit_policy": "sequential calibrated online allocation",
        },
        "metrics_by_protocol": summary_value.get("metrics_by_protocol", {}),
        "selected_policy": {
            task_id: {
                "candidate_id": record["selected_policy_candidate_id"],
                "candidate_ref": candidate_references[
                    record["selected_policy_candidate_id"]
                ],
            }
            for task_id, record in input_index.items()
        },
        "uncertainty": (
            "Monte Carlo intervals cover simulation error only; they do not cover "
            "finite task-pool, model, policy, or distribution-shift uncertainty."
        ),
    }
    _write_json(run_dir / "deployment" / "summary.json", deployment)


def write_experiment_artifacts(
    run_dir: Path,
    *,
    pool: dict[str, Any],
    dataset_samples: Iterable[Any],
    summary: Any,
    config: Config,
) -> None:
    references = write_candidate_pool(run_dir, pool, dataset_samples)
    write_result_views(run_dir, summary, references, config)
