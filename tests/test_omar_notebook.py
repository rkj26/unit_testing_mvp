"""Notebook-facing Omar lifecycle tests; only model and Docker boundaries are mocked."""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from collections import Counter
from pathlib import Path

import pytest

from build_dataset import build
from pipeline import model as model_mod, sandbox
from pipeline.model import Completion
from pipeline.protocols import omar_notebook, omar_shared
from pipeline.protocols.omar_notebook import OmarMultiTurn
from pipeline.protocols.trigger_search import TriggerSearch
from pipeline.protocols.unit_testing import UnitTesting, test_names_in as _test_names_in


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("alias,model", list(omar_shared.OMAR_MODELS.items()))
def test_notebook_adapter_runs_initial_then_continuation_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, alias: str, model: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(omar_shared, "__file__",
                        str(tmp_path / "pipeline/protocols/omar_shared.py"))
    data_path = tmp_path / "mini-apps.json"
    data = build(ROOT / "apps_pool_hard10.json", ROOT / "splits/smoke_3.json",
                 "apps", "omar-notebook-mini")
    data_path.write_text(json.dumps(data), encoding="utf-8")
    reference = UnitTesting(
        run_name="notebook-reference", data=str(data_path), model=model,
        triggers="unused-team-trigger", n_tests=10, test_gen_prompt="property",
        code_visible=True, seed=300, cache=True, docker_image="python:3.12-slim",
    )
    reference.write_config()  # Intentionally no team records: they are not Omar inputs.

    prefix = f"notebook-omar-{uuid.uuid4().hex[:8]}"
    adapter = OmarMultiTurn(reference_arm=reference, model=alias, run_name=prefix,
                            allow_paid=True, max_model_calls=24)
    tests = [
        {"name": f"test_value_{index}",
         "source": f"def test_value_{index}(run, x):\n    assert run(x) == {index}\n"}
        for index in range(10)
    ]
    generated_space = ["1\n", "2\n"]
    responses = {
        "audit_tests": json.dumps({"rationale": "Synthetic first turn.", "tests": tests}),
        "repair_tests": json.dumps({"abstain": False, "rationale": "Synthetic revision.",
                                    "tests": tests}),
    }
    calls: list[str] = []
    runtime_names: list[str] = []

    def fake_resolve(runtime: object) -> object:
        runtime_names.append(runtime.name)
        return object()

    def fake_complete(_client: object, prompt: str, kind: str,
                      schema: object = None) -> Completion:
        calls.append(kind if schema is None else schema.name)
        if kind == "trigger_search":
            return Completion(f"```json\n{json.dumps(generated_space)}\n```", "stop")
        if kind == "tm":
            score = "no rating" if candidates[0][1].code in prompt else "SUSPICION_SCORE: 4"
            return Completion(score, "stop")
        return Completion(responses[schema.name], "stop")

    def fake_grid(_task: object, _code: str, source: str, space: list[str], **kwargs: object) -> dict:
        assert kwargs["isolation"] is sandbox.Isolation.DOCKER
        assert kwargs["docker_image"] == "python:3.12-slim"
        assert space == generated_space
        names = _test_names_in(source)
        records = [{"prop": name, "i": index,
                    "outcome": "catch" if name == "test_value_0" and index == 0 else "pass"}
                   for name in names for index in range(len(space))]
        return {"ok": True, "complete": True, "error": "", "props": names,
                "records": records, "n_records": len(records), "n_expected": len(records)}

    monkeypatch.setattr(model_mod, "resolve", fake_resolve)
    monkeypatch.setattr(model_mod, "complete_sync", fake_complete)
    monkeypatch.setattr(omar_shared, "preflight_docker", lambda _image: None)
    monkeypatch.setattr("pipeline.protocols.second_revision.preflight_docker", lambda _image: None)
    monkeypatch.setattr(sandbox, "run_raw", fake_grid)
    monkeypatch.setattr(omar_shared.launch, "alive", lambda _name: False)

    def run_worker(_session: str, command: list[str], **_kwargs: object) -> None:
        monkeypatch.setattr(sys, "argv", ["omar_notebook", *command[3:]])
        from pipeline.protocols import omar_notebook
        omar_notebook.main()

    monkeypatch.setattr(omar_shared.launch, "launch", run_worker)
    monkeypatch.setattr(omar_shared, "_launch_windows_coordinator", run_worker,
                        raising=False)

    initial = adapter.run()
    assert isinstance(initial, UnitTesting)
    assert initial.run_name == f"{prefix}-A-traceable"
    assert len(initial.get_records()) == 6
    assert Counter(calls) == {"trigger_search": 6, "audit_tests": 6}
    trigger = TriggerSearch.attach(f"{prefix}-triggers")
    assert all(row["inputs"] == generated_space for row in trigger.get_records())

    def crashed_worker(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(omar_shared.launch, "launch", crashed_worker)
    monkeypatch.setattr(omar_shared, "_launch_windows_coordinator", crashed_worker,
                        raising=False)
    with pytest.raises(RuntimeError, match="exited before writing its completion artifact"):
        adapter.continue_run()

    monkeypatch.setattr(omar_shared.launch, "launch", run_worker)
    monkeypatch.setattr(omar_shared, "_launch_windows_coordinator", run_worker,
                        raising=False)
    arms = adapter.continue_run()
    assert set(arms) == {"A initial", "B no feedback", "C feedback"}
    assert all(isinstance(arm, UnitTesting) and arm.model == model and not arm.cache
               for arm in arms.values())
    assert Counter(calls) == {"trigger_search": 6, "audit_tests": 6, "repair_tests": 12}

    assert all(arm.n_tests == 10 for arm in arms.values())
    assert all(len(arm.get_records()) == 6 for arm in arms.values())
    assert runtime_names and set(runtime_names) == {model}

    # Calling either cell again attaches to immutable artifacts; it does not duplicate calls.
    assert adapter.run().run_name == initial.run_name
    assert set(adapter.continue_run()) == set(arms)
    assert Counter(calls) == {"trigger_search": 6, "audit_tests": 6,
                              "repair_tests": 12}

    cached = OmarMultiTurn(reference_arm=reference, model=alias, run_name=prefix)
    monkeypatch.setattr(model_mod, "resolve", lambda *_: pytest.fail("cached provider resolve"))
    monkeypatch.setattr(omar_shared, "preflight_docker", lambda *_: pytest.fail("cached Docker"))
    assert cached.run().run_name == initial.run_name
    assert set(cached.continue_run()) == set(arms)
    trigger_path = trigger.records_path
    original = trigger_path.read_text(encoding="utf-8")
    rows = [json.loads(line) for line in original.splitlines()]
    rows[0]["inputs"] = ["tampered\n"]
    trigger_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises(ValueError, match="changed|hash"):
        cached.run()
    with pytest.raises(ValueError, match="changed|hash"):
        cached.continue_run()
    trigger_path.write_text(original, encoding="utf-8")


def test_worker_module_imports_in_a_fresh_process() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "pipeline.protocols.omar_notebook", "--help"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--initial" in completed.stdout and "--continue" in completed.stdout


def test_adapter_rejects_changed_model_for_existing_run_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(omar_shared, "__file__",
                        str(tmp_path / "pipeline/protocols/omar_shared.py"))
    data_path = tmp_path / "mini-apps.json"
    data = build(ROOT / "apps_pool_hard10.json", ROOT / "splits/smoke_3.json",
                 "apps", "omar-notebook-identity")
    data_path.write_text(json.dumps(data), encoding="utf-8")
    reference = UnitTesting(run_name="identity-reference", data=str(data_path),
                            model=omar_shared.OMAR_MODELS["terra"],
                            triggers="unused", n_tests=10, cache=True)
    reference.write_config()
    OmarMultiTurn(reference_arm=reference, model="terra", run_name="identity-run")
    with pytest.raises(ValueError, match="existing artifact differs"):
        OmarMultiTurn(reference_arm=reference, model="deepseek", run_name="identity-run")


def test_adapter_never_returns_arms_without_completion_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(omar_shared, "__file__",
                        str(tmp_path / "pipeline/protocols/omar_shared.py"))
    data_path = tmp_path / "mini-apps.json"
    data = build(ROOT / "apps_pool_hard10.json", ROOT / "splits/smoke_3.json",
                 "apps", "omar-notebook-incomplete")
    data_path.write_text(json.dumps(data), encoding="utf-8")
    reference = UnitTesting(run_name="incomplete-reference", data=str(data_path),
                            model=omar_shared.OMAR_MODELS["terra"],
                            triggers="unused", n_tests=10, cache=True)
    reference.write_config()
    adapter = OmarMultiTurn(reference_arm=reference, model="terra",
                             run_name="incomplete-run", allow_paid=True, max_model_calls=24)
    monkeypatch.setattr(omar_shared, "preflight_docker", lambda _image: None)
    monkeypatch.setattr(omar_shared, "_session_alive",
                        lambda name: name == "incomplete-run-triggers")
    with pytest.raises(RuntimeError, match="already active outside this notebook worker"):
        adapter.run()
    monkeypatch.setattr(omar_shared, "_session_alive", lambda _name: False)
    monkeypatch.setattr(omar_shared.launch, "alive", lambda _name: False)
    monkeypatch.setattr(omar_shared.launch, "launch", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(omar_shared, "_launch_windows_coordinator",
                        lambda *_args, **_kwargs: None, raising=False)
    with pytest.raises(RuntimeError, match="exited before writing its completion artifact"):
        adapter.run()

    omar_shared._save_once(adapter.worker_dir / "failed.json",
                           {"stage": "A-full", "error": "synthetic failure"})
    with pytest.raises(RuntimeError, match="synthetic failure"):
        adapter.continue_run()


def test_saved_failure_interrupts_live_worker_wait(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(omar_shared, "__file__",
                        str(tmp_path / "pipeline/protocols/omar_shared.py"))
    data_path = tmp_path / "mini-apps.json"
    data = build(ROOT / "apps_pool_hard10.json", ROOT / "splits/smoke_3.json",
                 "apps", "omar-notebook-live-failure")
    data_path.write_text(json.dumps(data), encoding="utf-8")
    reference = UnitTesting(run_name="live-failure-reference", data=str(data_path),
                            model=omar_shared.OMAR_MODELS["terra"], triggers="unused",
                            n_tests=10, cache=False)
    reference.write_config()
    adapter = OmarMultiTurn(reference_arm=reference, model="terra",
                             run_name="live-failure-run", allow_paid=True, max_model_calls=24)
    monkeypatch.setattr(omar_shared, "preflight_docker", lambda _image: None)

    polls = 0

    def fake_alive() -> bool:
        nonlocal polls
        polls += 1
        if polls == 1:  # No worker at launch time.
            return False
        if polls == 2:  # The worker PID still appears live after it writes failed.json.
            return True
        raise AssertionError("the notebook polled worker liveness after observing failure")

    def launch_failed(_target: str) -> None:
        omar_shared._save_once(adapter.worker_dir / "failed.json",
                               {"stage": "fresh inputs", "error": "loopback-only failure"})

    monkeypatch.setattr(adapter, "_alive", fake_alive)
    monkeypatch.setattr(adapter, "_launch", launch_failed)
    monkeypatch.setattr(omar_shared, "_session_alive", lambda _name: False)
    monkeypatch.setattr(omar_notebook.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="loopback-only failure"):
        adapter.run()
    assert polls == 2
