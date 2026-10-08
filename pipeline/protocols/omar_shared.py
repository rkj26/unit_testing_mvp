"""Detached, resumable A/B/C(/D) study on a shared notebook population.

This creates a *new* code-visible traceable first turn.  It never borrows the
notebook's property-prompt UnitTesting arm or modifies a teammate's run.
"""

from __future__ import annotations

import argparse
import ast
import ctypes
import hashlib
import json
import os
import re
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

from .. import launch, sandbox
from ..data import Dataset, load_records
from .omar_runtime import coordinator_launch_lock, preflight_docker
from .base import Run
from .second_revision import SecondRevision, is_base_infra_failure
from .test_repair import feedback_summary
from .trigger_search import DEFAULT_NUM_INPUTS, TriggerSearch
from .unit_testing import UnitTesting, spaces_from, suite_source, test_names_in

HISTORICAL = {
    "apps30": {
        "data": "data/omar_apps30.json", "candidates": 60,
        "sha256": "707bade0d291fa0ff5c0b9672c1c4fe0528fe6115753acc7f9422ea467d548d9",
        "image": "python@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea",
        "delete": False,
    },
    "bcb26": {
        "data": "data/omar_bcb26.json", "candidates": 52,
        "sha256": "ade10be43433885843d74264c02d8e76c9ea4eb15e9bd03dbadf322056ef733f",
        "image": "omar-bcb-pbt@sha256:fd7deb31bc5174495c3cb9f25fcb503a900ea853740bb8d4fac1870265e31436",
        "delete": True,
    },
}
HISTORICAL_MODEL = "openai-api/azureai/gpt-5.6-terra"
OMAR_MODELS = {
    "terra": "openai-api/azureai/gpt-5.6-terra",
    "deepseek": "openai-api/azureai/DeepSeek-V3.2",
}


class OmarTriggerSearch(TriggerSearch):
    """Ten fresh inputs with the original single-attempt 12k-token runtime."""

    protocol = "omar_trigger_search"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if (self.num_inputs != 10 or not self.code_visible or self.runs != 1
                or self.seed != 300 or self.cache or self.reasoning.value != "low"):
            raise ValueError("Omar triggers require ten visible inputs, seed 300, low, no cache")

    def runtime(self, seed):
        return super().runtime(seed).model_copy(update={
            "http_retries": 0, "max_tokens": 12000,
            "attempt_timeout": 300, "http_timeout": 300,
        })


class OmarInitial(UnitTesting):
    """Traceable first turn, with historical or reference-matched settings."""

    protocol = "omar_initial"

    def __init__(self, *, study_kind: str = "historical", **kwargs):
        if study_kind not in {"historical", "shared"}:
            raise ValueError("Omar A study_kind must be historical or shared")
        super().__init__(study_kind=study_kind, **kwargs)
        if (self.code_visible is not True or self.framing != "traceable_v1"
                or self.resolve != "with" or self.n_tests != 10
                or self.critique or self.critique_informed):
            raise ValueError("Omar A requires ten traceable code-visible tests without critique")
        if study_kind == "historical" and (
                self.cache or self.reasoning.value != "low" or self.seed != 300
                or self.max_tokens != 8192 or self.call_seconds != 300
                or self.sandbox_seconds != 120):
            raise ValueError("historical Omar A settings differ from the frozen design")
        self.study_kind = study_kind

    def score(self, task, candidate):
        """Keep fresh-input infrastructure failures as infrastructure in Omar A."""
        cid = candidate.candidate_id
        if cid in self.no_trigger_space:
            blame = self.input_failure_blame[cid]
            return self._unmeasured([], blame,
                f"no trigger inputs: {self.triggers} {self.no_trigger_space[cid]}")
        return super().score(task, candidate)

    def _runtime(self):
        runtime = super()._runtime()
        return runtime if self.study_kind == "shared" else runtime.model_copy(
            update={"http_retries": 0})

    def prepare(self, data: Dataset) -> None:
        """Check Omar's sandbox before the first paid authoring call."""
        preflight_docker(self.docker_image)
        super().prepare(data)
        rows = {record["candidate_id"]: record for record in load_records(self.triggers)}
        self.input_failure_blame = {}
        for cid in self.no_trigger_space:
            if cid not in rows:
                raise ValueError(f"{cid}: fresh-input failure record is missing")
            row = rows[cid]
            blame = row["blame"] if row["failed"] else "model"
            if blame not in {"model", "infra"}:
                raise ValueError(f"{cid}: fresh-input failure has invalid blame")
            self.input_failure_blame[cid] = blame


def install_bcb_harness() -> None:
    """Install Omar's reviewed deepcopy wrapper around the sandbox harness.

    This is applied only inside the detached coordinator process. All four
    BCB stages execute in that process, so every sandbox invocation sees it.
    """
    original = sandbox.build_harness
    if getattr(original, "_omar_deepcopy_wrapper", False):
        return

    def wrapped(task, code, props_src, space, **kwargs):
        if task.io_mode != "function":
            raise ValueError("Omar's BCB wrapper requires function-mode tasks")
        script = original(task, code, props_src, space, **kwargs)
        marker = "import json, sys, io, contextlib, os, time"
        if script.count(marker) != 1 or script.count("_pfn(run, _x)") != 1:
            raise ValueError("BCB harness shape changed; deepcopy wrapper was not applied")
        script = script.replace(marker, marker + ", copy")
        script = script.replace("_pfn(run, _x)", "_pfn(run, copy.deepcopy(_x))")
        if kwargs.get("probe_bare_run", False):
            if script.count("run(_x)") != 1:
                raise ValueError("BCB bare-run probe shape changed")
            script = script.replace("run(_x)", "run(copy.deepcopy(_x))")
        elif "run(_x)" in script:
            raise ValueError("unexpected bare-run probe in BCB harness")
        ast.parse(script)
        return script

    wrapped._omar_deepcopy_wrapper = True
    sandbox.build_harness = wrapped


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hash_object(value: object) -> str:
    return _sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _save_once(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, sort_keys=True, indent=2) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != raw:
            raise ValueError(f"existing artifact differs: {path}")
        return
    with path.open("x", encoding="utf-8") as stream:
        stream.write(raw)
        stream.flush()


