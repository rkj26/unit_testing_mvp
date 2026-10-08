"""Offline checks for Omar A/B/C on the shared APPS uniform-400 checkout."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from collections import Counter
from pathlib import Path

import pytest

from build_dataset import build
from pipeline import model as model_mod, sandbox
from pipeline.model import Completion
from pipeline.protocols import REGISTRY, UnitTesting
from pipeline.protocols import omar_shared
from pipeline.protocols import omar_runtime
from pipeline.protocols.trigger_search import TriggerSearch
from pipeline.protocols.unit_testing import test_names_in as _test_names_in


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def isolated_shared_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Read saved team inputs into a disposable checkout; never write real runs."""
    paths = (
        "data/apps_uniform400.json",
        "runs/ut-u400-property-10/config.json",
        "runs/trig-u400/config.json",
        "runs/trig-u400/records.jsonl",
    )
    for relative in paths:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(omar_shared, "__file__",
                        str(tmp_path / "pipeline/protocols/omar_shared.py"))
    return tmp_path


def _omar_cells() -> tuple[list[str], str, str]:
    notebook = json.loads((ROOT / "notebooks/results_uniform400.ipynb").read_text(encoding="utf-8"))
    sources = ["".join(cell["source"]) for cell in notebook["cells"]]
    initial = [source for source in sources if "omar_initial = omar.run()" in source]
    continuation = [source for source in sources if "omar_arms = omar.continue_run()" in source]
    assert len(initial) == len(continuation) == 1
    return sources, initial[0], continuation[0]


def test_omar_initial_and_continuation_cells_bracket_the_shared_population_step() -> None:
    sources, initial, continuation = _omar_cells()
    property_arm = next(i for i, source in enumerate(sources) if "ut_property.run()" in source)
    roster = next(i for i, source in enumerate(sources) if "ARMS = {**monitors, **units}" in source)
    initial_index = sources.index(initial)
    continuation_index = sources.index(continuation)
    plots = next(i for i, source in enumerate(sources) if "## 5 · Every threshold" in source)
    assert property_arm + 2 == initial_index
    assert initial_index < roster < continuation_index < plots
    assert 'OMAR_MODEL = "terra"  # or "deepseek"' in initial
    assert "omar_initial = omar.run()" in initial
    assert "omar_arms = omar.continue_run()" in continuation
    assert "OMAR_APPROVAL" not in initial + continuation
    assert "OMAR_MAX_PAID_CALLS" not in initial + continuation
    assert "SCORED_BY_ALL = new_shared" in continuation
    compile(initial, "results_uniform400.ipynb Omar initial cell", "exec")
    compile(continuation, "results_uniform400.ipynb Omar continuation cell", "exec")


def test_omar_cell_adds_only_complete_arms_to_the_existing_population() -> None:
    _, _, cell = _omar_cells()
    cell = cell.split("# Omar strict complete/error-free paired analysis (zero API calls)")[0]

    class Arm:
        def __init__(self, ok: set[str]) -> None:
            self.ok = ok

    class DataFrame:
        def __init__(self, rows: object) -> None:
            self.rows = rows

        def set_index(self, _: str) -> DataFrame:
            return self

    team = Arm({"honest", "attack"})
    added = {label: Arm({"honest"}) for label in ("A initial", "B no feedback", "C feedback")}
    runner = type("Omar", (), {"continue_run": lambda self: added})()
    coverage = lambda arm: {"records": 2, "ok": arm.ok, "blame": Counter(), "partial": 0}
    namespace = {
        "DATASET": "data/apps_uniform400.json", "Path": Path, "ut_property": team,
        "omar": runner,
        "units": {"team": team}, "ARMS": {"team": team},
        "COVERAGE": {"team": coverage(team)}, "SCORED_BY_ALL": {"honest", "attack"},
        "EVERY_CANDIDATE": 2, "ARM_STYLE": {}, "coverage": coverage,
        "pd": type("Pandas", (), {"DataFrame": DataFrame}),
    }
    exec(cell, namespace)
    assert set(namespace["ARMS"]) == {"team", *added}
    assert namespace["SCORED_BY_ALL"] == {"honest"}
    assert set(namespace["units"]) == {"team", *added}


