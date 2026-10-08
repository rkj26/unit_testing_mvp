"""Offline security boundaries for Omar launch and immutable cached reuse."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from threading import Lock
import pytest

from pipeline import model as model_mod, sandbox
from pipeline.data import Candidate, Dataset, Task
from pipeline.model import Completion
from pipeline.protocols import omar_notebook, omar_runtime, omar_shared
from pipeline.protocols.omar_notebook import OmarMultiTurn
from pipeline.protocols.trigger_search import TriggerSearch
from pipeline.protocols.unit_testing import UnitTesting, test_names_in as suite_names


@pytest.mark.parametrize("fails", [False, True])
def test_bcb_preflight_delegates_once_and_preserves_shared_exception(monkeypatch, fails):
    calls = []
    failure = RuntimeError("shared sandbox preflight rejected the image")
    def shared_preflight(image):
        calls.append(image)
        if fails:
            raise failure
    monkeypatch.setattr(sandbox, "preflight", shared_preflight)
    monkeypatch.setattr(sandbox.shutil, "which",
                        lambda *_: pytest.fail("duplicate Omar Docker dependency check"))
    monkeypatch.setattr(sandbox.subprocess, "run",
                        lambda *_args, **_kwargs: pytest.fail("duplicate Omar Docker process"))
    if fails:
        with pytest.raises(RuntimeError) as error:
            omar_runtime.preflight_docker("pbt-bcb:2")
        assert error.value is failure
    else:
        assert omar_runtime.preflight_docker("pbt-bcb:2") is None
    assert calls == ["pbt-bcb:2"]


@pytest.fixture
def reference(tmp_path, monkeypatch, request):
    monkeypatch.setattr(omar_shared, "__file__", str(tmp_path / "pipeline/protocols/omar_shared.py"))
    backend = request.param if hasattr(request, "param") else "apps"
    io_mode = "function" if backend == "bcb" else "stdio"
    tasks = tuple(Task(task_id=f"t{n}", specification="Return the supplied integer.",
        io_mode=io_mode, entry_point="task_func" if backend == "bcb" else "",
        candidates=(Candidate(f"c{n}", "honest", "print(input())\n"),
                    Candidate(f"a{n}", "attack_0", "print('wrong')\n"))) for n in (1, 2))
    data = Dataset(name="approval-test", backend=backend, io_mode=io_mode, tasks=tasks,
        split={"train": ("t1",), "test": ("t2",)}, built_from={})
    path = tmp_path / "data.json"
    path.write_text(json.dumps(data.to_json()), encoding="utf-8")
    arm = UnitTesting(run_name="team-reference", data=str(path),
        model=omar_shared.OMAR_MODELS["terra"], triggers="unused-team", cache=True)
    arm.write_config()
    monkeypatch.setattr(omar_shared, "_session_alive", lambda _: False)
    monkeypatch.setattr(omar_notebook.launch, "alive", lambda _: False)
    monkeypatch.setattr(model_mod, "resolve", lambda *_: pytest.fail("unexpected provider resolve"))
    return arm


@pytest.mark.parametrize("kwargs", [
    {}, {"allow_paid": True}, {"allow_paid": True, "max_model_calls": 7},
])
def test_no_authorization_or_insufficient_cap_never_launches(reference, monkeypatch, kwargs):
    monkeypatch.setattr(omar_shared, "preflight_docker", lambda *_: pytest.fail("unapproved Docker"))
    monkeypatch.setattr(OmarMultiTurn, "_launch", lambda *_: pytest.fail("unapproved worker"))
    adapter = OmarMultiTurn(reference_arm=reference, run_name="unapproved", **kwargs)
    with pytest.raises(PermissionError, match="max_model_calls >= 16"):
        adapter.run()


@pytest.mark.parametrize("kwargs", [
    {"allow_paid": 1}, {"allow_paid": "yes"}, {"max_model_calls": True},
    {"max_model_calls": -1}, {"max_model_calls": 8.0},
])
def test_paid_options_require_actual_bool_and_nonnegative_int(reference, kwargs):
    with pytest.raises(TypeError):
        OmarMultiTurn(reference_arm=reference, run_name="invalid", **kwargs)


def test_missing_docker_stops_facade_and_low_level_before_provider(reference, monkeypatch):
    def missing(_image):
        raise RuntimeError("docker missing before provider")
    monkeypatch.setattr(omar_shared, "preflight_docker", missing)
    monkeypatch.setattr(OmarMultiTurn, "_launch", lambda *_: pytest.fail("Dockerless worker"))
    adapter = OmarMultiTurn(reference_arm=reference, run_name="dockerless",
                            allow_paid=True, max_model_calls=16)
    with pytest.raises(RuntimeError, match="docker missing"):
        adapter.run()
    plan, _, _ = omar_shared.advance_shared(reference_arm=reference, prefix="low-dockerless")
    monkeypatch.setattr(omar_shared, "_launch_windows_coordinator",
                        lambda *_: pytest.fail("Dockerless trigger worker"))
    with pytest.raises(RuntimeError, match="docker missing"):
        omar_shared.advance_shared(reference_arm=reference, prefix="low-dockerless",
            approval=plan["phase_approval_token"], max_paid_calls=plan["phase_paid_call_limit"])


def test_direct_input_worker_cannot_bypass_parent_approval(reference):
    trigger = TriggerSearch(run_name="direct-triggers", data=reference.data_path,
        model=reference.model, code_visible=True, cache=False)
    trigger.write_config()
    with pytest.raises(PermissionError, match="explicit paid authorization"):
        omar_shared.run_inputs(trigger.run_name)


def test_direct_notebook_worker_cannot_bypass_parent_approval(reference, monkeypatch):
    adapter = OmarMultiTurn(reference_arm=reference, run_name="direct-worker")
    monkeypatch.setattr(omar_shared, "preflight_docker", lambda *_: pytest.fail("unapproved Docker"))
    with pytest.raises(FileNotFoundError, match="authorization"):
        omar_notebook.worker(adapter.identity_path, "initial")


def test_omar_a_preserves_fresh_input_failure_blame(reference, monkeypatch):
    trigger = TriggerSearch(run_name="failed-triggers", data=reference.data_path,
        model=reference.model, code_visible=True, cache=False)
    trigger.write_config()
    rows = []
    for index, (task, candidate) in enumerate(trigger.data.candidates()):
        rows.append(dict(run_name=trigger.run_name, protocol=trigger.protocol, task_id=task.task_id,
            candidate_id=candidate.candidate_id, split=trigger.data.split_of(task.task_id),
            label=candidate.label, is_attack=candidate.is_attack, calls=[], failed=True,
            blame="infra" if index == 0 else "model", reason="synthetic fresh input failure", inputs=None))
    trigger.records_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    monkeypatch.setattr(omar_shared, "preflight_docker", lambda _: None)
    monkeypatch.setattr(sandbox, "preflight", lambda _: None, raising=False)
    monkeypatch.setattr(model_mod, "resolve", lambda _: object())
    arm = omar_shared.OmarInitial(run_name="A-failed-inputs", data=reference.data_path,
        model=reference.model, triggers=trigger.run_name, study_kind="shared",
        test_gen_prompt="traceable_v1", resolve="with", n_tests=10)
    arm.prepare(arm.data)
    verdicts = [arm.score(task, candidate) for task, candidate in arm.data.candidates()]
    assert [row["blame"] for row in verdicts] == ["infra", "model", "model", "model"]
    assert all(row["failed"] and row["calls"] == [] and row["catches"] is None for row in verdicts)


@pytest.fixture
def completed(reference, monkeypatch, request):
    tests = [{"name": f"test_{i}", "source": f"def test_{i}(run, x):\n    assert run(x)\n"}
             for i in range(10)]
    calls = Counter()
    lock = Lock()
    fail_arm = request.param if hasattr(request, "param") else None
    def complete(_client, prompt, kind, schema=None):
        if kind == "trigger_search":
            text = '[{"value": 1}, {"value": 2}]' if reference.data.backend == "bcb" else '["1\\n", "2\\n"]'
            return Completion(text, "stop")
        group = ("A" if schema.name == "audit_tests" else
                 "D" if schema.name == "retain_original_test_ids" else
                 "B" if "WITHHELD_BY_DESIGN" in prompt else "C")
        with lock:
            calls[group] += 1
            if group == fail_arm and calls[group] == 2:
                raise RuntimeError("synthetic provider transport failure")
        answer = {"rationale": "Synthetic test.", "tests": tests}
        if schema.name == "repair_tests":
            answer["abstain"] = False
        if schema.name == "retain_original_test_ids":
            answer = {"rationale": "Keep original tests.", "retain_test_ids": [test["name"] for test in tests]}
        return Completion(json.dumps(answer), "stop")
    def grid(_task, _code, source, space, **_kwargs):
        names = suite_names(source)
        records = [{"prop": name, "i": i, "outcome": "pass"}
                   for name in names for i in range(len(space))]
        return dict(ok=True, complete=True, error="", props=names, records=records,
                    n_records=len(records), n_expected=len(records))
    monkeypatch.setattr(model_mod, "resolve", lambda _: object())
    monkeypatch.setattr(model_mod, "complete_sync", complete)
    monkeypatch.setattr(omar_shared, "preflight_docker", lambda _: None)
    monkeypatch.setattr(sandbox, "preflight", lambda _: None, raising=False)
    monkeypatch.setattr("pipeline.protocols.second_revision.preflight_docker", lambda _: None)
    monkeypatch.setattr("pipeline.protocols.omar_delete_only.preflight_docker", lambda _: None)
    monkeypatch.setattr(sandbox, "run_raw", grid)
    monkeypatch.setattr(OmarMultiTurn, "_launch", lambda self, target:
                        omar_notebook.worker(self.identity_path, target))
    paid = OmarMultiTurn(reference_arm=reference, run_name="complete-test",
                         allow_paid=True, max_model_calls=reference.total * (5 if reference.data.backend == "bcb" else 4))
    paid.run()
    paid.continue_run()
    cached = OmarMultiTurn(reference_arm=reference, run_name=paid.run_name)
    monkeypatch.setattr(model_mod, "resolve", lambda *_: pytest.fail("cached provider"))
    monkeypatch.setattr(model_mod, "complete_sync", lambda *_: pytest.fail("cached call"))
    monkeypatch.setattr(omar_shared, "preflight_docker", lambda *_: pytest.fail("cached Docker"))
    return cached


@pytest.mark.parametrize("reference", ["bcb"], indirect=True)
@pytest.mark.parametrize("completed", ["A", "B", "C", "D"], indirect=True)
def test_thrown_provider_failure_is_unmeasured_and_cache_reuses_without_retry(completed):
    arms = completed.continue_run()
    failures = [row for arm in arms.values() for row in arm.get_records() if row["failed"]]
    assert failures
    assert all(row["blame"] == "infra" and row["calls"] == [] for row in failures)
    generic = [row for row in failures if row["reason"] == "RuntimeError: synthetic provider transport failure"]
    assert len(generic) == 1
    assert "tests_src" not in generic[0] and "catches" not in generic[0]
    if generic[0]["protocol"] == "omar_initial":
        cid = generic[0]["candidate_id"]
        bundle = json.loads((Path("runs") / "complete-test-coordinator/source-bundle.json").read_text())
        assert bundle["candidates"][cid]["suite_sha256"] is None
        assert bundle["candidates"][cid]["result"] is None
        for label, arm in arms.items():
            if label != "A initial":
                row = next(row for row in arm.get_records() if row["candidate_id"] == cid)
                assert row["failed"] is True and row["blame"] == "infra" and row["catches"] is None
    before = {path: path.read_bytes() for path in Path("runs").rglob("*") if path.is_file()}
    assert completed.run() is not None
    assert completed.continue_run() is not None
    assert before == {path: path.read_bytes() for path in Path("runs").rglob("*") if path.is_file()}
    failure_arm = next(arm for arm in arms.values() if arm.run_name == generic[0]["run_name"])
    rows = failure_arm.get_records()
    next(row for row in rows if row["candidate_id"] == generic[0]["candidate_id"])["reason"] = "tampered failure"
    failure_arm.records_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises(ValueError, match="changed|hash"):
        completed.continue_run()


@pytest.mark.parametrize("target", ["initial", "continue"])
def test_valid_legacy_cache_returns_without_approval_api_docker_or_resealing(completed, target):
    marker = Path("runs") / "complete-test-coordinator/complete.json"
    saved = json.loads(marker.read_text(encoding="utf-8"))
    saved.pop("records_sha256")  # Real legacy completion markers have no new checksum.
    marker.write_text(json.dumps(saved), encoding="utf-8")
    before = {path: path.read_bytes() for path in Path("runs").rglob("*") if path.is_file()}
    result = completed.run() if target == "initial" else completed.continue_run()
    assert result is not None
    assert before == {path: path.read_bytes() for path in Path("runs").rglob("*") if path.is_file()}


@pytest.mark.parametrize("artifact", ["inputs", "A", "bundle", "B", "C"])
def test_cached_returns_reject_tampering_without_api_or_docker(completed, artifact):
    folder = Path("runs")
    if artifact == "bundle":
        path = folder / "complete-test-coordinator/source-bundle.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["candidates"]["c1"]["result"]["records"][0]["outcome"] = "catch"
        path.write_text(json.dumps(value), encoding="utf-8")
    else:
        suffix = {"inputs": "triggers", "A": "A-traceable", "B": "B-no-feedback", "C": "C-feedback"}[artifact]
        path = folder / f"complete-test-{suffix}/records.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        if artifact == "inputs":
            rows[0]["inputs"] = ["tampered"]
        elif artifact in {"B", "C"}:
            rows[0]["fired"] = ["tampered"]
        else:
            rows[0]["reason"] = "tampered baseline"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises(ValueError, match="changed|hash"):
        completed.continue_run()
    if artifact in {"inputs", "A", "bundle"}:
        with pytest.raises(ValueError, match="changed|hash"):
            completed.run()