def _session_alive(run_name: str) -> bool:
    """Read Omar worker liveness without signaling Windows processes or requiring tmux."""
    if os.name == "nt":
        pid_path = Path("runs") / run_name / "coordinator.pid"
        try:
            pid = int(pid_path.read_text(encoding="ascii").strip())
        except (FileNotFoundError, ValueError):
            return False
        return _windows_process_alive(pid)
    try:
        return launch.alive(run_name)
    except FileNotFoundError:
        return False


def _windows_process_alive(pid: int) -> bool:
    """Query a Windows process with OpenProcess; never use os.kill(pid, 0)."""
    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def _launch_windows_coordinator(run_name: str, argv: list[str]) -> None:
    """Launch one detached Omar worker with a log, PID file, and duplicate guard."""
    folder = Path("runs") / run_name
    folder.mkdir(parents=True, exist_ok=True)
    pid_path = folder / "coordinator.pid"
    if _session_alive(run_name):
        raise RuntimeError(f"Omar coordinator {run_name!r} is already running")
    with coordinator_launch_lock(folder):
        if _session_alive(run_name):
            raise RuntimeError(f"Omar coordinator {run_name!r} is already running")
        log = (folder / launch.CONSOLE_LOG_NAME).open("ab", buffering=0)
        try:
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            process = subprocess.Popen(argv, cwd=Path.cwd(), stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT,
                                       close_fds=True, creationflags=flags)
        finally:
            log.close()
        temporary_pid = pid_path.with_suffix(".pid.tmp")
        temporary_pid.write_text(f"{process.pid}\n", encoding="ascii")
        os.replace(temporary_pid, pid_path)


def _study_args(*, data: str, model: str, triggers: str, prefix: str,
                docker_image: str, include_delete_only: bool,
                study_kind: str = "historical", settings: dict | None = None,
                allow_unusable_inputs: bool = False,
                reference_run: str = "") -> dict:
    if Path.cwd() != Path(__file__).resolve().parents[2]:
        raise ValueError("run the Omar cell from the repository root; runs/ is CWD-relative")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", prefix):
        raise ValueError("prefix must be a stable run-name slug")
    if not model or not triggers or not docker_image:
        raise ValueError("model, finished trigger run, and Docker image are required")
    if study_kind not in {"historical", "shared"}:
        raise ValueError("study_kind must be historical or shared")
    default_settings = {"n_tests": 10, "seed": 300, "reasoning": "low",
                        "max_tokens": 8192, "call_seconds": 300,
                        "sandbox_seconds": 120, "cache": False}
    settings = default_settings if settings is None else dict(settings)
    if (set(settings) != set(default_settings) or settings["n_tests"] != 10
            or any(type(settings[key]) is not int or settings[key] < 1
                   for key in ("max_tokens", "call_seconds", "sandbox_seconds"))
            or type(settings["seed"]) is not int
            or type(settings["cache"]) is not bool
            or settings["reasoning"] not in {"low", "medium", "high"}):
        raise ValueError("study settings must contain ten tests and explicit valid runtime fields")
    if study_kind == "historical" and (settings != default_settings or allow_unusable_inputs):
        raise ValueError("historical study settings and reviewed-input completeness are fixed")
    if study_kind == "shared" and not reference_run:
        raise ValueError("shared study requires a named saved reference arm")
    reference_config = Path("runs") / reference_run / "config.json" if reference_run else None
    if reference_config is not None and not reference_config.is_file():
        raise ValueError("shared reference config disappeared")
    dataset = Dataset.load(data)
    if include_delete_only != (dataset.backend == "bcb"):
        raise ValueError("delete-only D must be enabled exactly for BigCodeBench")
    wanted = {candidate.candidate_id for _, candidate in dataset.candidates()}
    if len(wanted) != sum(1 for _ in dataset.candidates()):
        raise ValueError("duplicate candidate IDs in dataset")
    input_rows = load_records(triggers)
    if len(input_rows) != len(wanted) or {row["candidate_id"] for row in input_rows} != wanted:
        raise ValueError("trigger run must have exactly one record for every study candidate")
    trigger_config = Path("runs") / triggers / "config.json"
    if not trigger_config.exists():
        raise ValueError("trigger run has no config.json")
    source = json.loads(trigger_config.read_text(encoding="utf-8"))
    if source["protocol"] != "trigger_search" or source["data"] != str(data):
        raise ValueError("trigger run is not a search over the selected dataset")
    input_model = source["model"]
    cross_model_inputs = input_model != model
    if cross_model_inputs:
        raise ValueError("Omar stages must author and consume inputs with the same model")
    provenance = source.get("review_provenance")
    if provenance is not None:
        original = Path("runs") / provenance["trigger_run"]
        for key, name in (("trigger_config_sha256", "config.json"),
                          ("trigger_records_sha256", "records.jsonl")):
            if _sha((original / name).read_bytes()) != provenance[key]:
                raise ValueError(f"reviewed input source changed: {original / name}")
        if _sha(Path(data).read_bytes()) != provenance["dataset_sha256"]:
            raise ValueError("reviewed input dataset changed")
    spaces, unusable = spaces_from(triggers, dataset)
    if (unusable or len(spaces) != len(wanted)) and not allow_unusable_inputs:
        raise ValueError(f"{len(unusable)} candidate(s) have no usable frozen trigger inputs")
    count = len(wanted)
    if not count:
        raise ValueError("empty study dataset")
    return {"schema_version": 3, "data": str(data), "model": model,
            "triggers": triggers, "prefix": prefix, "docker_image": docker_image,
            "include_delete_only": include_delete_only, "candidate_count": count,
            "study_kind": study_kind, "settings": settings,
            "allow_unusable_inputs": allow_unusable_inputs,
            "input_model": input_model,
            "cross_model_inputs": cross_model_inputs,
            "unusable_input_count": len(unusable),
            "shared_image": docker_image if study_kind == "shared" else "",
            "shared_trigger": triggers if study_kind == "shared" else "",
            "shared_cache": settings["cache"] if study_kind == "shared" else False,
            "reference_run": reference_run,
            "reference_config_sha256": _sha(reference_config.read_bytes()) if reference_config else "",
            "deepcopy_wrapper": dataset.backend == "bcb" and study_kind != "shared",
            "max_logical_model_calls": count * (4 if include_delete_only else 3),
            "workflow_max_logical_calls": count * (5 if include_delete_only else 4),
            "dataset_sha256": _sha(Path(data).read_bytes()),
            "trigger_config_sha256": _sha(trigger_config.read_bytes()),
            "input_records_sha256": _sha((Path("runs") / triggers / "records.jsonl").read_bytes())}