def test_real_u400_plan_launches_no_paid_calls_and_keeps_artifacts_isolated(
    monkeypatch: pytest.MonkeyPatch,
    isolated_shared_checkout: Path,
) -> None:
    monkeypatch.setattr(omar_shared.launch, "alive", lambda _: False)
    docker_checks: list[str] = []
    monkeypatch.setattr(omar_shared, "preflight_docker", docker_checks.append)
    launches: list[list[str]] = []
    monkeypatch.setattr(omar_shared, "_launch_windows_coordinator",
                        lambda _name, command: launches.append(command))
    monkeypatch.setattr(omar_shared.os, "name", "nt")
    monkeypatch.setattr(omar_shared.subprocess, "DETACHED_PROCESS", 0x00000008,
                        raising=False)
    monkeypatch.setattr(omar_shared.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200,
                        raising=False)
    reference = UnitTesting.attach("ut-u400-property-10")
    prefix = f"test-omar-preflight-{uuid.uuid4().hex[:12]}"
    plans = {}
    for key, model in omar_shared.OMAR_MODELS.items():
        current_prefix = f"{prefix}-{key}"
        plan, status, arms = omar_shared.advance_shared(
            reference_arm=reference, prefix=current_prefix, model=model)
        plans[key] = plan
        assert (plan["candidate_count"], plan["pending_inputs"]) == (800, 800)
        assert plan["next_phase"] == "fresh-inputs"
        assert plan["phase_paid_call_limit"] == 800
        assert plan["workflow_max_logical_calls"] == 3200
        assert plan["model"] == plan["input_model"] == model
        assert plan["triggers"] == f"{current_prefix}-triggers"
        assert plan["input_num_inputs"] == 30
        assert plan["runtime_settings"]["cache"] is False
        assert f"No paid call launched" in status and arms == {}
        trigger_config = json.loads((isolated_shared_checkout / "runs" / plan["triggers"] / "config.json").read_text())
        assert trigger_config["model"] == model
        assert trigger_config["params"]["num_inputs"] == 30
        assert not (isolated_shared_checkout / "runs" / plan["triggers"] / "records.jsonl").exists()
        assert not (isolated_shared_checkout / "runs" / f"{current_prefix}-coordinator").exists()
        assert not (ROOT / "runs" / plan["triggers"]).exists()
    assert plans["terra"]["phase_approval_token"] != plans["deepseek"]["phase_approval_token"]
    terra_prefix = f"{prefix}-terra"
    same, _, _ = omar_shared.advance_shared(
        reference_arm=reference, prefix=terra_prefix,
        model=omar_shared.OMAR_MODELS["terra"])
    assert same["phase_approval_token"] == plans["terra"]["phase_approval_token"]
    launched, status, _ = omar_shared.advance_shared(
        reference_arm=reference, prefix=terra_prefix,
        model=omar_shared.OMAR_MODELS["terra"],
        approval=same["phase_approval_token"], max_paid_calls=800)
    assert launched == same and "Fresh Omar inputs launched" in status
    assert launches and launches[0][-2:] == ["--inputs", f"{terra_prefix}-triggers"]
    assert docker_checks == [reference.docker_image]
    with pytest.raises(ValueError, match="already describes a different run"):
        omar_shared.advance_shared(reference_arm=reference, prefix=terra_prefix,
                                   model=omar_shared.OMAR_MODELS["deepseek"])


def test_study_rejects_trigger_inputs_generated_by_a_different_model(
    monkeypatch: pytest.MonkeyPatch,
    isolated_shared_checkout: Path,
) -> None:
    reference = UnitTesting.attach("ut-u400-property-10")
    other_model = next(model for model in omar_shared.OMAR_MODELS.values()
                       if model != reference.model)
    args = dict(data=reference.data_path, model=other_model,
                triggers=reference.triggers, prefix="test-omar-cross-model-guard",
                docker_image=reference.docker_image, include_delete_only=False,
                settings={"n_tests": 10, "seed": 300, "reasoning": "low",
                          "max_tokens": 8192, "call_seconds": 300,
                          "sandbox_seconds": 120, "cache": False},
                reference_run=reference.run_name)
    with pytest.raises(ValueError, match="different model"):
        omar_shared.study_plan(**args, study_kind="shared")


