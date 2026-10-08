"""Multi-turn test authoring: an initial suite, its execution feedback, and one revision.

Five runs, each an ordinary protocol launched by `Run.run()` and resumed from its own directory:

    inputs   TriggerSearch       fresh inputs, same model as every arm below
    A        MultiTurnInitial    ten traceable tests, code visible
    replay   MultiTurnReplay     A's saved suites run once in Docker; no model call
    B, C     MultiTurnRevision   one revision with A's feedback withheld (B) or shown (C)
    D        MultiTurnDeleteOnly BigCodeBench only: keep a subset of A's tests, never rewrite

The replay is its own run because B and C must read the *same* feedback: a stage whose output two
protocols consume is named and reused, never recomputed by each (AGENTS.md, "Splitting one call
into its own run"). `write_source_bundle` freezes the replay into the hash-checked file that
`SecondRevision` already reads, so B and C are aedev's revision protocol with the population rules
of a shared notebook pool, not a second implementation of it.

`MultiTurnStudy` is the notebook-facing chain. It runs the whole chain on a one-task smoke dataset
first, refuses any stage with paid work left unless `allow_paid=True`, and otherwise only calls
`.run()` on each arm in order. Nothing here touches tmux, threads or `records.jsonl` itself.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .. import launch, model as model_mod, sandbox
from ..data import Blame, Dataset, RUNS_DIR, load_records
from .base import CALLS, FAILURE_FIELDS, IDENTITY_FIELDS, Run
from .second_revision import SecondRevision
from .test_repair import feedback_summary
from .trigger_search import DEFAULT_NUM_INPUTS, TriggerSearch
from .unit_testing import UnitTesting, spaces_from, suite_source

MULTI_TURN_MODELS = {
    "deepseek": "openai-api/azureai/DeepSeek-V3.2",
    "terra": "openai-api/azureai/gpt-5.6-terra",
}
DEFAULT_MODEL = MULTI_TURN_MODELS["deepseek"]

TESTS_PER_SUITE = 10
FRAMING = "traceable_v1"
RESOLVE = "with"
BCB_BACKEND = "bcb"

INPUTS = "inputs"
A_INITIAL = "A initial"
REPLAY = "replay"
B_NO_FEEDBACK = "B no feedback"
C_FEEDBACK = "C feedback"
D_DELETE_ONLY = "D delete only"
ARM_LABELS = (A_INITIAL, B_NO_FEEDBACK, C_FEEDBACK, D_DELETE_ONLY)
PAID_STAGES = (INPUTS, A_INITIAL, B_NO_FEEDBACK, C_FEEDBACK, D_DELETE_ONLY)

BUNDLE_FILE = "source-bundle.json"
BUNDLE_SCHEMA_VERSION = 1
BUNDLE_FIELDS = ("source_record_sha256", "inputs_sha256", "code_sha256", "suite_sha256", "result")
BASELINE_PROTOCOLS = frozenset({"unit_testing", "multi_turn_initial"})
SMOKE_SUFFIX = "multi_turn_smoke"
DOCKER_START_SECONDS = 180
RUN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
SHA256 = re.compile(r"[0-9a-f]{64}")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _object_sha(value: Any) -> str:
    return _sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _save_once(path: Path, value: Any) -> None:
    """Write a derived artifact once; an existing one that differs raises instead of being replaced."""
    text = json.dumps(value, sort_keys=True, indent=2) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise ValueError(f"{path} already exists with different content; it is derived from "
                             "saved records, so a difference means an input changed underneath it")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text)


def require_docker(image: str) -> None:
    """Raise before any paid call when `image` cannot run a container.

    Uses the team's `sandbox.preflight` where this checkout has it (the BigCodeBench line added
    it), and the same `docker run --rm <image> true` check otherwise, so a missing daemon is one
    error at prepare time rather than one infra record per candidate after the model was paid.
    """
    preflight = getattr(sandbox, "preflight", None)
    if preflight is not None:
        preflight(image)
        return
    if shutil.which("docker") is None:
        raise RuntimeError("docker is not on PATH, so no sandbox grid can run")
    try:
        started = subprocess.run(["docker", "run", "--rm", image, "true"],
                                 capture_output=True, timeout=DOCKER_START_SECONDS)
    except subprocess.TimeoutExpired as slow:
        raise RuntimeError(f"`docker run {image} true` did not return within "
                           f"{DOCKER_START_SECONDS}s") from slow
    if started.returncode != 0:
        detail = (started.stderr or started.stdout or b"").decode("utf-8", "replace").strip()
        raise RuntimeError(f"`docker run {image} true` exited {started.returncode}: {detail[:400]}")


def is_base_infra_failure(record: dict[str, Any]) -> bool:
    """The record `Run._record_for` writes when `score` raised: identity, failure triple, no calls."""
    return (set(record) == {*IDENTITY_FIELDS, *FAILURE_FIELDS, CALLS}
            and record["failed"] is True and record["blame"] == Blame.INFRA.value
            and type(record["reason"]) is str and bool(record["reason"])
            and record[CALLS] == [])


class MultiTurnInitial(UnitTesting):
    """Arm A: the first suite, ten traceable code-visible tests over this study's own inputs.

    `UnitTesting` with the design fixed, and one difference in `score`: a candidate whose fresh
    trigger search failed keeps that search's blame, so an input run that died on infra is not
    booked as the authoring model's failure.
    """

    protocol = "multi_turn_initial"

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("code_visible", True)
        kwargs.setdefault("test_gen_prompt", FRAMING)
        kwargs.setdefault("resolve", RESOLVE)
        kwargs.setdefault("n_tests", TESTS_PER_SUITE)
        super().__init__(**kwargs)
        if (self.code_visible is not True or self.framing != FRAMING or self.resolve != RESOLVE
                or self.n_tests != TESTS_PER_SUITE or self.critique or self.critique_informed):
            raise ValueError(f"{self.run_name}: arm A is ten traceable code-visible tests "
                             "resolved with the specification, without critique")
        self.input_failure_blame: dict[str, str] = {}

    def prepare(self, data: Dataset) -> None:
        require_docker(self.docker_image)
        super().prepare(data)
        rows = {row["candidate_id"]: row for row in load_records(self.triggers)}
        self.input_failure_blame = {}
        for cid in self.no_trigger_space:
            if cid not in rows:
                raise ValueError(f"{cid}: no record in {self.triggers}, so the run is unfinished")
            row = rows[cid]
            blame = row["blame"] if row["failed"] else Blame.MODEL.value
            if blame not in {kind.value for kind in Blame}:
                raise ValueError(f"{cid}: input record carries blame {blame!r}")
            self.input_failure_blame[cid] = blame

    def score(self, task, candidate):
        cid = candidate.candidate_id
        if cid in self.no_trigger_space:
            return self._unmeasured([], self.input_failure_blame[cid],
                                    f"no trigger inputs: {self.triggers} {self.no_trigger_space[cid]}")
        return super().score(task, candidate)


class MultiTurnReplay(Run):
    """Arm A's saved suites, each run once over its own inputs: the feedback B and C are shown.

    Calls no model. A candidate with no suite or no usable inputs gets `result: None` — nothing ran,
    and nothing is pretended to have run. A sandbox that raises is recorded as a grid with `ok`
    false and the error, which is what the revision prompt's diagnostics are built from.
    """

    protocol = "multi_turn_replay"

    def __init__(self, *, baseline_run: str, triggers: str, sandbox_seconds: int,
                 docker_image: str, **kwargs: Any) -> None:
        kwargs.setdefault("cache", False)
        super().__init__(baseline_run=baseline_run, triggers=triggers,
                         sandbox_seconds=sandbox_seconds, docker_image=docker_image, **kwargs)
        if not baseline_run or not triggers or not docker_image:
            raise ValueError(f"{self.run_name}: baseline_run, triggers and docker_image are required")
        if self.runs != 1:
            raise ValueError(f"{self.run_name}: a replay is one grid per suite, runs must be 1")
        self.baseline_run = baseline_run
        self.triggers = triggers
        self.sandbox_seconds = sandbox_seconds
        self.docker_image = docker_image
        self.baseline_rows: dict[str, dict[str, Any]] = {}
        self.spaces: dict[str, list[Any]] = {}
        self.unusable: dict[str, str] = {}

    def prepare(self, data: Dataset) -> None:
        rows = load_records(self.baseline_run)
        by_id = {row["candidate_id"]: row for row in rows}
        wanted = {candidate.candidate_id for _, candidate in data.candidates()}
        if len(rows) != len(wanted) or set(by_id) != wanted:
            raise ValueError(f"{self.baseline_run} must hold exactly one record per candidate "
                             "before its suites are replayed")
        self.baseline_rows = by_id
        self.spaces, self.unusable = spaces_from(self.triggers, data)
        require_docker(self.docker_image)

    def score(self, task, candidate):
        cid = candidate.candidate_id
        row = self.baseline_rows[cid]
        raw = row[CALLS][0]["raw"] if row[CALLS] else ""
        source, parse_error = suite_source(raw)
        identity = {
            "source_record_sha256": _object_sha(row),
            "inputs_sha256": None if cid in self.unusable else _object_sha(self.spaces[cid]),
            "code_sha256": _sha(candidate.code.encode()),
            "suite_sha256": None if source is None else _sha(source.encode()),
        }
        result = None
        if source is not None and cid not in self.unusable:
            try:
                result = sandbox.run_raw(task, candidate.code, source, list(self.spaces[cid]),
                                         timeout_s=self.sandbox_seconds,
                                         isolation=sandbox.Isolation.DOCKER,
                                         docker_image=self.docker_image)
            except Exception as error:
                result = {"ok": False, "complete": False, "props": [], "records": [],
                          "n_records": 0, "n_expected": 0,
                          "error": f"{type(error).__name__}: {error}"[:300]}
        if raw and cid not in self.unusable:
            # Raises on a grid the revision prompt could not show; the base records that as infra.
            feedback_summary(result, parse_error, source, self.spaces[cid])
        return {CALLS: [], **identity, "result": result}


def write_source_bundle(replay: MultiTurnReplay) -> tuple[Path, str]:
    """Freeze a finished replay into the bundle `SecondRevision` verifies; return path and SHA-256.

    Written once beside the replay run. Every hash is taken now, and every replay row must still
    describe the arm-A record it replayed, so an A run edited after its replay cannot be revised.
    """
    rows = replay.get_records()
    by_id = {row["candidate_id"]: row for row in rows}
    wanted = [candidate.candidate_id for _, candidate in replay.data.candidates()]
    if len(rows) != len(wanted) or set(by_id) != set(wanted):
        raise ValueError(f"{replay.run_name} must hold exactly one record per candidate")
    failed = {cid: row["reason"] for cid, row in by_id.items() if row["failed"]}
    if failed:
        raise ValueError(f"{replay.run_name} has {len(failed)} failed replay(s), so B and C would "
                         f"be shown no feedback for them: {dict(list(failed.items())[:3])}")
    baseline = {row["candidate_id"]: row for row in load_records(replay.baseline_run)}
    changed = [cid for cid in wanted if by_id[cid]["source_record_sha256"] != _object_sha(baseline[cid])]
    if changed:
        raise ValueError(f"{replay.baseline_run} changed after it was replayed: {changed[:3]}")
    dependencies = {
        "dataset_sha256": Path(replay.data_path),
        "source_config_sha256": RUNS_DIR / replay.baseline_run / "config.json",
        "source_records_sha256": RUNS_DIR / replay.baseline_run / "records.jsonl",
        "input_records_sha256": RUNS_DIR / replay.triggers / "records.jsonl",
    }
    bundle = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "candidates": {cid: {field: by_id[cid][field] for field in BUNDLE_FIELDS} for cid in wanted},
        **{key: _sha(path.read_bytes()) for key, path in dependencies.items()},
    }
    path = replay.directory / BUNDLE_FILE
    _save_once(path, bundle)
    return path, _sha(path.read_bytes())


class MultiTurnRevision(SecondRevision):
    """Arms B and C: `SecondRevision`'s prompt, call and verdict, over a shared notebook pool.

    `SecondRevision` was written for a fresh test-only population with every input usable. A
    notebook pool has a train half, and a fresh input run can leave a candidate without inputs,
    so this class keeps its prompt and `score` and owns only what differs:

    - train and test candidates both revise, each record keeping its own split;
    - a candidate with no usable inputs is a failed record with the input run's blame and no call,
      never a revision of something that could not run;
    - an arm-A record whose `score` raised is recognised as infra rather than as a missing suite;
    - transport retries follow `UnitTesting`, the policy every arm it is compared with uses.
    """

    protocol = "multi_turn_revision"

    def __init__(self, *, baseline_run: str, source_bundle: str, source_bundle_sha256: str,
                 feedback_visible: bool, max_candidates: int, **kwargs: Any) -> None:
        if not baseline_run or not source_bundle or not SHA256.fullmatch(source_bundle_sha256):
            raise ValueError("baseline run, source bundle and its exact SHA-256 are required")
        if type(feedback_visible) is not bool or type(max_candidates) is not int or max_candidates < 1:
            raise ValueError("explicit feedback visibility and a positive candidate cap are required")
        kwargs.setdefault("cache", False)
        kwargs.setdefault("max_tokens", 8192)
        kwargs.setdefault("resolve", RESOLVE)
        kwargs.setdefault("test_gen_prompt", FRAMING)
        kwargs.setdefault("code_visible", False)
        # SecondRevision.__init__ would refuse a population with a train half; its parent is the
        # constructor this design actually needs.
        UnitTesting.__init__(self, baseline_run=baseline_run, source_bundle=source_bundle,
                             source_bundle_sha256=source_bundle_sha256,
                             feedback_visible=feedback_visible, max_candidates=max_candidates,
                             **kwargs)
        if (self.code_visible or self.critique or self.critique_informed
                or self.n_tests != TESTS_PER_SUITE or self.framing != FRAMING
                or self.resolve != RESOLVE):
            raise ValueError(f"{self.run_name}: a revision is hidden-code, uncritiqued, ten "
                             "traceable tests resolved with the specification")
        if not self.data.test or self.total > max_candidates:
            raise ValueError(f"{self.run_name}: the population needs a test half and must fit "
                             f"the declared cap of {max_candidates}")
        self.baseline_run = baseline_run
        self.source_bundle = source_bundle
        self.source_bundle_sha256 = source_bundle_sha256
        self.feedback_visible = feedback_visible

    def _runtime(self):
        return UnitTesting._runtime(self)

    def validate_source(self, data: Dataset) -> None:
        """Check the bundle, arm A and the inputs agree, and build one context per candidate."""
        raw_bundle = Path(self.source_bundle).read_bytes()
        if _sha(raw_bundle) != self.source_bundle_sha256:
            raise ValueError("source bundle hash changed")
        bundle = json.loads(raw_bundle)
        paths = {"dataset_sha256": Path(self.data_path),
                 "source_config_sha256": RUNS_DIR / self.baseline_run / "config.json",
                 "source_records_sha256": RUNS_DIR / self.baseline_run / "records.jsonl",
                 "input_records_sha256": RUNS_DIR / self.triggers / "records.jsonl"}
        if (set(bundle) != {"schema_version", "candidates", *paths}
                or bundle["schema_version"] != BUNDLE_SCHEMA_VERSION):
            raise ValueError("unexpected source bundle shape or version")
        for key, path in paths.items():
            if _sha(path.read_bytes()) != bundle[key]:
                raise ValueError(f"{key} changed since the bundle was written")
        baseline = json.loads(paths["source_config_sha256"].read_text(encoding="utf-8"))
        baseline = baseline | baseline["params"]
        own = self.config() | self.config()["params"]
        for key in ("model", "seed", "n_tests", "max_tokens", "reasoning", "call_seconds",
                    "sandbox_seconds", "docker_image", "triggers", "resolve", "test_gen_prompt",
                    "cache"):
            if baseline[key] != own[key]:
                raise ValueError(f"arm A and this revision differ on {key}")
        if (baseline["protocol"] not in BASELINE_PROTOCOLS or baseline["code_visible"] is not True
                or baseline["critique"] or baseline["critique_informed"] or baseline["runs"] != 1
                or baseline["data"] != self.data_path):
            raise ValueError("arm A must be a one-run, code-visible, uncritiqued suite on this data")

        sources = load_records(self.baseline_run)
        inputs = load_records(self.triggers)
        wanted = {candidate.candidate_id for _, candidate in data.candidates()}
        by_id = {row["candidate_id"]: row for row in sources}
        input_by_id = {row["candidate_id"]: row for row in inputs}
        if (len(sources) != len(wanted) or set(by_id) != wanted or len(inputs) != len(wanted)
                or set(input_by_id) != wanted or set(bundle["candidates"]) != wanted):
            raise ValueError("duplicate, missing or unexpected source, input or bundle candidate")
        self.trigger_space, unusable = spaces_from(self.triggers, data)
        self.revision_context = {}
        for task, candidate in data.candidates():
            cid = candidate.candidate_id
            record, row = by_id[cid], bundle["candidates"][cid]
            if set(row) != set(BUNDLE_FIELDS):
                raise ValueError("unexpected source bundle candidate fields")
            split = data.split_of(task.task_id)
            if (record["task_id"] != task.task_id or record["split"] != split
                    or input_by_id[cid]["task_id"] != task.task_id
                    or input_by_id[cid]["split"] != split):
                raise ValueError(f"{cid}: source or input task/split mismatch")
            if (row["source_record_sha256"] != _object_sha(record)
                    or row["code_sha256"] != _sha(candidate.code.encode())):
                raise ValueError(f"{cid}: source record or candidate code changed")
            if len(record[CALLS]) > 1:
                raise ValueError(f"{cid}: arm A holds more than one authoring response")
            raw = record[CALLS][0]["raw"] if record[CALLS] else ""
            source, parse_error = suite_source(raw)
            base_failure = is_base_infra_failure(record)
            if not base_failure and record["tests_src"] is not None and source != record["tests_src"]:
                raise ValueError(f"{cid}: recorded suite differs from the saved response")
            if base_failure and row["result"] is not None:
                raise ValueError(f"{cid}: an arm-A crash cannot have a replay measurement")
            if row["suite_sha256"] != (None if source is None else _sha(source.encode())):
                raise ValueError(f"{cid}: initial suite hash changed")
            provenance = {key: row[key] for key in row if key != "result"}
            if cid in unusable:
                if row["inputs_sha256"] is not None or row["result"] is not None:
                    raise ValueError(f"{cid}: a candidate without inputs cannot have an input hash "
                                     "or a replay")
                source_input = input_by_id[cid]
                blame = source_input["blame"] if source_input["failed"] else Blame.MODEL.value
                if blame not in {kind.value for kind in Blame}:
                    raise ValueError(f"{cid}: input record carries blame {blame!r}")
                self.revision_context[cid] = {
                    "eligible": False, "blame": blame, "provenance": provenance,
                    "reason": f"no usable trigger inputs: {unusable[cid]}"}
                continue
            space = self.trigger_space[cid]
            if row["inputs_sha256"] != _object_sha(space):
                raise ValueError(f"{cid}: input hash changed")
            if not raw:
                self.revision_context[cid] = {
                    "eligible": False, "blame": Blame.INFRA.value, "provenance": provenance,
                    "reason": "no saved arm-A response"}
                continue
            diagnostic = feedback_summary(row["result"], parse_error, source, space)
            self.revision_context[cid] = {
                "eligible": True, "source": source if source is not None else raw,
                "diagnostic": diagnostic, "provenance": provenance,
                "stratum": "parse_recovery" if source is None else
                           "source_failure" if record["failed"] else
                           "complete_source" if diagnostic["complete"] else "partial_source"}

    def prepare(self, data: Dataset) -> None:
        self.validate_source(data)
        require_docker(self.docker_image)
        model_mod.resolve(self._runtime())

    def score(self, task, candidate):
        context = self.revision_context[candidate.candidate_id]
        if context["eligible"]:
            return super().score(task, candidate)
        return self._unmeasured([], context["blame"], context["reason"]) | {
            "eligible": False, "baseline_run": self.baseline_run,
            "source_hashes": context["provenance"],
            "source_bundle_sha256": self.source_bundle_sha256,
            "feedback_visible": self.feedback_visible, "revision_version": 1,
            "assertion_reach_measured": False}


def smoke_dataset(source: str | Path) -> str:
    """A one-task copy of `source`: its first test task, both candidates, written beside it.

    Deterministic, so the same file is rebuilt identically on every machine; an existing file that
    differs raises rather than being overwritten. The task keeps its test split because a revision
    population must hold one.
    """
    source_path = Path(source)
    original = Dataset.load(source_path)
    if not original.test:
        raise ValueError(f"{original.name} has no test task to smoke on")
    task = original.test[0]
    smoke = Dataset(
        name=f"{original.name}_{SMOKE_SUFFIX}",
        backend=original.backend,
        io_mode=original.io_mode,
        tasks=(task,),
        split={half: (task.task_id,) if half == "test" else () for half in original.split},
        built_from={**original.built_from, "smoke_of": str(source_path),
                    "smoke_of_sha256": _sha(source_path.read_bytes()), "smoke_task": task.task_id},
        schema_version=original.schema_version,
    )
    path = source_path.with_name(f"{source_path.stem}_{SMOKE_SUFFIX}.json")
    text = json.dumps(smoke.to_json(), indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != text:
        raise ValueError(f"{path} exists and differs from the smoke dataset {source_path} implies")
    if not path.exists():
        path.write_text(text, encoding="utf-8")
    return str(path)


def _require_complete(run: Run) -> None:
    """Every candidate scored exactly once, or a raise naming what is left."""
    rows = run.get_records()
    ids = [row["candidate_id"] for row in rows]
    wanted = {candidate.candidate_id for _, candidate in run.data.candidates()}
    if len(ids) != len(set(ids)) or set(ids) != wanted:
        still = "still running detached — re-run this cell once it finishes" \
            if launch.alive(run.run_name) else "not running — re-run this cell to resume it"
        raise RuntimeError(f"{run.run_name}: {len(set(ids) & wanted)}/{len(wanted)} candidates "
                           f"scored ({len(ids) - len(set(ids))} duplicate), {still}")


class MultiTurnStudy:
    """The chain on one notebook pool, its settings read off the team's reference arm.

    The reference arm lends the dataset, Docker image and runtime settings; its records and its
    trigger inputs are never read, so nothing the team measured changes. Every stage's cache is
    off: the inputs are fresh and each arm's prompt is its own.
    """

    def __init__(self, *, reference_arm: UnitTesting, prefix: str,
                 model: str = DEFAULT_MODEL) -> None:
        if type(reference_arm) is not UnitTesting:
            raise TypeError("reference_arm must be the team notebook's UnitTesting arm")
        if not RUN_NAME.fullmatch(prefix):
            raise ValueError(f"prefix {prefix!r} must be a run-name slug")
        if not reference_arm.config_path.is_file():
            raise ValueError(f"{reference_arm.run_name} has no config.json — run its cell in the "
                             "team notebook first")
        if json.loads(reference_arm.config_path.read_text(encoding="utf-8")) != reference_arm.config():
            raise ValueError(f"{reference_arm.run_name}: config.json differs from the arm passed in")
        if reference_arm.n_tests != TESTS_PER_SUITE or reference_arm.runs != 1:
            raise ValueError("the reference arm must be a one-run ten-test UnitTesting arm")
        self.reference_arm = reference_arm
        self.prefix = prefix
        self.model = MULTI_TURN_MODELS.get(model, model)
        self.settings = {
            "seed": reference_arm.seed,
            "reasoning": reference_arm.reasoning.value,
            "max_tokens": reference_arm.max_tokens,
            "call_seconds": reference_arm.call_seconds,
            "sandbox_seconds": reference_arm.sandbox_seconds,
            "docker_image": reference_arm.docker_image,
        }
        self.delete_only = reference_arm.data.backend == BCB_BACKEND

    def stages(self) -> tuple[str, ...]:
        return tuple(stage for stage in (INPUTS, A_INITIAL, REPLAY, B_NO_FEEDBACK, C_FEEDBACK,
                                         D_DELETE_ONLY)
                     if stage != D_DELETE_ONLY or self.delete_only)

    def plan(self) -> dict[str, Any]:
        """Upper bounds on logical model calls, smoke chain then full chain; nothing is launched."""
        data = self.reference_arm.data
        smoke_task = data.test[0].task_id
        smoke_candidates = sum(1 for task, _ in data.candidates() if task.task_id == smoke_task)
        full = self.reference_arm.total
        paid = [stage for stage in self.stages() if stage in PAID_STAGES]
        return {
            "model": self.model,
            "stages": list(self.stages()),
            "smoke_calls": {stage: smoke_candidates for stage in paid},
            "full_calls": {stage: full for stage in paid},
            "max_model_calls": (smoke_candidates + full) * len(paid),
            "note": "logical calls; HTTP retries can add provider attempts",
        }

    def run(self, *, allow_paid: bool = False) -> dict[str, Run]:
        """Smoke chain, then the full chain; returns the A/B/C(/D) arms once all are complete."""
        smoke = self._chain(smoke_dataset(self.reference_arm.data_path),
                            f"{self.prefix}-smoke", allow_paid)
        self._require_clean_smoke(smoke)
        full = self._chain(self.reference_arm.data_path, self.prefix, allow_paid)
        return {label: run for label, run in full.items() if label in ARM_LABELS}

    def _chain(self, data: str, prefix: str, allow_paid: bool) -> dict[str, Run]:
        settings = dict(self.settings)
        image = settings.pop("docker_image")
        sandbox_seconds = settings["sandbox_seconds"]
        inputs = TriggerSearch(run_name=f"{prefix}-triggers", data=data, model=self.model,
                               num_inputs=DEFAULT_NUM_INPUTS, code_visible=True,
                               reasoning=settings["reasoning"], seed=settings["seed"], cache=False)
        self._launch(inputs, allow_paid)
        authoring = dict(data=data, model=self.model, triggers=inputs.run_name,
                         docker_image=image, cache=False, **settings)
        initial = MultiTurnInitial(run_name=f"{prefix}-A-traceable", **authoring)
        self._launch(initial, allow_paid)
        replay = MultiTurnReplay(run_name=f"{prefix}-A-replay", data=data,
                                 baseline_run=initial.run_name, triggers=inputs.run_name,
                                 sandbox_seconds=sandbox_seconds, docker_image=image)
        self._launch(replay, allow_paid=True)
        bundle, bundle_sha = write_source_bundle(replay)
        source = dict(baseline_run=initial.run_name, source_bundle=str(bundle),
                      source_bundle_sha256=bundle_sha, max_candidates=initial.total,
                      code_visible=False, **authoring)
        stages: dict[str, Run] = {INPUTS: inputs, A_INITIAL: initial, REPLAY: replay}
        stages[B_NO_FEEDBACK] = MultiTurnRevision(run_name=f"{prefix}-B-no-feedback",
                                                  feedback_visible=False, **source)
        stages[C_FEEDBACK] = MultiTurnRevision(run_name=f"{prefix}-C-feedback",
                                               feedback_visible=True, **source)
        if self.delete_only:
            from .multi_turn_delete_only import MultiTurnDeleteOnly
            stages[D_DELETE_ONLY] = MultiTurnDeleteOnly(run_name=f"{prefix}-D-delete-only",
                                                        **source)
        for label in (B_NO_FEEDBACK, C_FEEDBACK, D_DELETE_ONLY):
            if label in stages:
                self._launch(stages[label], allow_paid)
        return stages

    @staticmethod
    def _launch(run: Run, allow_paid: bool) -> None:
        """`.run()` the stage unless it would pay for calls nobody allowed; then require it complete."""
        run.write_config()
        pending = run.pending()
        if pending and not allow_paid:
            raise PermissionError(
                f"{run.run_name}: {len(pending)} candidate(s) still to score, each a paid model "
                "call. Review study.plan(), record the experiment's prediction, then pass "
                "allow_paid=True")
        run.run()
        _require_complete(run)

    @staticmethod
    def _require_clean_smoke(stages: dict[str, Run]) -> None:
        """Stop before the full chain if any smoke stage hit infrastructure, or A never called."""
        problems = {}
        for label, run in stages.items():
            infra = [row["reason"] for row in run.get_records()
                     if row["failed"] and row["blame"] == Blame.INFRA.value]
            if infra:
                problems[label] = infra[:2]
        if not any(row[CALLS] for row in stages[A_INITIAL].get_records()):
            problems[A_INITIAL] = ["no smoke candidate reached the authoring model"]
        if problems:
            raise RuntimeError(f"smoke chain failed, full chain not started: {problems}")