def study_plan(*, data: str, model: str, triggers: str, prefix: str,
               docker_image: str = "python:3.12-slim",
               include_delete_only: bool = False,
               study_kind: str = "historical", settings: dict | None = None,
               allow_unusable_inputs: bool = False,
               reference_run: str = "") -> dict:
    """Read-only preflight and maximum logical call count; no paid launch."""
    args = _study_args(data=data, model=model, triggers=triggers, prefix=prefix,
                       docker_image=docker_image, include_delete_only=include_delete_only,
                       study_kind=study_kind, settings=settings,
                       allow_unusable_inputs=allow_unusable_inputs,
                       reference_run=reference_run)
    digest = _hash_object(args)[:16]
    n = args["candidate_count"]
    revisions = 3 if include_delete_only else 2
    phase_calls = {"A-smoke": 1, "A-full": n - 1,
                   "revision-smoke": revisions,
                   "revision-full": revisions * (n - 1)}
    approvals = {phase: f"RUN-OMAR-{prefix}-{phase}-{calls}-{digest}"
                 for phase, calls in phase_calls.items()}
    return {**args, "phase_max_calls": phase_calls, "approval_tokens": approvals}


def _baseline(plan: dict) -> OmarInitial:
    settings = plan["settings"]
    return OmarInitial(run_name=f"{plan['prefix']}-A-traceable", data=plan["data"],
                       model=plan["model"], triggers=plan["triggers"],
                       n_tests=settings["n_tests"], study_kind=plan["study_kind"],
                       code_visible=True, test_gen_prompt="traceable_v1", resolve="with",
                       reasoning=settings["reasoning"], seed=settings["seed"],
                       max_tokens=settings["max_tokens"], call_seconds=settings["call_seconds"],
                       sandbox_seconds=settings["sandbox_seconds"],
                       docker_image=plan["docker_image"], cache=settings["cache"])


def _revisions(plan: dict, baseline: UnitTesting, bundle: Path) -> dict[str, UnitTesting]:
    bundle_hash = _sha(bundle.read_bytes())
    settings = plan["settings"]
    common = dict(data=plan["data"], model=plan["model"], triggers=plan["triggers"],
                  n_tests=settings["n_tests"], test_gen_prompt="traceable_v1", resolve="with",
                  reasoning=settings["reasoning"], seed=settings["seed"],
                  max_tokens=settings["max_tokens"], call_seconds=settings["call_seconds"],
                  sandbox_seconds=settings["sandbox_seconds"],
                  docker_image=plan["docker_image"], cache=settings["cache"],
                  baseline_run=baseline.run_name, source_bundle=str(bundle),
                  source_bundle_sha256=bundle_hash, max_candidates=plan["candidate_count"])
    shared_options = {"shared_workspace": True} if plan["study_kind"] == "shared" else {}
    arms: dict[str, UnitTesting] = {
        "A initial": baseline,
        "B no feedback": SecondRevision(
            run_name=f"{plan['prefix']}-B-no-feedback", feedback_visible=False,
            code_visible=False, **shared_options, **common),
        "C feedback": SecondRevision(
            run_name=f"{plan['prefix']}-C-feedback", feedback_visible=True,
            code_visible=False, **shared_options, **common),
    }
    if plan["include_delete_only"]:
        from .omar_delete_only import OmarDeleteOnly
        arms["D delete only"] = OmarDeleteOnly(
            run_name=f"{plan['prefix']}-D-delete-only", code_visible=False,
            **shared_options, **common)
    return arms


def _complete_records(arm: Run) -> None:
    rows = arm.get_records()
    wanted = {candidate.candidate_id for _, candidate in arm.data.candidates()}
    if len(rows) != arm.total or {row["candidate_id"] for row in rows} != wanted:
        raise ValueError(f"{arm.run_name}: missing or duplicate candidate records")
    if not arm.config_path.exists() or json.loads(arm.config_path.read_text()) != arm.config():
        raise ValueError(f"{arm.run_name}: absent or conflicting run config")
    by_id = {row["candidate_id"]: row for row in rows}
    for task, candidate in arm.data.candidates():
        row = by_id[candidate.candidate_id]
        expected = {"run_name": arm.run_name, "protocol": arm.protocol,
                    "task_id": task.task_id, "candidate_id": candidate.candidate_id,
                    "split": arm.data.split_of(task.task_id), "label": candidate.label,
                    "is_attack": candidate.is_attack}
        if any(row[key] != value for key, value in expected.items()):
            raise ValueError(f"{arm.run_name}: completed record identity changed")
        if type(row["failed"]) is not bool or not isinstance(row["calls"], list):
            raise ValueError(f"{arm.run_name}: invalid completed record")
        if row["failed"] and (row["blame"] not in {"model", "infra"} or not row["reason"]):
            raise ValueError(f"{arm.run_name}: invalid completed failure provenance")