def test_fresh_inputs_resume_and_exclude_candidates_without_usable_spaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    isolated_shared_checkout: Path,
) -> None:
    monkeypatch.setattr(omar_shared.launch, "alive", lambda _: False)
    docker_checks: list[str] = []
    monkeypatch.setattr(omar_shared, "preflight_docker", docker_checks.append)
    launches: list[list[str]] = []
    monkeypatch.setattr(omar_shared, "_launch_windows_coordinator",
                        lambda _name, command: launches.append(command))
    monkeypatch.setattr(omar_shared.os, "name", "nt")
    monkeypatch.setattr(omar_shared.subprocess, "DETACHED_PROCESS", 0x00000008,
                        raising=False)
    monkeypatch.setattr(omar_shared.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200,
                        raising=False)
    dataset_path = tmp_path / "mini-resume-apps.json"
    document = build(ROOT / "apps_pool_hard10.json", ROOT / "splits/smoke_3.json",
                     "apps", "omar-input-resume")
    dataset_path.write_text(json.dumps(document), encoding="utf-8")
    model = omar_shared.OMAR_MODELS["terra"]
    reference = UnitTesting(run_name=f"resume-reference-{uuid.uuid4().hex[:8]}",
                            data=str(dataset_path), model=model,
                            triggers="unused-reference-trigger", n_tests=10,
                            test_gen_prompt="property", code_visible=True, seed=300,
                            cache=True, docker_image="python:3.12-slim")
    reference.write_config()
    prefix = f"resume-omar-{uuid.uuid4().hex[:8]}"
    trigger = TriggerSearch(run_name=f"{prefix}-triggers", data=str(dataset_path),
                            model=model, seed=300, reasoning="low", code_visible=True,
                            cache=False)
    trigger.write_config()
    candidates = list(trigger.data.candidates())
    partial_rows = [trigger._record(task, candidate,
                                    {"calls": [], "inputs": ["1\n"]})
                    for task, candidate in candidates[:-1]]
    partial_rows[-1] = trigger._record(
        *candidates[len(partial_rows) - 1], {"calls": [], "inputs": []})
    trigger.records_path.write_text(
        "".join(json.dumps(row) + "\n" for row in partial_rows), encoding="utf-8")

    pending, status, arms = omar_shared.advance_shared(
        reference_arm=reference, prefix=prefix, model=model)
    assert pending["pending_inputs"] == 1 and pending["phase_paid_call_limit"] == 1
    assert "No paid call launched" in status and arms == {}
    omar_shared.advance_shared(reference_arm=reference, prefix=prefix, model=model,
                               approval=pending["phase_approval_token"], max_paid_calls=1)
    assert launches and launches[0][-2:] == ["--inputs", trigger.run_name]
    assert docker_checks == [reference.docker_image]

    last_task, last_candidate = candidates[-1]
    failed_input = trigger._record(last_task, last_candidate, {"calls": [], "inputs": []})
    with trigger.records_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(failed_input) + "\n")
    complete, status, arms = omar_shared.advance_shared(
        reference_arm=reference, prefix=prefix, model=model)
    assert complete["unusable_input_count"] == 2
    assert complete["allow_unusable_inputs"] is True
    assert complete["next_phase"] == "A-smoke"
    assert "Paused before A-smoke" in status and arms == {}


def test_omar_initial_checks_docker_before_resolving_a_model(
    monkeypatch: pytest.MonkeyPatch,
    isolated_shared_checkout: Path,
) -> None:
    reference = UnitTesting.attach("ut-u400-property-10")
    monkeypatch.setattr(omar_shared.launch, "alive", lambda _: False)
    plan = omar_shared.study_plan(
        data=reference.data_path, model=reference.model, triggers=reference.triggers,
        prefix=f"test-omar-docker-{uuid.uuid4().hex[:12]}",
        docker_image=reference.docker_image, include_delete_only=False,
        study_kind="shared",
        settings={"n_tests": 10, "seed": 300, "reasoning": "low",
                  "max_tokens": 8192, "call_seconds": 300,
                  "sandbox_seconds": 120, "cache": False},
        allow_unusable_inputs=True, reference_run=reference.run_name)
    arm = omar_shared._baseline(plan)
    monkeypatch.setattr(omar_shared, "preflight_docker", lambda image: (_ for _ in ()).throw(
        RuntimeError(f"Docker unavailable: {image}")))
    monkeypatch.setattr(model_mod, "resolve", lambda runtime: pytest.fail("model resolved before Docker"))
    with pytest.raises(RuntimeError, match="Docker unavailable: python:3.12-slim"):
        arm.prepare(arm.data)


