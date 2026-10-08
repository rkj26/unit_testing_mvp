"""The multi-turn chain end to end, through the same `Run` path every team arm takes.

Fakes sit at the process boundary only, as `tests/AGENTS.md` asks: the provider (`resolve`,
`complete_sync`), Docker (`run_raw` and the image check) and tmux (`Run.run` runs the subprocess's
own `write_config` + `execute` in-process, because a tmux subprocess would not see these patches).
Everything between — prompts, parsers, records, the replay, the bundle, `SecondRevision`'s
prompt and verdict, the delete-only cut, the notebook's analysis cell — is the real code.
"""

from __future__ import annotations

import json
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
                                           MultiTurnStudy)
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
ANALYSIS_MARKER = "# strict complete/error-free paired analysis (zero API calls)"


class Boundary:
    """The provider, Docker and tmux, scripted; every call they receive is kept for assertions."""

    def __init__(self, data: Dataset, starved: str | None = None) -> None:
        self.attack_code = {candidate.code for _, candidate in data.candidates() if candidate.is_attack}
        self.starved_code = next((candidate.code for _, candidate in data.candidates()
                                  if candidate.candidate_id == starved), None)
        self.inputs = INPUTS[data.io_mode]
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


def _analysis_cell() -> str:
    notebook = json.loads((REPO_ROOT / "notebooks/multi_turn_uniform400.ipynb").read_text())
    [cell] = ["".join(cell["source"]) for cell in notebook["cells"]
              if "".join(cell["source"]).startswith(ANALYSIS_MARKER)]
    return cell


def test_the_apps_chain_runs_every_arm_through_the_team_launcher(tmp_path, monkeypatch):
    document = build(REPO_ROOT / "apps_pool_hard10.json", REPO_ROOT / "splits/smoke_3.json",
                     "apps", "mini")
    (tmp_path / "mini.json").write_text(json.dumps(document), encoding="utf-8")
    data = Dataset.load("mini.json")
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

    chain = ["triggers", "A-traceable", "A-replay", "B-no-feedback", "C-feedback"]
    smoke_arms = study.run(allow_paid=True, smoke_only=True)
    assert boundary.launched == [f"mt-smoke-{stage}" for stage in chain]
    assert list(smoke_arms) == [A_INITIAL, B_NO_FEEDBACK, C_FEEDBACK]
    assert all(arm.total == 2 for arm in smoke_arms.values())
    assert len(boundary.calls) == study.plan()["smoke_max_model_calls"] == 8
    with pytest.raises(PermissionError, match="mt-triggers"):
        study.run()
    assert len(boundary.calls) == 8

    arms = study.run(allow_paid=True)
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

    exec(compile(_analysis_cell(), "analysis cell", "exec"), {"multi_turn_arms": arms})
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


def test_the_committed_multi_turn_notebooks_are_what_the_generator_writes(tmp_path):
    shutil.copyfile(REPO_ROOT / "notebooks/build_multi_turn.py", tmp_path / "build_multi_turn.py")
    for pool, notebook in (("u400", "multi_turn_uniform400.ipynb"), ("bcbas", "multi_turn_bcbas.ipynb")):
        subprocess.run([sys.executable, "build_multi_turn.py", pool], cwd=tmp_path, check=True,
                       capture_output=True)
        assert ((tmp_path / notebook).read_text(encoding="utf-8")
                == (REPO_ROOT / "notebooks" / notebook).read_text(encoding="utf-8"))