def verify_cached_study(plan: dict, *, complete: bool) -> dict[str, UnitTesting]:
    """Read-only dependency/record validation; never reseal, resolve, or execute."""
    _verify_plan(plan)
    baseline = _baseline(plan)
    _complete_records(baseline)
    folder = Path("runs") / f"{plan['prefix']}-coordinator"
    bundle_path = folder / "source-bundle.json"
    arms = _revisions(plan, baseline, bundle_path)
    revision = arms["B no feedback"]
    revision.validate_source(revision.data)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    for cid, row in bundle["candidates"].items():
        cache = folder / "source-feedback" / f"{_sha(cid.encode())}.json"
        if not cache.is_file():
            raise ValueError(f"frozen source feedback is missing for {cid}")
        saved = json.loads(cache.read_text(encoding="utf-8"))
        if saved != {"identity": {key: value for key, value in row.items() if key != "result"},
                     "result": row["result"]}:
            raise ValueError(f"frozen source feedback changed for {cid}")
    if complete:
        marker = json.loads((folder / "complete.json").read_text(encoding="utf-8"))
        if marker["plan_sha256"] != _hash_object(plan):
            raise ValueError("completion marker belongs to a different plan")
        for label, arm in arms.items():
            _complete_records(arm)
            if arm is baseline:
                continue
            arm.validate_source(arm.data)
            for row in arm.get_records():
                cid = row["candidate_id"]
                if is_base_infra_failure(row):
                    continue
                if label == "D delete only":
                    from .omar_delete_only import parse_selection, subset_source
                    context = arm.source_context[cid]
                    if (row["source_eligible"] != context["eligible"]
                            or row["source_suite_sha256"] != context["source_sha256"]):
                        raise ValueError(f"{arm.run_name}: completed source linkage changed")
                    if row["selection"] is not None:
                        retain, rationale = parse_selection(row["calls"][0]["raw"])
                        if retain != row["selection"] or rationale != row["selection_rationale"]:
                            raise ValueError(f"{arm.run_name}: completed selection changed")
                        source, _ = subset_source(context["source"], retain)
                        if retain and source != row["tests_src"]:
                            raise ValueError(f"{arm.run_name}: retained original tests changed")
                else:
                    from .test_repair import parse_repair
                    context = arm.revision_context[cid]
                    if (row["source_bundle_sha256"] != arm.source_bundle_sha256
                            or row["source_hashes"] != context["provenance"]
                            or row["baseline_run"] != baseline.run_name
                            or row["eligible"] != context["eligible"]):
                        raise ValueError(f"{arm.run_name}: completed source linkage changed")
                    if row["calls"]:
                        parsed = parse_repair(row["calls"][0]["raw"], arm.n_tests)
                        if parsed["error"] is None and parsed["tests_src"] != row["tests_src"]:
                            raise ValueError(f"{arm.run_name}: completed response/source changed")
                result = row.get("execution")
                if result is not None and row["tests_src"] is not None:
                    verdict = arm._verdict(row["calls"], row["tests_src"], row["test_names"],
                                           arm.trigger_space[cid], result)
                    for key, value in verdict.items():
                        if key in row and row[key] != value:
                            raise ValueError(f"{arm.run_name}: completed verdict changed: {key}")
        if "records_sha256" in marker:
            hashes = {label: _sha(arm.records_path.read_bytes()) for label, arm in arms.items()}
            if hashes != marker["records_sha256"]:
                raise ValueError("completed records hash changed")
    return arms


def authorize_inputs(trigger: TriggerSearch, docker_image: str) -> None:
    """Persist explicit parent approval separately from experiment identity."""
    preflight_docker(docker_image)
    _save_once(trigger.config_path.parent / "omar-authorization.json", {
        "allow_paid": True, "max_model_calls": trigger.total,
        "trigger_config_sha256": _sha(trigger.config_path.read_bytes()),
        "dataset_sha256": _sha(Path(trigger.data_path).read_bytes()),
        "docker_image": docker_image,
    })


def _verify_input_authorization(trigger: TriggerSearch) -> None:
    from .omar_runtime import require_paid
    path = trigger.config_path.parent / "omar-authorization.json"
    if not path.is_file():
        raise PermissionError("Omar fresh-input worker has no explicit paid authorization")
    approval = json.loads(path.read_text(encoding="utf-8"))
    require_paid(approval["allow_paid"], approval["max_model_calls"], trigger.total)
    if (approval["trigger_config_sha256"] != _sha(trigger.config_path.read_bytes())
            or approval["dataset_sha256"] != _sha(Path(trigger.data_path).read_bytes())):
        raise ValueError("Omar fresh-input authorization dependency changed")
    preflight_docker(approval["docker_image"])


def _verify_plan(plan: dict) -> None:
    checked = study_plan(data=plan["data"], model=plan["model"],
                         triggers=plan["triggers"], prefix=plan["prefix"],
                         docker_image=plan["docker_image"],
                         include_delete_only=plan["include_delete_only"],
                         study_kind=plan["study_kind"], settings=plan["settings"],
                         allow_unusable_inputs=plan["allow_unusable_inputs"],
                         reference_run=plan["reference_run"])
    if checked != plan:
        raise ValueError("dataset, trigger inputs, or study settings changed after approval")


def _reviewed_inputs(prefix: str, trigger: TriggerSearch) -> tuple[str, str, bool]:
    """Require a frozen, independent statement-only review of fresh inputs."""
    from .omar_input_review import finalize_review, review_template

    folder = Path("runs") / f"{prefix}-coordinator"
    reviewed_name = f"{prefix}-reviewed-inputs"
    template = review_template(trigger.data_path, trigger.run_name, reviewed_name, folder)
    accepted, message = finalize_review(trigger.data_path, trigger.run_name, reviewed_name, folder)
    if not accepted:
        return reviewed_name, f"Fresh triggers finished; review {template}. {message}", False
    return reviewed_name, "Statement-only review accepted; proceeding to Omar A", True

