"""Shared-workspace SecondRevision checks that make no model or Docker calls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from build_dataset import build
from pipeline.protocols.second_revision import SecondRevision
from pipeline.protocols.trigger_search import TriggerSearch
from pipeline.protocols.unit_testing import UnitTesting


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def dataset_path(tmp_path: Path) -> Path:
    path = tmp_path / "mini.json"
    document = build(ROOT / "apps_pool_hard10.json", ROOT / "splits" / "smoke_3.json", "apps", "revision-mini")
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _object_sha(value: object) -> str:
    return _sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _artifacts(dataset_path: Path, *, shared_workspace: bool = True) -> tuple[SecondRevision, str]:
    baseline_name, trigger_name, revised_name = "rev-A", "rev-inputs", "rev-B"
    shared_cache = shared_workspace
    baseline = UnitTesting(
        run_name=baseline_name, data=str(dataset_path), model="mockllm/model",
        triggers=trigger_name, n_tests=10, code_visible=True,
        test_gen_prompt="traceable_v1", resolve="with", reasoning="low", seed=300,
        max_tokens=32000, call_seconds=300, sandbox_seconds=720,
        docker_image="python:3.12-slim", cache=shared_cache,
    )
    baseline.write_config()
    trigger = TriggerSearch(run_name=trigger_name, data=str(dataset_path), model="mockllm/model",
                           num_inputs=10, code_visible=True, reasoning="low", seed=300, cache=False)
    trigger.write_config()
    candidates = list(baseline.data.candidates())
    unusable_id = candidates[0][1].candidate_id
    trigger_rows = []
    baseline_rows = []
    bundle_candidates = {}
    for task, candidate in candidates:
        failed = candidate.candidate_id == unusable_id
        trigger_rows.append({"run_name": trigger_name, "protocol": "trigger_search",
                             "split": baseline.data.split_of(task.task_id), "task_id": task.task_id,
                             "candidate_id": candidate.candidate_id,
                             "failed": failed, "blame": "model" if failed else None,
                             "reason": "no parseable input" if failed else None,
                             "inputs": [] if failed else ["1\n"], "calls": []})
        baseline_row = {"run_name": baseline_name, "protocol": "omar_initial",
                        "split": baseline.data.split_of(task.task_id), "task_id": task.task_id,
                        "candidate_id": candidate.candidate_id, "calls": [], "failed": False,
                        "blame": None, "reason": None, "tests_src": None}
        baseline_rows.append(baseline_row)
        bundle_candidates[candidate.candidate_id] = {
            "source_record_sha256": _object_sha(baseline_row),
            "inputs_sha256": None if failed else _object_sha(["1\n"]),
            "code_sha256": _sha(candidate.code.encode()),
            "suite_sha256": None,
            "result": None,
        }
    trigger.records_path.write_text("".join(json.dumps(row) + "\n" for row in trigger_rows), encoding="utf-8")
    baseline.records_path.write_text("".join(json.dumps(row) + "\n" for row in baseline_rows), encoding="utf-8")
    bundle_path = Path("runs/revision-source-bundle.json")
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    paths = {
        "dataset_sha256": Path(dataset_path),
        "source_config_sha256": baseline.config_path,
        "source_records_sha256": baseline.records_path,
        "input_records_sha256": trigger.records_path,
    }
    bundle = {"schema_version": 1, "candidates": bundle_candidates,
              **{key: _sha(path.read_bytes()) for key, path in paths.items()}}
    bundle_path.write_text(json.dumps(bundle, sort_keys=True), encoding="utf-8")
    revision = SecondRevision(
        run_name=revised_name, data=str(dataset_path), model="mockllm/model", triggers=trigger_name,
        baseline_run=baseline_name, source_bundle=str(bundle_path),
        source_bundle_sha256=_sha(bundle_path.read_bytes()), feedback_visible=False,
        max_candidates=baseline.total, shared_workspace=shared_workspace,
        n_tests=10, code_visible=False, test_gen_prompt="traceable_v1", resolve="with",
        reasoning="low", seed=300, max_tokens=32000, call_seconds=300, sandbox_seconds=720,
        docker_image="python:3.12-slim", cache=shared_cache,
    )
    return revision, unusable_id


def test_shared_mode_records_unusable_trigger_as_failed_without_model_call(
    dataset_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    revision, unusable_id = _artifacts(dataset_path)
    preflighted = []
    monkeypatch.setattr("pipeline.protocols.second_revision.preflight_docker", preflighted.append)
    monkeypatch.setattr("pipeline.protocols.second_revision.model_mod.resolve", lambda runtime: object())
    monkeypatch.setattr("pipeline.protocols.second_revision.model_mod.complete_sync",
                        lambda *args, **kwargs: pytest.fail("unusable candidate must not call a model"))
    monkeypatch.setattr("pipeline.protocols.second_revision.sandbox.run_raw",
                        lambda *args, **kwargs: pytest.fail("unusable candidate must not run Docker"))

    revision.prepare(revision.data)
    task, candidate = next((task, candidate) for task, candidate in revision.data.candidates()
                           if candidate.candidate_id == unusable_id)
    record = revision.score(task, candidate)

    assert preflighted == ["python:3.12-slim"]
    assert revision.config()["params"]["shared_workspace"] is True
    assert revision._runtime().http_retries == 1
    assert revision.cache is True
    assert record["failed"] is True
    assert record["blame"] == "model"
    assert record["calls"] == []
    assert record["eligible"] is False
    assert record["fired"] is None


def test_historical_mode_still_rejects_unusable_trigger_inputs(dataset_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch) -> None:
    document = json.loads(dataset_path.read_text(encoding="utf-8"))
    document["split"]["test"] += document["split"]["train"]
    document["split"]["train"] = []
    dataset_path.write_text(json.dumps(document), encoding="utf-8")
    revision, _ = _artifacts(dataset_path, shared_workspace=False)
    monkeypatch.setattr("pipeline.protocols.second_revision.model_mod.resolve",
                        lambda runtime: pytest.fail("validation must precede model resolution"))
    monkeypatch.setattr("pipeline.protocols.second_revision.preflight_docker",
                        lambda image: pytest.fail("unusable-input validation must fail first"))

    with pytest.raises(ValueError, match="require the same reviewed nonempty"):
        revision.prepare(revision.data)


def _construct_revision(dataset_path: Path, *, shared_workspace, max_candidates=100):
    return SecondRevision(
        run_name="population-guard", data=str(dataset_path), model="mockllm/model",
        triggers="unused-inputs", baseline_run="unused-source", source_bundle="unused.json",
        source_bundle_sha256="a" * 64, feedback_visible=False,
        max_candidates=max_candidates, shared_workspace=shared_workspace, cache=False,
    )


@pytest.mark.parametrize("shared_workspace", [False, True])
def test_only_shared_workspace_accepts_mixed_train_test_population(dataset_path, shared_workspace):
    if shared_workspace:
        revision = _construct_revision(dataset_path, shared_workspace=True)
        assert revision.data.train and revision.data.test
    else:
        with pytest.raises(ValueError, match="historical.*test-only"):
            _construct_revision(dataset_path, shared_workspace=False)


def test_historical_workspace_still_accepts_a_test_only_population(dataset_path):
    document = json.loads(dataset_path.read_text(encoding="utf-8"))
    document["split"]["test"] += document["split"]["train"]
    document["split"]["train"] = []
    dataset_path.write_text(json.dumps(document), encoding="utf-8")
    revision = _construct_revision(dataset_path, shared_workspace=False)
    assert not revision.data.train and revision.data.test


@pytest.mark.parametrize("shared_workspace", [False, True])
def test_every_workspace_requires_a_test_split(dataset_path, shared_workspace):
    document = json.loads(dataset_path.read_text(encoding="utf-8"))
    document["split"]["train"] += document["split"]["test"]
    document["split"]["test"] = []
    dataset_path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="test split"):
        _construct_revision(dataset_path, shared_workspace=shared_workspace)


@pytest.mark.parametrize("shared_workspace", [False, True])
def test_every_workspace_enforces_its_candidate_cap(dataset_path, shared_workspace):
    document = json.loads(dataset_path.read_text(encoding="utf-8"))
    document["split"]["test"] += document["split"]["train"]
    document["split"]["train"] = []
    dataset_path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="candidate cap"):
        _construct_revision(dataset_path, shared_workspace=shared_workspace, max_candidates=1)


@pytest.mark.parametrize("shared_workspace", [None, 0, 1, "yes", {}])
def test_shared_workspace_bool_is_validated_before_any_dataset_access(tmp_path, shared_workspace):
    with pytest.raises(ValueError, match="shared_workspace must be an explicit boolean"):
        _construct_revision(tmp_path / "does-not-exist.json", shared_workspace=shared_workspace)