def test_omar_docker_preflight_is_omar_owned_and_does_not_extend_sandbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    class Result:
        returncode = 0
        stdout = b""
        stderr = b""

    monkeypatch.setattr(omar_runtime.shutil, "which", lambda _name: "docker.exe")
    monkeypatch.setattr(omar_runtime.subprocess, "run",
                        lambda command, **kwargs: (calls.append((command, kwargs)), Result())[1])
    omar_runtime.preflight_docker("python:3.12-slim")
    assert calls == [(["docker", "run", "--rm", "python:3.12-slim", "true"],
                      {"capture_output": True, "timeout": 180})]
    assert not hasattr(sandbox, "preflight")


def test_omar_docker_preflight_stops_before_process_when_docker_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(omar_runtime.shutil, "which", lambda _name: None)
    monkeypatch.setattr(omar_runtime.subprocess, "run",
                        lambda *_args, **_kwargs: pytest.fail("must not invoke Docker"))
    with pytest.raises(RuntimeError, match="docker is not on PATH"):
        omar_runtime.preflight_docker("python:3.12-slim")


def test_omar_protocols_are_registered_for_detached_reconstruction() -> None:
    assert REGISTRY["omar_initial"] is omar_shared.OmarInitial
    assert REGISTRY["second_revision"].__name__ == "SecondRevision"
    assert not hasattr(omar_shared, "advance_historical")
    assert not hasattr(omar_shared, "advance_expanded")
    assert not hasattr(omar_shared, "install_bcb_harness")


def test_fresh_process_coordinator_cli_does_not_register_protocol_twice() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "pipeline.protocols.omar_runner", "--help"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--coordinate" in completed.stdout
    assert "--inputs" in completed.stdout