def advance_historical(*, pool: str, prefix: str, approval: str | None = None,
                       max_paid_calls: int | None = None,
                       docker_image: str | None = None,
                       accept_image_difference: bool = False) -> tuple[dict, str, dict[str, UnitTesting]]:
    """Fresh historical-population trigger run, review gate, then A/B/C(/D)."""
    if pool not in HISTORICAL:
        raise ValueError(f"pool must be one of {sorted(HISTORICAL)}")
    spec = HISTORICAL[pool]
    path = Path(spec["data"])
    if not path.exists() or _sha(path.read_bytes()) != spec["sha256"]:
        raise ValueError(f"historical {pool} dataset missing or changed: {path}")
    data = Dataset.load(path)
    count = sum(1 for _ in data.candidates())
    if count != spec["candidates"]:
        raise ValueError(f"historical {pool} candidate count changed")
    image = spec["image"] if docker_image is None else docker_image
    if not image:
        raise ValueError("Docker image must be a pinned digest or explicit local image name")
    if image != spec["image"] and not accept_image_difference:
        raise ValueError("rebuilt image differs from historical digest; set accept_image_difference=True")
    return _advance_fresh_population(pool=pool, path=path, image=image,
                                     delete=spec["delete"], prefix=prefix,
                                     approval=approval, max_paid_calls=max_paid_calls)


def advance_shared(*, reference_arm: UnitTesting, prefix: str,
                   model: str = OMAR_MODELS["terra"],
                   approval: str | None = None,
                   max_paid_calls: int | None = None) -> tuple[dict, str, dict[str, UnitTesting]]:
    """Generate same-model Omar inputs, then advance arms on the shared population.

    The notebook arm supplies population and runtime settings only. Its records
    and trigger inputs are not read or reused by the Omar study.
    """
    if Path.cwd() != Path(__file__).resolve().parents[2]:
        raise ValueError("run the Omar cell from the repository root; runs/ is CWD-relative")
    if type(reference_arm) is not UnitTesting:
        raise TypeError("reference_arm must be the notebook's UnitTesting arm")
    if not reference_arm.config_path.is_file():
        raise ValueError("reference arm has no saved config; finish its notebook cell first")
    if json.loads(reference_arm.config_path.read_text(encoding="utf-8")) != reference_arm.config():
        raise ValueError("reference arm config differs from the notebook object")
    settings = {"n_tests": reference_arm.n_tests, "seed": reference_arm.seed,
                "reasoning": reference_arm.reasoning.value,
                "max_tokens": reference_arm.max_tokens,
                "call_seconds": reference_arm.call_seconds,
                "sandbox_seconds": reference_arm.sandbox_seconds, "cache": False}
    if reference_arm.n_tests != 10 or reference_arm.runs != 1:
        raise ValueError("shared Omar study needs the notebook's one-run ten-test reference")
    if model not in OMAR_MODELS.values():
        raise ValueError(f"model must be one of the configured Omar models: {sorted(OMAR_MODELS)}")
    selected_model = model
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", prefix):
        raise ValueError("prefix must be a stable run-name slug")

    trigger = TriggerSearch(
        run_name=f"{prefix}-triggers", data=reference_arm.data_path,
        model=selected_model, num_inputs=DEFAULT_NUM_INPUTS, code_visible=True,
        reasoning=reference_arm.reasoning.value, seed=reference_arm.seed,
        cache=False,
    )
    trigger.write_config()
    input_rows = trigger.get_records()
    input_ids = [row["candidate_id"] for row in input_rows]
    wanted_ids = {candidate.candidate_id for _, candidate in trigger.data.candidates()}
    if len(input_ids) != len(set(input_ids)) or not set(input_ids).issubset(wanted_ids):
        raise ValueError("Omar trigger run has duplicate or foreign candidate records")
    pending = trigger.pending()
    if pending:
        identity = {
            "dataset_sha256": _sha(Path(reference_arm.data_path).read_bytes()),
            "trigger_config": trigger.config(),
            "runtime_settings": settings,
            "docker_image": reference_arm.docker_image,
            "reference_config_sha256": _sha(reference_arm.config_path.read_bytes()),
        }
        digest = _hash_object(identity)[:16]
        token = (f"RUN-OMAR-{prefix}-fresh-inputs-{len(pending)}-{digest}")
        plan = {"next_phase": "fresh-inputs", "model": selected_model,
                "triggers": trigger.run_name, "candidate_count": trigger.total,
                "pending_inputs": len(pending), "input_model": selected_model,
                "input_num_inputs": DEFAULT_NUM_INPUTS,
                "cross_model_inputs": False,
                "trigger_config_sha256": _hash_object(trigger.config()),
                "dataset_sha256": _sha(Path(reference_arm.data_path).read_bytes()),
                "runtime_settings": settings,
                "docker_image": reference_arm.docker_image,
                "reference_config_sha256": identity["reference_config_sha256"],
                "workflow_max_logical_calls": trigger.total * (
                    5 if reference_arm.data.backend == "bcb" else 4),
                "phase_paid_call_limit": len(pending), "phase_approval_token": token}
        if _session_alive(trigger.run_name):
            return plan, f"Fresh Omar inputs running: {trigger.run_name}", {}
        if approval != token or max_paid_calls != len(pending):
            return plan, (f"No paid call launched. To generate Omar inputs, approve {token} "
                          f"and max_paid_calls={len(pending)}."), {}
        authorize_inputs(trigger, reference_arm.docker_image)
        command = [sys.executable, "-m", "pipeline.protocols.omar_runner",
                   "--inputs", trigger.run_name]
        if os.name == "nt":
            _launch_windows_coordinator(trigger.run_name, command)
        else:
            launch.launch(trigger.run_name, command, cwd=Path.cwd())
        return plan, f"Fresh Omar inputs launched: {trigger.run_name}", {}

    _complete_records(trigger)
    return advance_study(
        data=reference_arm.data_path, model=selected_model,
        triggers=trigger.run_name, prefix=prefix,
        docker_image=reference_arm.docker_image,
        include_delete_only=reference_arm.data.backend == "bcb",
        study_kind="shared", settings=settings, allow_unusable_inputs=True,
        reference_run=reference_arm.run_name,
        approval=approval, max_paid_calls=max_paid_calls)


