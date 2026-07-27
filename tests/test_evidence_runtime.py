import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import evidence_runtime
from artifact_io import atomic_write_text, safe_path_component
from evidence import (
    TM,
    MonitorEvidence,
    PBTExecutionEvidence,
    PBTTestSuite,
    candidate_sha256,
    sha256_text,
    task_spec_sha256,
)
from evidence_runtime import RuntimeEvidenceStore


def _records():
    task_id = "Task/1"
    source = "def solve(x): return x\n"
    digest = candidate_sha256(source)
    suite = PBTTestSuite(
        task_id=task_id,
        task_spec_sha256=task_spec_sha256(
            description="identity",
            entry_point="solve",
            starter_code="def solve(x): ...",
        ),
        prompt="write an identity property",
        script="def test_identity():\n    assert solve(1) == 1\n",
        hypothesis_seed=7,
        model_name="mockllm/model",
    )
    execution = PBTExecutionEvidence.from_raw(
        task_id=task_id,
        candidate_sha256=digest,
        suite_sha256=suite.suite_sha256,
        raw_result={"returncode": 0, "stdout": "1 passed", "stderr": "", "error": None},
    )
    monitor = MonitorEvidence(
        task_id=task_id,
        candidate_sha256=digest,
        kind=TM,
        suspicion_score=0.1,
        reason="looks ordinary",
        model_name="mockllm/model",
        prompt_sha256=sha256_text("tm prompt"),
    )
    return task_id, digest, suite, execution, monitor


def test_runtime_store_persists_one_suite_and_candidate_results(tmp_path):
    task_id, digest, suite, execution, monitor = _records()
    store = RuntimeEvidenceStore(tmp_path)

    store.put_suite(suite)
    store.put_pbt(execution)
    store.put_monitor(monitor)
    bundles = store.write_bundles({task_id: {digest: "honest"}})

    assert bundles[task_id].candidate(digest).tm == monitor
    task_dirs = [path for path in tmp_path.iterdir() if path.is_dir()]
    assert len(task_dirs) == 1
    assert (task_dirs[0] / "pbt" / "test.py").read_text() == suite.script
    assert (task_dirs[0] / "pbt" / "results" / f"{digest}.json").is_file()
    assert (task_dirs[0] / "bundle.json").is_file()


def test_runtime_store_reuses_identical_records(tmp_path):
    task_id, digest, suite, execution, monitor = _records()
    store = RuntimeEvidenceStore(tmp_path)

    assert store.put_suite(suite) == store.put_suite(suite)
    assert store.put_pbt(execution) == store.put_pbt(execution)
    assert store.put_monitor(monitor) == store.put_monitor(monitor)
    assert store.get_suite(task_id) == suite
    assert store.get_pbt(task_id, digest) == execution


@pytest.mark.parametrize(
    ("lookup", "message"),
    [
        ({"task_spec_sha256": "0" * 64}, "task specification"),
        ({"prompt_sha256": "0" * 64}, "rendered prompt"),
        ({"hypothesis_seed": 8}, "Hypothesis seed"),
        ({"model_name": "different/model"}, "generator model"),
    ],
)
def test_suite_reuse_requires_exact_producer_identity(tmp_path, lookup, message):
    task_id, _, suite, _, _ = _records()
    store = RuntimeEvidenceStore(tmp_path)
    store.put_suite(suite)

    with pytest.raises(ValueError, match=message):
        store.get_suite(task_id, **lookup)


def test_pbt_and_monitor_reuse_validate_their_dependencies(tmp_path):
    task_id, digest, suite, execution, monitor = _records()
    store = RuntimeEvidenceStore(tmp_path)
    store.put_suite(suite)
    store.put_pbt(execution)
    store.put_monitor(monitor)

    with pytest.raises(ValueError, match="different shared suite"):
        store.get_pbt(task_id, digest, suite_sha256="0" * 64)
    with pytest.raises(ValueError, match="model"):
        store.get_monitor(task_id, digest, TM, model_name="different/model")
    with pytest.raises(ValueError, match="rendered prompt"):
        store.get_monitor(task_id, digest, TM, prompt_sha256="0" * 64)