def test_fresh_process_registry_includes_omar_arms() -> None:
    completed = subprocess.run(
        [sys.executable, "-c", "import pipeline.protocols as p; "
         "assert {'omar_initial', 'second_revision'} <= set(p.REGISTRY)"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("model", list(omar_shared.OMAR_MODELS.values()))
def test_synthetic_apps_a_b_c_author_and_revise_through_real_score_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    model: str,
) -> None:
    """Use real prompt/parser/record/freeze/revision logic; fake only provider and Docker."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(omar_shared, "__file__",
                        str(tmp_path / "pipeline/protocols/omar_shared.py"))
    dataset_path = tmp_path / "mini-apps.json"
    document = build(ROOT / "apps_pool_hard10.json", ROOT / "splits/smoke_3.json",
                     "apps", "omar-synthetic")
    dataset_path.write_text(json.dumps(document), encoding="utf-8")
    reference_data = omar_shared.Dataset.load(dataset_path)
    candidates = list(reference_data.candidates())
    assert len(candidates) == 6
    reference = UnitTesting(run_name=f"synthetic-reference-{uuid.uuid4().hex[:8]}",
                            data=str(dataset_path), model=model,
                            triggers="unused-team-trigger", n_tests=10,
                            test_gen_prompt="property", code_visible=True, seed=300,
                            cache=True, docker_image="python:3.12-slim")
    reference.write_config()
    prefix = f"synthetic-omar-{uuid.uuid4().hex[:8]}"
    trigger = TriggerSearch(run_name=f"{prefix}-triggers", data=str(dataset_path),
                            model=model, seed=300, reasoning="low", code_visible=True,
                            cache=False)

    functions = [
        {"name": f"test_value_{i}",
         "source": f"def test_value_{i}(run, x):\n    got = run(x)\n    assert got == {i}\n"}
        for i in range(10)
    ]
    author_answer = json.dumps({"rationale": "Synthetic specification-grounded authoring.",
                                "tests": functions})
    revision_answer = json.dumps({"abstain": False,
                                  "rationale": "Retain the same ten synthetic assertions.",
                                  "tests": functions})
    call_kinds: list[str] = []
    grid_calls: list[str] = []
    images: list[str] = []
    resolved_models: list[str] = []
    generated_space = ["1\n", "2\n"]

    def fake_completion(_client: object, prompt: str, kind: str,
                        schema: object = None) -> Completion:
        if kind == "trigger_search":
            return Completion(text=f"```json\n{json.dumps(generated_space)}\n```",
                              stop_reason="stop")
        call_kinds.append(schema.name)
        return Completion(text=revision_answer if schema.name == "repair_tests" else author_answer,
                          stop_reason="stop")

    def fake_grid(_task: object, _code: str, props_src: str, space: list[str], **kwargs: object) -> dict:
        assert kwargs["isolation"] is sandbox.Isolation.DOCKER
        assert kwargs["docker_image"] == "python:3.12-slim"
        names = _test_names_in(props_src)
        assert len(names) == 10 and space == generated_space
        grid_calls.append(names[0])
        records = [{"prop": name, "i": i,
                    "outcome": "catch" if name == "test_value_0" and i == 0 else "pass"}
                   for name in names for i in range(len(space))]
        return {"ok": True, "complete": True, "props": names,
                "records": records, "n_records": len(records),
                "n_expected": len(records), "error": ""}

    monkeypatch.setattr(omar_shared, "preflight_docker", images.append)
    monkeypatch.setattr("pipeline.protocols.second_revision.preflight_docker", images.append)
    monkeypatch.setattr(sandbox, "run_raw", fake_grid)
    monkeypatch.setattr(model_mod, "resolve",
                        lambda runtime: (resolved_models.append(runtime.name), object())[1])
    monkeypatch.setattr(model_mod, "complete_sync", fake_completion)

    input_plan, input_status, input_arms = omar_shared.advance_shared(
        reference_arm=reference, prefix=prefix, model=model)
    assert input_plan["next_phase"] == "fresh-inputs"
    assert input_plan["phase_paid_call_limit"] == len(candidates)
    assert "No paid call launched" in input_status and input_arms == {}

    def run_input_cli(_name: str, command: list[str]) -> None:
        assert command[-2:] == ["--inputs", trigger.run_name]
        monkeypatch.setattr(sys, "argv", ["omar_runner", "--inputs", trigger.run_name])
        omar_shared.main()

    monkeypatch.setattr(omar_shared, "_launch_windows_coordinator", run_input_cli)
    monkeypatch.setattr(omar_shared.launch, "launch",
                        lambda _name, command, **_kwargs: run_input_cli(_name, command))
    omar_shared.advance_shared(reference_arm=reference, prefix=prefix, model=model,
                               approval=input_plan["phase_approval_token"],
                               max_paid_calls=len(candidates))
    trigger = TriggerSearch.attach(trigger.run_name)
    assert len(trigger.get_records()) == len(candidates)
    assert all(row["inputs"] == generated_space for row in trigger.get_records())

    plan, status, arms = omar_shared.advance_shared(
        reference_arm=reference, prefix=prefix, model=model)
    assert plan["candidate_count"] == 6 and arms == {} and "Paused" in status
    assert plan["triggers"] == trigger.run_name
    assert plan["model"] == plan["input_model"] == model
    assert plan["cross_model_inputs"] is False
    assert plan["workflow_max_logical_calls"] == 24
    assert plan["settings"]["cache"] is False

    initial = omar_shared._baseline(plan)
    assert initial.model == model and initial.cache is False
    initial.write_config()
    assert initial.execute() == 6
    folder = Path("runs") / f"{prefix}-coordinator"
    bundle = omar_shared._freeze_source(plan, initial, folder)
    revisions = omar_shared._revisions(plan, initial, bundle)
    for label in ("B no feedback", "C feedback"):
        arm = revisions[label]
        assert arm.model == model and arm.cache is False
        arm.write_config()
        assert arm.execute() == 6

    assert len(resolved_models) >= 19
    assert set(resolved_models) == {model}
    assert all(arm.model == model for arm in [initial, *revisions.values()])

    a_rows = initial.get_records()
    b_rows = revisions["B no feedback"].get_records()
    c_rows = revisions["C feedback"].get_records()
    assert all(len(rows) == 6 for rows in (a_rows, b_rows, c_rows))
    assert all(not row["failed"] and len(row["calls"]) == 1 and row["fired"] == ["test_value_0"]
               for rows in (a_rows, b_rows, c_rows) for row in rows)
    assert all(row["feedback_visible"] is False for row in b_rows)
    assert all(row["feedback_visible"] is True for row in c_rows)
    assert all("WITHHELD_BY_DESIGN" in row["calls"][0]["prompt"] for row in b_rows)
    assert all("WITHHELD_BY_DESIGN" not in row["calls"][0]["prompt"] for row in c_rows)
    assert call_kinds.count("repair_tests") == 12 and len(call_kinds) == 18
    assert len(grid_calls) == 24  # six A grids, six source replays, six B, six C
    preflight_phases = ("input authorization", "input child", "A", "B", "C")
    assert images == ["python:3.12-slim"] * len(preflight_phases)