def advance_expanded(*, source_pool: str, n_tasks: int, selection_seed: int,
                     prefix: str, approval: str | None = None,
                     max_paid_calls: int | None = None) -> tuple[dict, str, dict[str, UnitTesting]]:
    """Outcome-blind larger task sample, then the same fresh-input workflow.

    This is an expanded-population experiment, never a historical 30/26 claim.
    """
    from .omar_population import select_omar_population

    allowed = {"data/apps_uniform400.json", "data/bcbas.json"}
    if source_pool not in allowed:
        raise ValueError(f"expanded source_pool must be one of {sorted(allowed)}")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", prefix):
        raise ValueError("prefix must be a stable run-name slug")
    selected = select_omar_population(source_pool, n_tasks, selection_seed,
                                       f"data/{prefix}-selected.json")
    path = Path(selected)
    dataset = Dataset.load(path)
    is_bcb = dataset.backend == "bcb"
    image = "pbt-bcb:2" if is_bcb else "python:3.12-slim"
    return _advance_fresh_population(pool="expanded-bcb" if is_bcb else "expanded-apps",
                                     path=path, image=image, delete=is_bcb,
                                     prefix=prefix, approval=approval,
                                     max_paid_calls=max_paid_calls)


def _advance_fresh_population(*, pool: str, path: Path, image: str, delete: bool,
                              prefix: str, approval: str | None,
                              max_paid_calls: int | None) -> tuple[dict, str, dict[str, UnitTesting]]:
    data = Dataset.load(path)
    count = sum(1 for _ in data.candidates())
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", prefix):
        raise ValueError("prefix must be a stable run-name slug")
    trigger = OmarTriggerSearch(run_name=f"{prefix}-triggers", data=str(path),
                                model=HISTORICAL_MODEL, num_inputs=10,
                                code_visible=True, reasoning="low", seed=300, cache=False)
    if trigger.config_path.exists():
        if json.loads(trigger.config_path.read_text(encoding="utf-8")) != trigger.config():
            raise ValueError("fresh trigger name already belongs to a different run")
    trigger.write_config()
    if trigger.pending():
        input_identity = _sha((_sha(path.read_bytes()) + image).encode())[:16]
        token = f"RUN-OMAR-{prefix}-fresh-triggers-{count}-{input_identity}"
        plan = {"pool": pool, "data": str(path), "candidate_count": count,
                "next_phase": "fresh-triggers", "phase_paid_call_limit": count,
                "phase_approval_token": token, "model": HISTORICAL_MODEL,
                "docker_image": image}
        if _session_alive(trigger.run_name):
            return plan, f"Fresh trigger search running: {trigger.run_name}", {}
        if approval != token or max_paid_calls != count:
            return plan, (f"No paid call launched. To generate fresh inputs, approve {token} "
                          f"and max_paid_calls={count}."), {}
        trigger.run(wait=False)
        return plan, f"Fresh trigger search launched: {trigger.run_name}", {}
    _complete_records(trigger)
    reviewed_name, review_status, accepted = _reviewed_inputs(prefix, trigger)
    if not accepted:
        return {"pool": pool, "data": str(path), "candidate_count": count,
                "next_phase": "statement-only-review", "review_path": str(
                    Path("runs") / f"{prefix}-coordinator" / "input-review.json")}, review_status, {}
    plan, status, arms = advance_study(
        data=str(path), model=HISTORICAL_MODEL, triggers=reviewed_name,
        prefix=prefix, docker_image=image, include_delete_only=delete,
        approval=approval, max_paid_calls=max_paid_calls)
    return plan, f"{review_status}. {status}", arms


