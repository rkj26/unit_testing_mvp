"""Notebook-facing, resumable two-cell lifecycle for the shared Omar study."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from .. import launch
from . import omar_shared
from .base import Run
from .trigger_search import TriggerSearch
from .unit_testing import UnitTesting
from .omar_runtime import coordinator_launch_lock, require_paid, validate_paid_options

_WAIT_SECONDS = 1.0
_WORKER_SUFFIX = "-notebook-worker"


def _full_model(model: str) -> str:
    selected = omar_shared.OMAR_MODELS.get(model, model)
    if selected not in omar_shared.OMAR_MODELS.values():
        raise ValueError(f"model must be one of {sorted(omar_shared.OMAR_MODELS)}")
    return selected


def _identity(reference_arm: UnitTesting, model: str, run_name: str) -> dict[str, Any]:
    if type(reference_arm) is not UnitTesting:
        raise TypeError("reference_arm must be the notebook's UnitTesting arm")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", run_name):
        raise ValueError("run_name must be a stable run-name slug")
    if not reference_arm.config_path.is_file():
        raise ValueError("reference arm has no saved config; finish its notebook cell first")
    config_bytes = reference_arm.config_path.read_bytes()
    if json.loads(config_bytes) != reference_arm.config():
        raise ValueError("reference arm config differs from the notebook object")
    if reference_arm.n_tests != 10 or reference_arm.runs != 1:
        raise ValueError("Omar needs the notebook's one-run ten-test reference")
    if model not in omar_shared.OMAR_MODELS.values():
        raise ValueError("model must be selected from omar_shared.OMAR_MODELS")
    data_path = Path(reference_arm.data_path)
    return {
        "schema_version": 1,
        "run_name": run_name,
        "model": model,
        "reference_run": reference_arm.run_name,
        "reference_config_sha256": omar_shared._sha(config_bytes),
        "data": reference_arm.data_path,
        "dataset_sha256": omar_shared._sha(data_path.read_bytes()),
        "docker_image": reference_arm.docker_image,
        "settings": {
            "n_tests": reference_arm.n_tests,
            "seed": reference_arm.seed,
            "reasoning": reference_arm.reasoning.value,
            "max_tokens": reference_arm.max_tokens,
            "call_seconds": reference_arm.call_seconds,
            "sandbox_seconds": reference_arm.sandbox_seconds,
            "cache": False,
        },
        "include_delete_only": reference_arm.data.backend == "bcb",
    }


class OmarMultiTurn:
    """A synchronous notebook facade over Omar's detached, resumable coordinator.

    ``run()`` completes fresh inputs, Omar A, and the frozen source replay.
    ``continue_run()`` completes B/C (and D for BCB), returning only verified arms.
    """

    def __init__(self, *, reference_arm: UnitTesting, model: str = "terra",
                 run_name: str, allow_paid: bool = False,
                 max_model_calls: int = 0) -> None:
        validate_paid_options(allow_paid, max_model_calls)
        self.allow_paid = allow_paid
        self.max_model_calls = max_model_calls
        self.model = _full_model(model)
        self.run_name = run_name
        self.reference_arm = reference_arm
        self.identity = _identity(reference_arm, self.model, run_name)
        self.worker_dir = Path("runs") / f"{run_name}-notebook"
        self.identity_path = self.worker_dir / "identity.json"
        omar_shared._save_once(self.identity_path, self.identity)

    @property
    def worker_session(self) -> str:
        return f"{self.run_name}{_WORKER_SUFFIX}"

    def _verify_identity(self) -> None:
        current = _identity(self.reference_arm, self.model, self.run_name)
        saved = json.loads(self.identity_path.read_text(encoding="utf-8"))
        if current != saved or current != self.identity:
            raise ValueError("Omar notebook identity changed; choose a new run_name")

    def run(self, *, wait: bool = True) -> UnitTesting | None:
        """Start or resume the initial group; return A only after it is complete."""
        return self._start("initial", wait=wait)

    def continue_run(self, *, wait: bool = True) -> dict[str, UnitTesting] | None:
        """Start or resume B/C(/D); return the full verified Omar roster."""
        return self._start("continue", wait=wait)

    def _alive(self) -> bool:
        if os.name == "nt" and hasattr(omar_shared, "_session_alive"):
            return omar_shared._session_alive(self.worker_session)
        return launch.alive(self.worker_session)

    def _launch(self, target: str) -> None:
        command = [sys.executable, "-m", "pipeline.protocols.omar_notebook",
                   f"--{target}", str(self.identity_path)]
        if os.name == "nt" and hasattr(omar_shared, "_launch_windows_coordinator"):
            omar_shared._launch_windows_coordinator(self.worker_session, command)
        else:
            launch.launch(self.worker_session, command, cwd=Path.cwd())

    def _ensure_no_low_level_worker(self) -> None:
        for session in (f"{self.run_name}-triggers", f"{self.run_name}-coordinator"):
            if omar_shared._session_alive(session):
                raise RuntimeError(
                    f"Omar run {session!r} is already active outside this notebook worker; "
                    "wait for it to finish before starting OmarMultiTurn"
                )

    def _start(self, target: str, *, wait: bool) -> Any:
        self._verify_identity()
        failure = self.worker_dir / "failed.json"
        if failure.is_file():
            raise self._saved_failure(failure)
        completed = self.worker_dir / ("initial-complete.json" if target == "initial"
                                       else "complete.json")
        if completed.is_file():
            return (self._initial_result(completed) if target == "initial"
                    else self._complete_result(completed))
        was_running = self._alive()
        initial_was_complete = (self.worker_dir / "initial-complete.json").is_file()
        if not was_running:
            self._ensure_no_low_level_worker()
            required = self.reference_arm.total * (5 if self.identity["include_delete_only"] else 4)
            require_paid(self.allow_paid, self.max_model_calls, required)
            omar_shared.preflight_docker(self.identity["docker_image"])
            omar_shared._save_once(self.worker_dir / "authorization.json", {
                "identity_sha256": omar_shared._hash_object(self.identity),
                "allow_paid": self.allow_paid, "max_model_calls": self.max_model_calls,
            })
            self._launch(target)
        if not wait:
            return None
        while self._alive():
            # Failure artifacts are authoritative even if process liveness lags their creation.
            # Check before sleeping so a notebook cell does not hang on a failed worker PID.
            if failure.is_file():
                raise self._saved_failure(failure)
            time.sleep(_WAIT_SECONDS)
        if failure.is_file():
            raise self._saved_failure(failure)
        if target == "initial":
            marker = self.worker_dir / "initial-complete.json"
            if not marker.is_file():
                raise RuntimeError(self._missing_artifact_message())
            return self._initial_result(marker)
        marker = self.worker_dir / "complete.json"
        if not marker.is_file():
            # An already-running initial worker may have ended between these calls.
            if (was_running and not initial_was_complete
                    and (self.worker_dir / "initial-complete.json").is_file()):
                return self._start("continue", wait=True)
            raise RuntimeError(self._missing_artifact_message())
        return self._complete_result(marker)

    @staticmethod
    def _saved_failure(path: Path) -> RuntimeError:
        detail = json.loads(path.read_text(encoding="utf-8"))
        return RuntimeError(f"Omar notebook worker failed at {detail['stage']}: {detail['error']}")

    def _missing_artifact_message(self) -> str:
        log = Path("runs") / self.worker_session / launch.CONSOLE_LOG_NAME
        detail = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
        return (f"Omar worker exited before writing its completion artifact. "
                f"Inspect {log}. {detail[-2000:]}")

    def _initial_result(self, marker: Path) -> UnitTesting:
        plan = self._load_study_plan()
        saved = json.loads(marker.read_text(encoding="utf-8"))
        if saved["plan_sha256"] != omar_shared._hash_object(plan):
            raise ValueError("Omar initial marker belongs to a different study plan")
        omar_shared.verify_cached_study(plan, complete=False)
        initial = omar_shared._baseline(plan)
        omar_shared._complete_records(initial)
        return initial

    def _complete_result(self, marker: Path) -> dict[str, UnitTesting]:
        plan = self._load_study_plan()
        saved = json.loads(marker.read_text(encoding="utf-8"))
        if saved["plan_sha256"] != omar_shared._hash_object(plan):
            raise ValueError("Omar completion marker belongs to a different study plan")
        omar_shared.verify_cached_study(plan, complete=True)
        if not (Path("runs") / f"{self.run_name}-coordinator" / "complete.json").is_file():
            raise ValueError("Omar worker completion marker exists without complete coordinator records")
        initial = omar_shared._baseline(plan)
        arms = omar_shared._revisions(
            plan, initial, Path("runs") / f"{self.run_name}-coordinator" / "source-bundle.json")
        for arm in arms.values():
            omar_shared._complete_records(arm)
        return arms

    def _load_study_plan(self) -> dict[str, Any]:
        path = Path("runs") / f"{self.run_name}-coordinator" / "plan.json"
        if not path.is_file():
            raise FileNotFoundError(f"Omar study plan is missing: {path}")
        return json.loads(path.read_text(encoding="utf-8"))


def _attach_reference(identity: dict[str, Any]) -> UnitTesting:
    arm = Run.attach(identity["reference_run"])
    if type(arm) is not UnitTesting:
        raise TypeError("saved Omar reference is not a UnitTesting arm")
    actual = _identity(arm, identity["model"], identity["run_name"])
    if actual != identity:
        raise ValueError("saved Omar reference, dataset, model, image, or settings changed")
    return arm


def _study_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in plan.items()
            if key not in {"next_phase", "phase_approval_token", "phase_paid_call_limit"}}


def _run_phase(plan: dict[str, Any], phase: str) -> None:
    folder = Path("runs") / f"{plan['prefix']}-coordinator"
    marker = folder / f"{phase}-complete.json"
    if marker.is_file():
        saved = json.loads(marker.read_text(encoding="utf-8"))
        if saved["plan_sha256"] != omar_shared._hash_object(plan):
            raise ValueError(f"{phase} marker belongs to a different study plan")
        return
    if omar_shared._session_alive(folder.name):
        while omar_shared._session_alive(folder.name):
            time.sleep(_WAIT_SECONDS)
        if marker.is_file():
            saved = json.loads(marker.read_text(encoding="utf-8"))
            if saved["plan_sha256"] != omar_shared._hash_object(plan):
                raise ValueError(f"{phase} marker belongs to a different study plan")
            return
    omar_shared._save_once(folder / "plan.json", plan)
    request = folder / f"{phase}-request.json"
    omar_shared._save_once(request, {"phase": phase,
                                     "plan_sha256": omar_shared._hash_object(plan),
                                     "approval": plan["approval_tokens"][phase],
                                     "max_paid_calls": plan["phase_max_calls"][phase]})
    omar_shared.coordinate_study(request)


def _finish_initial(identity: dict[str, Any], reference: UnitTesting) -> dict[str, Any]:
    worker_dir = Path("runs") / f"{identity['run_name']}-notebook"
    marker = worker_dir / "initial-complete.json"
    if marker.is_file():
        plan = json.loads((Path("runs") / f"{identity['run_name']}-coordinator" /
                           "plan.json").read_text(encoding="utf-8"))
        if json.loads(marker.read_text(encoding="utf-8"))["plan_sha256"] != omar_shared._hash_object(plan):
            raise ValueError("Omar initial marker belongs to a different study plan")
        omar_shared.verify_cached_study(plan, complete=False)
        return plan

    plan, _, arms = omar_shared.advance_shared(
        reference_arm=reference, prefix=identity["run_name"], model=identity["model"])
    if plan.get("next_phase") == "fresh-inputs":
        trigger = Run.attach(plan["triggers"])
        if type(trigger) is not TriggerSearch or trigger.model != identity["model"]:
            raise ValueError("Omar fresh-input run does not match the selected model")
        while trigger.pending() and omar_shared._session_alive(trigger.run_name):
            time.sleep(_WAIT_SECONDS)
        if trigger.pending():
            omar_shared.authorize_inputs(trigger, identity["docker_image"])
            omar_shared.run_inputs(trigger.run_name)
        omar_shared._complete_records(trigger)
        plan, _, arms = omar_shared.advance_shared(
            reference_arm=reference, prefix=identity["run_name"], model=identity["model"])
    if arms:
        # An older or externally completed run is still safe only after its own records verify.
        full_plan = plan
        initial = arms["A initial"]
        omar_shared._complete_records(initial)
        omar_shared._save_once(marker, {"plan_sha256": omar_shared._hash_object(full_plan),
                                        "run_name": initial.run_name})
        return full_plan

    study_plan = _study_plan(plan)
    for phase in ("A-smoke", "A-full"):
        _run_phase(study_plan, phase)
    baseline = omar_shared._baseline(study_plan)
    omar_shared._complete_records(baseline)
    bundle = Path("runs") / f"{identity['run_name']}-coordinator" / "source-bundle.json"
    if not bundle.is_file():
        raise FileNotFoundError(f"Omar source bundle was not frozen: {bundle}")
    omar_shared.verify_cached_study(study_plan, complete=False)
    omar_shared._save_once(marker, {"plan_sha256": omar_shared._hash_object(study_plan),
                                    "run_name": baseline.run_name})
    return study_plan


def _finish_all(identity: dict[str, Any], reference: UnitTesting) -> dict[str, Any]:
    plan = _finish_initial(identity, reference)
    complete = Path("runs") / f"{identity['run_name']}-notebook" / "complete.json"
    if complete.is_file():
        if json.loads(complete.read_text(encoding="utf-8"))["plan_sha256"] != omar_shared._hash_object(plan):
            raise ValueError("Omar notebook completion marker belongs to a different plan")
        omar_shared.verify_cached_study(plan, complete=True)
        return plan
    for phase in ("revision-smoke", "revision-full"):
        _run_phase(plan, phase)
    coordinator_complete = Path("runs") / f"{identity['run_name']}-coordinator" / "complete.json"
    if not coordinator_complete.is_file():
        raise FileNotFoundError(f"Omar coordinator has no complete marker: {coordinator_complete}")
    omar_shared._save_once(complete, {"plan_sha256": omar_shared._hash_object(plan),
                                      "candidate_count": plan["candidate_count"]})
    return plan


def worker(identity_path: Path, target: str) -> None:
    """Own execution before entering paid work; duplicate rejection cannot poison its owner."""
    execution_dir = identity_path.parent / "execution"
    execution_dir.mkdir(parents=True, exist_ok=True)
    with coordinator_launch_lock(execution_dir):
        _worker(identity_path, target)


def _worker(identity_path: Path, target: str) -> None:
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    worker_dir = identity_path.parent
    failure = worker_dir / "failed.json"
    if failure.is_file():
        raise OmarMultiTurn._saved_failure(failure)
    stage = target
    try:
        reference = _attach_reference(identity)
        completed = worker_dir / ("complete.json" if target == "continue" else "initial-complete.json")
        if not completed.is_file():
            authorization = json.loads((worker_dir / "authorization.json").read_text(encoding="utf-8"))
            if authorization["identity_sha256"] != omar_shared._hash_object(identity):
                raise ValueError("Omar paid authorization belongs to a different identity")
            require_paid(authorization["allow_paid"], authorization["max_model_calls"],
                         reference.total * (5 if identity["include_delete_only"] else 4))
            omar_shared.preflight_docker(identity["docker_image"])
        _finish_initial(identity, reference)
        if target == "continue":
            stage = "continuation"
            _finish_all(identity, reference)
    except Exception as error:
        omar_shared._save_once(failure, {"stage": stage,
                                         "error": f"{type(error).__name__}: {error}"})
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Omar notebook worker")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--initial", type=Path)
    group.add_argument("--continue", dest="continue_path", type=Path)
    args = parser.parse_args()
    if args.initial is not None:
        worker(args.initial, "initial")
    else:
        worker(args.continue_path, "continue")


if __name__ == "__main__":
    main()