def test_artifact_root_is_bound_to_one_producer_config(tmp_path):
    first = RuntimeEvidenceStore(
        tmp_path, producer_config={"model": "mockllm/model", "seed": 7}
    )
    first_digest = first.producer_config_sha256
    first.close()
    same = RuntimeEvidenceStore(
        tmp_path, producer_config={"seed": 7, "model": "mockllm/model"}
    )

    assert first_digest == same.producer_config_sha256
    manifest = json.loads((tmp_path / "producer_config.json").read_text())
    assert manifest["producer_config_sha256"] == first_digest
    same.close()
    with pytest.raises(ValueError, match="different producer settings"):
        RuntimeEvidenceStore(
            tmp_path, producer_config={"model": "mockllm/model", "seed": 8}
        )


def test_store_cannot_be_rebound_after_population(tmp_path):
    _, _, suite, _, _ = _records()
    store = RuntimeEvidenceStore(tmp_path)
    store.put_suite(suite)

    with pytest.raises(RuntimeError, match="before evidence is populated"):
        store.bind_producer_config({"seed": 7})


def test_artifact_root_allows_only_one_active_store(tmp_path):
    root = tmp_path / "evidence"
    first = RuntimeEvidenceStore(root, producer_config={"seed": 7})

    with pytest.raises(RuntimeError, match="already has an active store"):
        RuntimeEvidenceStore(root / ".." / "evidence", producer_config={"seed": 7})

    first.close()
    with RuntimeEvidenceStore(root, producer_config={"seed": 7}) as replacement:
        assert replacement.producer_config_sha256 is not None

    with pytest.raises(RuntimeError, match="closed"):
        replacement.get_suite("task")


def test_failed_suite_persistence_is_not_published_in_memory(tmp_path, monkeypatch):
    task_id, _, suite, _, _ = _records()
    store = RuntimeEvidenceStore(tmp_path)
    real_write = evidence_runtime.atomic_write_text

    def fail_manifest(path, value):
        if Path(path).name == "suite.json":
            raise OSError("simulated disk failure")
        real_write(path, value)

    monkeypatch.setattr(evidence_runtime, "atomic_write_text", fail_manifest)

    with pytest.raises(OSError, match="simulated disk failure"):
        store.put_suite(suite)
    assert store.get_suite(task_id) is None
    assert not list(tmp_path.glob("*/pbt/suite.json"))


def test_suite_generation_is_single_flight_per_task():
    async def exercise():
        task_id, _, suite, _, _ = _records()
        store = RuntimeEvidenceStore()
        calls = 0

        async def produce():
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return suite

        arguments = {
            "task_spec_sha256": suite.task_spec_sha256,
            "prompt_sha256": suite.prompt_sha256,
            "hypothesis_seed": suite.hypothesis_seed,
            "model_name": suite.model_name,
            "producer": produce,
        }
        results = await asyncio.gather(
            *(store.get_or_create_suite(task_id, **arguments) for _ in range(12))
        )
        return calls, results, suite

    calls, results, suite = asyncio.run(exercise())
    assert calls == 1
    assert results == [suite] * 12


def test_runtime_store_reuses_cached_evidence_across_sequential_event_loops():
    task_id, _, suite, _, _ = _records()
    store = RuntimeEvidenceStore()
    calls = 0

    async def produce():
        nonlocal calls
        calls += 1
        return suite

    arguments = {
        "task_spec_sha256": suite.task_spec_sha256,
        "prompt_sha256": suite.prompt_sha256,
        "hypothesis_seed": suite.hypothesis_seed,
        "model_name": suite.model_name,
        "producer": produce,
    }

    assert asyncio.run(store.get_or_create_suite(task_id, **arguments)) == suite
    assert asyncio.run(store.get_or_create_suite(task_id, **arguments)) == suite
    assert calls == 1


def test_shared_path_component_blocks_traversal_and_preserves_identity():
    first = safe_path_component("../task/a", fallback="task")
    second = safe_path_component("../../task/a", fallback="task")

    assert "/" not in first and ".." not in first
    assert first != second


def test_atomic_writes_use_unique_temporaries(tmp_path):
    path = tmp_path / "result.json"
    values = [f"value-{index}" for index in range(24)]
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda value: atomic_write_text(path, value), values))

    assert path.read_text() in values
    assert list(tmp_path.glob(".result.json.tmp-*")) == []