def advance_study(*, data: str, model: str, triggers: str, prefix: str,
                  docker_image: str = "python:3.12-slim",
                  include_delete_only: bool = False,
                  study_kind: str = "historical", settings: dict | None = None,
                  allow_unusable_inputs: bool = False,
                  reference_run: str = "",
                  approval: str | None = None,
                  max_paid_calls: int | None = None) -> tuple[dict, str, dict[str, UnitTesting]]:
    """Advance one reviewed phase in a detached coordinator after acknowledgement.

    Re-running with the same prefix only attaches to immutable study artifacts.
    Returned arms are complete or the mapping is empty; partial plots are impossible.
    """
    plan = study_plan(data=data, model=model, triggers=triggers, prefix=prefix,
                      docker_image=docker_image, include_delete_only=include_delete_only,
                      study_kind=study_kind, settings=settings,
                      allow_unusable_inputs=allow_unusable_inputs,
                      reference_run=reference_run)
    folder = Path("runs") / f"{prefix}-coordinator"
    plan_path = folder / "plan.json"
    done = folder / "complete.json"
    failed = folder / "failed.json"
    if plan_path.exists():
        if json.loads(plan_path.read_text(encoding="utf-8")) != plan:
            raise ValueError("study run name already belongs to a different plan")
    if done.exists():
        saved = json.loads(done.read_text(encoding="utf-8"))
        if saved["plan_sha256"] != _hash_object(plan):
            raise ValueError("completion marker belongs to a different plan")
        arms = verify_cached_study(plan, complete=True)
        return plan, "Omar study complete; all required arms verified", arms
    if failed.exists():
        detail = json.loads(failed.read_text(encoding="utf-8"))
        raise RuntimeError(f"Omar coordinator stopped at {detail['stage']}: {detail['error']}")
    phases = ("A-smoke", "A-full", "revision-smoke", "revision-full")
    phase = next((each for each in phases if not (folder / f"{each}-complete.json").exists()), None)
    if phase is None:
        raise ValueError("all phase markers exist but complete.json is absent")
    for completed in phases[:phases.index(phase)]:
        marker = json.loads((folder / f"{completed}-complete.json").read_text(encoding="utf-8"))
        if marker["plan_sha256"] != _hash_object(plan):
            raise ValueError(f"{completed} marker belongs to a different plan")
    plan = {**plan, "next_phase": phase,
            "phase_approval_token": plan["approval_tokens"][phase],
            "phase_paid_call_limit": plan["phase_max_calls"][phase]}
    if _session_alive(folder.name):
        return plan, f"Omar coordinator running: {folder}", {}
    if approval != plan["phase_approval_token"] or max_paid_calls != plan["phase_paid_call_limit"]:
        return plan, (f"Paused before {phase}. Review the preceding artifacts, then set approval "
                      f"to {plan['phase_approval_token']} and max_paid_calls to "
                      f"{plan['phase_paid_call_limit']}. This is a logical-call limit, "
                      "not a monetary cap."), {}
    stored_plan = {key: value for key, value in plan.items()
                   if key not in {"next_phase", "phase_approval_token", "phase_paid_call_limit"}}
    _save_once(plan_path, stored_plan)
    request = folder / f"{phase}-request.json"
    preflight_docker(docker_image)
    _save_once(request, {"phase": phase, "plan_sha256": _hash_object(stored_plan),
                         "approval": approval, "max_paid_calls": max_paid_calls})
    command = [sys.executable, "-m", "pipeline.protocols.omar_runner",
               "--coordinate", str(request)]
    if os.name == "nt":
        _launch_windows_coordinator(folder.name, command)
    else:
        launch.launch(folder.name, command)
    return plan, f"Omar {phase} phase launched: {folder}", {}


def _smoke_candidate(plan: dict, baseline: OmarInitial | None = None) -> str:
    """One usable input/source candidate shared by every smoke arm."""
    data = Dataset.load(plan["data"])
    spaces, _ = spaces_from(plan["triggers"], data)
    source_by_id = {} if baseline is None else {
        row["candidate_id"]: row for row in baseline.get_records()}
    for _, candidate in data.candidates():
        cid = candidate.candidate_id
        if cid not in spaces:
            continue
        if baseline is not None:
            row = source_by_id[cid]
            if not row["calls"]:
                continue
            source, error = suite_source(row["calls"][0]["raw"])
            if source is None or error is not None or len(test_names_in(source)) != 10:
                continue
        return cid
    raise ValueError("no candidate has usable reviewed inputs and a callable ten-test A source")


def _execute_candidates(arm: UnitTesting, *, limit: int | None = None,
                        candidate_id: str | None = None) -> None:
    """Execute in this process so the BCB deepcopy harness remains installed."""
    arm.write_config()
    pending = arm.pending()
    if candidate_id is not None:
        pending = [(task, candidate) for task, candidate in pending
                   if candidate.candidate_id == candidate_id]
    if not pending:
        return
    if limit is not None:
        pending = pending[:limit]
    arm.pending = lambda: pending
    try:
        arm.execute()
    finally:
        del arm.pending


def _freeze_source(plan: dict, baseline: OmarInitial, folder: Path) -> Path:
    bundle = folder / "source-bundle.json"
    freeze_request = folder / "freeze-request.json"
    dependencies = {"dataset_sha256": Path(baseline.data_path),
                    "source_config_sha256": baseline.config_path,
                    "source_records_sha256": baseline.records_path,
                    "input_records_sha256": Path("runs") / baseline.triggers / "records.jsonl"}
    _save_once(freeze_request, {"baseline_run": baseline.run_name,
                                "bundle": str(bundle),
                                "allow_unusable_inputs": plan["allow_unusable_inputs"],
                                **{key: _sha(path.read_bytes()) for key, path in dependencies.items()}})
    return freeze_bundle(freeze_request)


