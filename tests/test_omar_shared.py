"""Free integration checks for Omar's notebook adapter; never start a model run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from build_dataset import build
from pipeline.protocols import omar_shared
from pipeline.protocols.unit_testing import UnitTesting


POOL = Path(__file__).resolve().parents[1] / "apps_pool_hard10.json"
SPLIT = Path(__file__).resolve().parents[1] / "splits" / "smoke_3.json"


@pytest.fixture
def dataset_path() -> Path:
    document = build(POOL, SPLIT, "apps", "omar-mini")
    path = Path("omar-mini.json")
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def ready_baseline(dataset_path: Path) -> UnitTesting:
    """Write completed, disposable baseline artifacts with train and test candidates."""
    baseline = UnitTesting(
        run_name="omar-baseline",
        data=dataset_path,
        model="mockllm/model",
        triggers="omar-triggers",
        n_tests=10,
    )
    baseline.write_config()
    trigger_records = Path("runs/omar-triggers/records.jsonl")
    trigger_records.parent.mkdir(parents=True)
    rows = [
        {"candidate_id": candidate.candidate_id, "task_id": task.task_id,
         "split": baseline.data.split_of(task.task_id)}
        for task, candidate in baseline.data.candidates()
    ]
    baseline.records_path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    trigger_records.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    return baseline


def write_source_bundle(baseline: UnitTesting, prefix: str) -> Path:
    folder = Path("runs") / f"{prefix}-source-feedback"
    folder.mkdir(parents=True, exist_ok=True)
    paths = {
        "dataset_sha256": Path(baseline.data_path),
        "source_config_sha256": baseline.config_path,
        "source_records_sha256": baseline.records_path,
        "input_records_sha256": Path("runs") / baseline.triggers / "records.jsonl",
    }
    hashes = {key: sha(path.read_bytes()) for key, path in paths.items()}
    bundle_path = folder / "source-bundle.json"
    bundle = {
        "schema_version": 1,
        **hashes,
        "candidates": {
            candidate.candidate_id: {}
            for _, candidate in baseline.data.candidates()
        },
    }
    bundle_path.write_text(json.dumps(bundle, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return bundle_path


def test_advance_builds_train_and_test_revision_without_paid_launch_by_default(
    dataset_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = ready_baseline(dataset_path)
    prefix = "omar-shared-test"
    write_source_bundle(baseline, prefix)
    launches: list[str] = []
    constructed: list[object] = []
    monkeypatch.setattr(omar_shared.launch, "launch", lambda *args, **kwargs: launches.append("replay"))
    monkeypatch.setattr(
        omar_shared.SecondRevision,
        "pending",
        lambda arm: constructed.append(arm) or [(None, None)],
    )

    status, arms = omar_shared.advance(baseline, prefix=prefix)

    assert status == f"{prefix}-feedback needs paid calls; set launch_paid=True after reviewing the bundle"
    assert arms == {}
    assert len(constructed) == 1
    assert constructed[0].data.train and constructed[0].data.test
    assert not launches, "default notebook invocation must not start either replay or a paid revision"


def test_advance_fails_closed_when_source_artifact_changes(
    dataset_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = ready_baseline(dataset_path)
    prefix = "omar-shared-test"
    write_source_bundle(baseline, prefix)
    monkeypatch.setattr(omar_shared.launch, "launch", lambda *args, **kwargs: None)

    rows = [json.loads(line) for line in baseline.records_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["changed"] = True
    baseline.records_path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="source bundle dependencies changed"):
        omar_shared.advance(baseline, prefix=prefix)
