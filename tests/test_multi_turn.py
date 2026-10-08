"""The multi-turn chain end to end, through the same `Run` path every team arm takes.

Fakes sit at the process boundary only, as `tests/AGENTS.md` asks: the provider (`resolve`,
`complete_sync`), Docker (`run_raw` and the image check) and tmux (`Run.run` runs the subprocess's
own `write_config` + `execute` in-process, because a tmux subprocess would not see these patches).
Everything between — prompts, parsers, records, the replay, the bundle, `SecondRevision`'s
prompt and verdict, the delete-only cut, the notebook's analysis cell — is the real code.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from build_dataset import build
from pipeline import launch, model as model_mod, sandbox
from pipeline.data import Dataset
from pipeline.model import Completion
from pipeline.protocols import UnitTesting, multi_turn, multi_turn_delete_only
from pipeline.protocols.base import Run
from pipeline.protocols.multi_turn import (A_INITIAL, B_NO_FEEDBACK, C_FEEDBACK, D_DELETE_ONLY,
                                           MultiTurnStudy, UnretriedInfraFailures)
from pipeline.protocols.multi_turn_delete_only import exact_tests, parse_selection, subset_source
from pipeline.protocols.unit_testing import test_names_in as names_in

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL = "mockllm/model"
IMAGE = "python:3.12-slim"
INPUTS = {"stdio": ["1\n", "2\n"], "function": [{"x": 1}, {"x": 2}]}
NO_INPUTS = "I could not think of any inputs for this one."
WITHHELD = "WITHHELD_BY_DESIGN"
TESTS = [{"name": f"test_value_{i}",
          "source": f"def test_value_{i}(run, x):\n    got = run(x)\n    assert got == {i}\n"}
         for i in range(10)]
RETAINED = [test["name"] for test in TESTS[:5]]
AUTHORING_ANSWER = json.dumps({"rationale": "Grounded in the statement.", "tests": TESTS})
REVISION_ANSWER = json.dumps({"abstain": False, "rationale": "Keep the ten.", "tests": TESTS})
SELECTION_ANSWER = json.dumps({"rationale": "Five are justified.", "retain_test_ids": RETAINED})
NOTEBOOKS = REPO_ROOT / "notebooks"
HOOK = "from multi_turn_cells import add_multi_turn_section\nadd_multi_turn_section(POOL, md, code)\n"


def _cells_module():
    spec = importlib.util.spec_from_file_location("multi_turn_cells", NOTEBOOKS / "multi_turn_cells.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CELLS = _cells_module()


class Boundary:
    """The provider, Docker and tmux, scripted; every call they receive is kept for assertions."""

    def __init__(self, data: Dataset, starved: str | None = None, crash_once: str | None = None) -> None:
        self.attack_code = {candidate.code for _, candidate in data.candidates() if candidate.is_attack}
        self.starved_code = next((candidate.code for _, candidate in data.candidates()
                                  if candidate.candidate_id == starved), None)
        self.inputs = INPUTS[data.io_mode]
        self.crash_code = next((candidate.code for _, candidate in data.candidates()
                                if candidate.candidate_id == crash_once), None)
        self.calls: list[tuple[str, str]] = []
        self.grids: list[list[str]] = []
        self.launched: list[str] = []
        self.detached: list[str] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(model_mod, "resolve", lambda runtime: object())
        monkeypatch.setattr(model_mod, "complete_sync", self.complete)
        monkeypatch.setattr(sandbox, "run_raw", self.grid)
        monkeypatch.setattr(sandbox, "preflight", lambda image: None, raising=False)
        monkeypatch.setattr(multi_turn, "require_docker", lambda image: None)
        monkeypatch.setattr(multi_turn_delete_only, "require_docker", lambda image: None)
        monkeypatch.setattr(Run, "run", lambda arm, wait=True: self.run(arm, wait))
        monkeypatch.setattr(launch, "alive", lambda name: False)

    def complete(self, _client, prompt: str, kind: str, schema=None) -> Completion:
        if kind == "trigger_search":
            self.calls.append(("inputs", prompt))
            if self.starved_code is not None and self.starved_code in prompt:
                return Completion(text=NO_INPUTS, stop_reason="stop")
            return Completion(text=f"```json\n{json.dumps(self.inputs)}\n```", stop_reason="stop")
        self.calls.append((schema.name, prompt))
        answers = {"repair_tests": REVISION_ANSWER, "retain_original_test_ids": SELECTION_ANSWER}
        return Completion(text=answers.get(schema.name, AUTHORING_ANSWER), stop_reason="stop")

    def grid(self, _task, code: str, props_src: str, space, **kwargs) -> dict:
        assert kwargs["isolation"] is sandbox.Isolation.DOCKER and kwargs["docker_image"] == IMAGE
        assert list(space) == self.inputs
        names = names_in(props_src)
        if code == self.crash_code:
            self.crash_code = None
            raise OSError("synthetic sandbox outage")
        self.grids.append(names)
        caught = code in self.attack_code
        records = [{"prop": name, "i": i,
                    "outcome": "catch" if caught and name == names[0] and i == 0 else "pass"}
                   for name in names for i in range(len(space))]
        return {"ok": True, "complete": True, "props": names, "records": records,
                "n_records": len(records), "n_expected": len(records), "error": ""}

    def run(self, arm: Run, wait: bool = True) -> None:
        self.launched.append(arm.run_name)
        if not wait:
            self.detached.append(arm.run_name)
        arm.write_config()
        if arm.pending():
            arm.execute()


def _reference(data_path: str) -> UnitTesting:
    reference = UnitTesting(run_name="ut-reference", data=data_path, model=MODEL,
                            triggers="trig-team", test_gen_prompt="property", n_tests=10,
                            docker_image=IMAGE)
    reference.write_config()
    return reference


def _mini_apps(tmp_path) -> Dataset:
    document = build(REPO_ROOT / "apps_pool_hard10.json", REPO_ROOT / "splits/smoke_3.json",
                     "apps", "mini")
    (tmp_path / "mini.json").write_text(json.dumps(document), encoding="utf-8")
    return Dataset.load("mini.json")


def test_the_apps_chain_runs_every_arm_through_the_team_launcher(tmp_path, monkeypatch):
    data = _mini_apps(tmp_path)
    starved = data.train[0].task_id
    starved_id = next(c.candidate_id for t, c in data.candidates()
                      if t.task_id == starved and c.is_attack)
    boundary = Boundary(data, starved=starved_id)
    boundary.install(monkeypatch)
    study = MultiTurnStudy(reference_arm=_reference("mini.json"), prefix="mt", model=MODEL)

    plan = study.plan()
    assert D_DELETE_ONLY not in plan["stages"] and plan["model"] == MODEL
    assert plan["max_model_calls"] == (2 + 6) * 4

    with pytest.raises(PermissionError, match="allow_paid=True"):
        study.run()
    assert boundary.calls == [] and boundary.launched == []
    assert study.complete(smoke_only=True) is False

    chain = ["triggers", "A-traceable", "A-replay", "B-no-feedback", "C-feedback"]
    smoke_arms = study.run(allow_paid=True, smoke_only=True)
    assert boundary.launched == [f"mt-smoke-{stage}" for stage in chain]
    assert list(smoke_arms) == [A_INITIAL, B_NO_FEEDBACK, C_FEEDBACK]
    assert all(arm.total == 2 for arm in smoke_arms.values())
    assert len(boundary.calls) == study.plan()["smoke_max_model_calls"] == 8
    assert study.complete(smoke_only=True) is True and study.complete() is False
    with pytest.raises(PermissionError, match="mt-triggers"):
        study.run()
    assert len(boundary.calls) == 8

    arms = study.run(allow_paid=True)
    assert study.complete() is True
    assert [name for name in boundary.launched if not name.startswith("mt-smoke-")] == [
        f"mt-{stage}" for stage in chain]
    assert list(arms) == [A_INITIAL, B_NO_FEEDBACK, C_FEEDBACK]
    assert boundary.detached == ["mt-smoke-B-no-feedback", "mt-smoke-C-feedback",
                                 "mt-B-no-feedback", "mt-C-feedback"]
    assert [arm.protocol for arm in arms.values()] == ["multi_turn_initial", "multi_turn_revision",
                                                        "multi_turn_revision"]
    assert all(arm.model == MODEL and arm.cache is False for arm in arms.values())

    rows = {label: {row["candidate_id"]: row for row in arm.get_records()}
            for label, arm in arms.items()}
    for label, by_id in rows.items():
        assert len(by_id) == 6 and {row["split"] for row in by_id.values()} == {"train", "test"}
        starved_row = by_id[starved_id]
        assert starved_row["failed"] and starved_row["blame"] == "model" and starved_row["calls"] == []
        measured = [row for cid, row in by_id.items() if cid != starved_id]
        assert all(not row["failed"] and len(row["calls"]) == 1 for row in measured)
    assert all(WITHHELD in row["calls"][0]["prompt"]
               for cid, row in rows[B_NO_FEEDBACK].items() if cid != starved_id)
    assert all(WITHHELD not in row["calls"][0]["prompt"]
               for cid, row in rows[C_FEEDBACK].items() if cid != starved_id)
    replay = {row["candidate_id"]: row for row in Run.attach("mt-A-replay").get_records()}
    assert replay[starved_id]["result"] is None and replay[starved_id]["calls"] == []
    assert (Path("runs") / "mt-A-replay" / "source-bundle.json").is_file()

    spent = len(boundary.calls)
    assert spent == (2 + 6) * 4 - 3 * 1  # the starved candidate reaches only the input search
    again = study.run(allow_paid=False)
    assert len(boundary.calls) == spent and list(again) == list(arms)

    exec(compile(CELLS.CODE_ANALYSIS, "analysis cell", "exec"), {"multi_turn_arms": arms})
    summary = json.loads((arms[A_INITIAL].directory / "multi_turn_analysis.json").read_text())
    attack = summary["primary_contrasts"]["C_minus_B_attack_catch"]
    assert summary["primary_split"] == "test" and attack["candidate_denominator_each_arm"] == 1
    assert attack["left_rate"] == attack["right_rate"] == 1.0
    assert starved_id in summary["excluded_candidates"]
    assert {"C_minus_B_honest_fpr", "C_minus_A_attack_catch", "B_minus_A_attack_catch"} <= set(
        summary["primary_contrasts"])
    assert "test_without_pilot_exposed_tasks" in summary["sensitivity"]


def test_the_bcb_chain_adds_a_delete_only_arm_that_never_rewrites_a_test(tmp_path, monkeypatch):
    shutil.copyfile(REPO_ROOT / "data/bcb_smoke2.json", "bcb.json")
    data = Dataset.load("bcb.json")
    boundary = Boundary(data)
    boundary.install(monkeypatch)
    study = MultiTurnStudy(reference_arm=_reference("bcb.json"), prefix="mtb", model=MODEL)

    arms = study.run(allow_paid=True)
    assert list(arms) == [A_INITIAL, B_NO_FEEDBACK, C_FEEDBACK, D_DELETE_ONLY]
    assert boundary.detached[-3:] == ["mtb-B-no-feedback", "mtb-C-feedback", "mtb-D-delete-only"]
    assert arms[D_DELETE_ONLY].protocol == "multi_turn_delete_only"
    suites = {row["candidate_id"]: row["tests_src"] for row in arms[A_INITIAL].get_records()}
    for row in arms[D_DELETE_ONLY].get_records():
        assert not row["failed"] and row["selection"] == RETAINED
        assert row["removed_test_ids"] == [test["name"] for test in TESTS[5:]]
        original = exact_tests(suites[row["candidate_id"]])
        kept = exact_tests(row["tests_src"])
        assert list(kept) == RETAINED and all(kept[n][2] == original[n][2] for n in RETAINED)
    assert RETAINED in boundary.grids


def test_a_delete_only_selection_is_parsed_strictly_and_cut_byte_for_byte():
    source = "import math\n\n" + "\n".join(test["source"] for test in TESTS[:3])
    cut, original = subset_source(source, ["test_value_0", "test_value_2"])
    assert "test_value_1" not in cut and "import math" in cut
    assert set(original) == {"test_value_0", "test_value_1", "test_value_2"}
    for bad in (["test_value_0", "test_value_0"], ["test_value_9"]):
        with pytest.raises(ValueError, match="duplicate or unavailable"):
            subset_source(source, bad)
    assert parse_selection(json.dumps({"rationale": "none hold", "retain_test_ids": []})) == (
        [], "none hold")
    for bad in ({"rationale": "", "retain_test_ids": []},
                {"rationale": "x", "retain_test_ids": [], "tests": []}):
        with pytest.raises(ValueError):
            parse_selection(json.dumps(bad))


def test_a_fresh_interpreter_registers_every_multi_turn_protocol():
    names = subprocess.run(
        [sys.executable, "-c", "import pipeline.protocols as p; print(sorted(p.REGISTRY))"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
    for protocol in ("multi_turn_initial", "multi_turn_replay", "multi_turn_revision",
                     "multi_turn_delete_only", "second_revision", "unit_testing"):
        assert f"'{protocol}'" in names


def test_without_its_runs_the_section_spends_nothing_and_raises_nothing(tmp_path, monkeypatch, capsys):
    import pandas as pd
    boundary = Boundary(_mini_apps(tmp_path))
    boundary.install(monkeypatch)
    namespace = {"mt_study": MultiTurnStudy(reference_arm=_reference("mini.json"), prefix="mt",
                                            model=MODEL),
                 "MT_PREFIX": "mt", "MT_ALLOW_PAID_SMOKE": False, "MT_ALLOW_PAID_FULL": False,
                 "pd": pd, "display": print}
    for source in (CELLS.CODE_SMOKE, CELLS.CODE_FULL, CELLS.CODE_COVERAGE, CELLS.CODE_ANALYSIS):
        exec(compile(source, "section cell", "exec"), namespace)
    assert namespace["multi_turn_arms"] == {}
    assert boundary.calls == [] and boundary.launched == []
    assert not list(Path("runs").glob("mt-*/records.jsonl"))
    printed = capsys.readouterr().out
    assert "smoke chain not on this machine" in printed and "analysis skipped" in printed


def _team_pools(generator: str) -> list[str]:
    return re.findall(r'^    "(\w+)": \{"pool"', generator, re.MULTILINE)


def _generate(directory: Path, generator: str, pool: str, notebook: str) -> list[tuple[str, str]]:
    (directory / "build_results.py").write_text(generator, encoding="utf-8")
    shutil.copyfile(NOTEBOOKS / "multi_turn_cells.py", directory / "multi_turn_cells.py")
    subprocess.run([sys.executable, "build_results.py", pool], cwd=directory, check=True,
                   capture_output=True)
    return [(c["cell_type"], "".join(c["source"]))
            for c in json.loads((directory / notebook).read_text(encoding="utf-8"))["cells"]]


def _notebook_of(generator: str, pool: str) -> str:
    return re.search(rf'^    "{pool}": \{{"pool": "{pool}", "notebook": "([^"]+)"', generator,
                     re.MULTILINE).group(1)


def test_the_team_generator_only_appends_the_section_and_only_where_the_study_runs(tmp_path):
    generator = (NOTEBOOKS / "build_results.py").read_text(encoding="utf-8")
    assert generator.count(HOOK) == 1
    pools = _team_pools(generator)
    assert pools
    for pool in pools:
        notebook = _notebook_of(generator, pool)
        (tmp_path / f"{pool}-hook").mkdir(); (tmp_path / f"{pool}-team").mkdir()
        with_hook = _generate(tmp_path / f"{pool}-hook", generator, pool, notebook)
        team_only = _generate(tmp_path / f"{pool}-team", generator.replace(HOOK, ""), pool, notebook)
        assert with_hook[:len(team_only)] == team_only, f"{pool}: a team cell changed"
        added = with_hook[len(team_only):]
        if pool in CELLS.MULTI_TURN_POOLS:
            assert len(added) == len(CELLS.section_cells())
            assert added[0][1].startswith(CELLS.SECTION_MARKER)
        else:
            assert added == [], f"{pool}: the section leaked into a pool the study does not run on"


def test_every_committed_notebook_with_the_section_is_what_the_generator_writes(tmp_path):
    generator = (NOTEBOOKS / "build_results.py").read_text(encoding="utf-8")
    checked = 0
    for pool in set(_team_pools(generator)) & CELLS.MULTI_TURN_POOLS:
        notebook = _notebook_of(generator, pool)
        committed = NOTEBOOKS / notebook
        if not committed.exists():
            continue
        (tmp_path / pool).mkdir()
        expected = _generate(tmp_path / pool, generator, pool, notebook)
        actual = [(c["cell_type"], "".join(c["source"]))
                  for c in json.loads(committed.read_text(encoding="utf-8"))["cells"]]
        assert actual == expected, f"{notebook} is stale: rebuild it, or splice the section in"
        checked += 1
    assert checked >= 1


@pytest.mark.parametrize("recovery", ["retry", "accept"])
def test_an_arm_a_infra_failure_stops_the_chain_before_it_is_frozen_in(tmp_path, monkeypatch, recovery):
    data = _mini_apps(tmp_path)
    victim = next(c.candidate_id for t, c in data.candidates() if t.task_id == data.train[0].task_id)
    boundary = Boundary(data, crash_once=victim)
    boundary.install(monkeypatch)
    study = MultiTurnStudy(reference_arm=_reference("mini.json"), prefix="mt", model=MODEL)

    with pytest.raises(UnretriedInfraFailures, match="mt-A-traceable"):
        study.run(allow_paid=True)
    assert not (Path("runs") / "mt-A-replay").exists()

    records = Path("runs/mt-A-traceable/records.jsonl")
    if recovery == "retry":
        rows = [json.loads(line) for line in records.read_text().splitlines()]
        records.write_text("".join(json.dumps(row) + "\n" for row in rows
                                   if not (row["failed"] and row["blame"] == "infra")))
        arms = study.run(allow_paid=True)
        assert not any(row["failed"] for row in arms[A_INITIAL].get_records())
    else:
        arms = study.run(allow_paid=True, accept_infra_failures=True)
        a_row = {row["candidate_id"]: row for row in arms[A_INITIAL].get_records()}[victim]
        assert a_row["failed"] and a_row["blame"] == "infra"
        for label in (B_NO_FEEDBACK, C_FEEDBACK):
            row = {r["candidate_id"]: r for r in arms[label].get_records()}[victim]
            assert row["failed"] and row["blame"] == "infra" and row["calls"] == []
        assert list(study.run(allow_paid=False)) == list(arms)
    assert study.complete() is True