def coordinate_study(request: Path) -> None:
    """Run one explicitly approved phase, in one detached process."""
    command = json.loads(request.read_text(encoding="utf-8"))
    folder = request.parent
    plan = json.loads((folder / "plan.json").read_text(encoding="utf-8"))
    _verify_plan(plan)
    phase = command["phase"]
    if command["plan_sha256"] != _hash_object(plan) or phase not in plan["approval_tokens"]:
        raise ValueError("phase request does not match the frozen study plan")
    if (command.get("approval") != plan["approval_tokens"][phase]
            or type(command.get("max_paid_calls")) is not int
            or command["max_paid_calls"] != plan["phase_max_calls"][phase]):
        raise PermissionError("Omar phase request has no explicit paid authorization")
    preflight_docker(plan["docker_image"])
    if plan["include_delete_only"] and plan["study_kind"] != "shared":
        install_bcb_harness()
    baseline = _baseline(plan)
    stage = phase
    try:
        if phase == "A-smoke":
            baseline.write_config()
            smoke_id = _smoke_candidate(plan)
            if not baseline.get_records():
                _execute_candidates(baseline, candidate_id=smoke_id)
            smoke_rows = baseline.get_records()
            if (len(smoke_rows) != 1 or smoke_rows[0]["candidate_id"] != smoke_id
                    or len(smoke_rows[0]["calls"]) != 1):
                raise ValueError("A smoke must make one actual model call on a usable candidate")
        elif phase == "A-full":
            _execute_candidates(baseline)
            _complete_records(baseline)
            stage = "source replay and freeze"
            _freeze_source(plan, baseline, folder)
        elif phase == "revision-smoke":
            _complete_records(baseline)
            arms = _revisions(plan, baseline, folder / "source-bundle.json")
            smoke_id = _smoke_candidate(plan, baseline)
            for label, arm in list(arms.items())[1:]:
                stage = label
                arm.write_config()
                if not arm.get_records():
                    _execute_candidates(arm, candidate_id=smoke_id)
                smoke_rows = arm.get_records()
                if (len(smoke_rows) != 1 or smoke_rows[0]["candidate_id"] != smoke_id
                        or len(smoke_rows[0]["calls"]) != 1):
                    raise ValueError(f"{arm.run_name}: smoke did not make one actual call")
        elif phase == "revision-full":
            _complete_records(baseline)
            arms = _revisions(plan, baseline, folder / "source-bundle.json")
            revisions = list(arms.values())[1:]
            paired = revisions[:2]
            while any(arm.pending() for arm in paired):
                for arm in paired:
                    if arm.pending():
                        stage = arm.run_name
                        _execute_candidates(arm, limit=8)
            for arm in revisions[2:]:
                stage = arm.run_name
                _execute_candidates(arm)
            for arm in arms.values():
                _complete_records(arm)
            _save_once(folder / "complete.json", {"plan_sha256": _hash_object(plan),
                                                   "records_sha256": {label: _sha(arm.records_path.read_bytes())
                                                                      for label, arm in arms.items()},
                                                   "runs": {label: arm.run_name for label, arm in arms.items()},
                                                   "candidate_count": plan["candidate_count"]})
        else:
            raise ValueError(f"unknown study phase {phase!r}")
        _save_once(folder / f"{phase}-complete.json", {"plan_sha256": _hash_object(plan),
                                                      "stage": phase})
    except Exception as error:
        _save_once(folder / "failed.json", {"stage": stage,
                                             "error": f"{type(error).__name__}: {error}"})
        raise


def freeze_bundle(request_path: Path) -> Path:
    """Replay each saved baseline suite once; write an immutable source bundle."""
    request = json.loads(request_path.read_text(encoding="utf-8"))
    baseline = Run.attach(request["baseline_run"])
    if not isinstance(baseline, UnitTesting):
        raise TypeError("source run must be a UnitTesting-derived first turn")
    data = Dataset.load(baseline.data_path)
    if baseline.pending():
        raise ValueError("baseline has not scored every candidate")
    paths = {
        "dataset_sha256": Path(baseline.data_path),
        "source_config_sha256": baseline.config_path,
        "source_records_sha256": baseline.records_path,
        "input_records_sha256": Path("runs") / baseline.triggers / "records.jsonl",
    }
    for key, path in paths.items():
        if _sha(path.read_bytes()) != request[key]:
            raise ValueError(f"{key} changed since feedback was requested")
    spaces, unusable = spaces_from(baseline.triggers, data)
    if unusable and not request.get("allow_unusable_inputs", False):
        raise ValueError(f"{len(unusable)} candidate(s) lack usable fixed inputs")
    rows = load_records(baseline.run_name)
    by_id = {row["candidate_id"]: row for row in rows}
    wanted = {candidate.candidate_id for _, candidate in data.candidates()}
    if len(rows) != len(wanted) or set(by_id) != wanted:
        raise ValueError("baseline has duplicate or missing candidates")
    bundle = {"schema_version": 1, "candidates": {},
              **{key: request[key] for key in paths}}
    output = Path(request["bundle"])
    for task, candidate in data.candidates():
        cid = candidate.candidate_id
        row = by_id[cid]
        raw = row["calls"][0]["raw"] if row["calls"] else ""
        source, error = suite_source(raw)
        identity = {
            "source_record_sha256": _hash_object(row),
            "inputs_sha256": None if cid in unusable else _hash_object(spaces[cid]),
            "code_sha256": _sha(candidate.code.encode()),
            "suite_sha256": None if source is None else _sha(source.encode()),
        }
        # Candidate IDs come from dataset artifacts, not a filesystem namespace.
        cache = output.parent / "source-feedback" / f"{_sha(cid.encode())}.json"
        if cache.exists():
            saved = json.loads(cache.read_text(encoding="utf-8"))
            if saved["identity"] != identity:
                raise ValueError(f"cached feedback source changed for {cid}")
            result = saved["result"]
        else:
            result = None
            if source is not None and cid not in unusable:
                try:
                    result = sandbox.run_raw(
                        task, candidate.code, source, spaces[cid],
                        timeout_s=baseline.sandbox_seconds,
                        isolation=sandbox.Isolation.DOCKER,
                        docker_image=baseline.docker_image,
                    )
                except Exception as exc:
                    result = {"ok": False, "complete": False, "props": [],
                              "records": [], "n_records": 0, "n_expected": 0,
                              "error": f"{type(exc).__name__}: {exc}"[:300]}
            _save_once(cache, {"identity": identity, "result": result})
        if raw and cid not in unusable:
            feedback_summary(result, error, source, spaces[cid])
        bundle["candidates"][cid] = {**identity, "result": result}
    _save_once(output, bundle)
    return output


def run_inputs(run_name: str) -> None:
    """Execute a saved standard TriggerSearch without the base status polling wrapper."""
    trigger = Run.attach(run_name)
    if type(trigger) is not TriggerSearch:
        raise TypeError("Omar's fresh-input runner requires a standard TriggerSearch run")
    if not trigger.pending():
        _complete_records(trigger)
        return
    _verify_input_authorization(trigger)
    trigger.execute()


def main() -> None:
    parser = argparse.ArgumentParser(description="Omar's detached multi-turn study")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", type=Path)
    action.add_argument("--coordinate", type=Path)
    action.add_argument("--inputs", metavar="RUNNAME")
    args = parser.parse_args()
    if args.coordinate is not None:
        coordinate_study(args.coordinate)
    elif args.inputs is not None:
        run_inputs(args.inputs)
    else:
        print(freeze_bundle(args.freeze))


if __name__ == "__main__":
    main()
