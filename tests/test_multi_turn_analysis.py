"""The multi-turn notebook's analysis cell, executed as committed against saved-record artifacts.

The cell is read out of `notebooks/multi_turn_uniform400.ipynb` — the generated notebook a reader
runs — so these tests cannot pass against a copy that drifted from it.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from pipeline.data import Dataset

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "multi_turn_uniform400.ipynb"
MARKER = "# strict complete/error-free paired analysis (zero API calls)"
LABELS = ["A initial", "B no feedback", "C feedback"]
ANALYSIS_FILE = "multi_turn_analysis.json"


def _cell() -> str:
    cells = ["".join(cell["source"]) for cell in json.loads(NOTEBOOK.read_text())["cells"]]
    [cell] = [cell for cell in cells if cell.startswith(MARKER)]
    return cell


class ArtifactArm:
    """What the cell reads off an arm: its dataset, records and directory, and nothing else."""

    def __init__(self, label: str, data_path: Path, rows: list[dict], root: Path):
        self.run_name = label
        self.data_path = str(data_path)
        self.data = Dataset.load(data_path)
        self.directory = root / label.replace(" ", "-")
        self.records_path = self.directory / "records.jsonl"
        self.directory.mkdir(parents=True)
        self.records_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def get_records(self):
        return [json.loads(line) for line in self.records_path.read_text(encoding="utf-8").splitlines()]


def _row(candidate_id, caught):
    return {"candidate_id": candidate_id, "failed": False, "blame": None, "reason": None,
            "complete": True, "n_pairs_expected": 2, "n_pairs_run": 2,
            "n_pairs_by_outcome": {"pass": 1, "catch": 1} if caught else {"pass": 2},
            "catches": ["test_1"] if caught else []}


def _fixture(tmp_path):
    payload = json.loads((ROOT / "data" / "apps_uniform400.json").read_text(encoding="utf-8"))
    payload["tasks"] = payload["tasks"][:2]
    payload["split"] = {"train": [], "test": sorted(task["task_id"] for task in payload["tasks"])}
    data_path = tmp_path / "tiny.json"
    data_path.write_text(json.dumps(payload), encoding="utf-8")
    data = Dataset.load(data_path)
    honest = [c.candidate_id for _, c in data.candidates() if not c.is_attack]
    rows = [_row(c.candidate_id, c.is_attack) for _, c in data.candidates()]
    return data_path, data, honest, rows


def _execute(tmp_path, data_path, rows_by_arm):
    arms = {label: ArtifactArm(label, data_path, rows_by_arm[label], tmp_path / "runs")
            for label in LABELS}
    before = {label: hashlib.sha256(arm.records_path.read_bytes()).hexdigest()
              for label, arm in arms.items()}
    exec(compile(_cell(), "analysis cell", "exec"), {"multi_turn_arms": arms})
    assert before == {label: hashlib.sha256(arm.records_path.read_bytes()).hexdigest()
                      for label, arm in arms.items()}, "the analysis rewrote a measured record"
    return json.loads((arms["A initial"].directory / ANALYSIS_FILE).read_text())


def _bootstrap(task_by_candidate, records):
    """The cell's own bootstrap function, compiled out of the notebook, not a copy of it."""
    function = next(node for node in ast.parse(_cell()).body
                    if isinstance(node, ast.FunctionDef) and node.name == "mt_bootstrap_differences")
    namespace = {"np": np, "mt_task_by_candidate": task_by_candidate, "mt_records": records,
                 "MT_BOOTSTRAP_SEED": 300, "MT_BOOTSTRAP_DRAWS": 10000}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "bootstrap", "exec"), namespace)
    return namespace["mt_bootstrap_differences"]


@pytest.mark.parametrize("defect", ["failed", "partial", "prop_error", "candidate_crash",
                                    "abstained", "missing", "missing_pair_outcomes",
                                    "invalid_pair_outcomes", "catch_outcome_mismatch",
                                    "missing_pair_metadata"])
def test_an_unmeasured_grid_is_excluded_never_a_clean_negative(tmp_path, defect):
    data_path, _data, honest, rows = _fixture(tmp_path)
    rows_by_arm = {label: json.loads(json.dumps(rows)) for label in LABELS}
    target = next(row for row in rows_by_arm["C feedback"] if row["candidate_id"] == honest[0])
    if defect == "failed":
        target.update(failed=True, blame="infra", reason="synthetic failure")
    elif defect == "partial":
        target.update(complete=False, n_pairs_run=1, catches=["test_1"], n_pairs_by_outcome={"catch": 1})
    elif defect in ("prop_error", "candidate_crash"):
        target.update(catches=["test_1"], n_pairs_by_outcome={"catch": 1, defect: 1})
    elif defect == "abstained":
        target["abstained"] = True
    elif defect == "missing":
        rows_by_arm["C feedback"].remove(target)
    elif defect == "missing_pair_outcomes":
        target["n_pairs_by_outcome"] = None
    elif defect == "invalid_pair_outcomes":
        target["n_pairs_by_outcome"] = {"unrecognized": 2}
    elif defect == "catch_outcome_mismatch":
        target["catches"] = ["test_1"]
    elif defect == "missing_pair_metadata":
        del target["n_pairs_by_outcome"]
    summary = _execute(tmp_path, data_path, rows_by_arm)
    matched = summary["by_split"]["test"]["common_ABC_grid"]["matched_rates"]["A"]
    assert (matched["honest_candidate_denominator"], matched["attack_candidate_denominator"]) == (1, 2)
    assert (matched["honest_fpr"], matched["attack_catch_rate"]) == (0, 1)
    honest_result = summary["primary_contrasts"]["C_minus_B_honest_fpr"]
    assert honest_result["candidate_denominator_each_arm"] == 1
    assert honest_result["bootstrap"]["interval_status"] == "fewer_than_two_task_clusters"
    assert sum(honest_result["excluded_candidates_by_reason"].values()) == 1
    assert honest[0] in summary["excluded_candidates"]
    attack_result = summary["primary_contrasts"]["C_minus_B_attack_catch"]
    assert attack_result["candidate_denominator_each_arm"] == 2
    assert attack_result["bootstrap"]["percentile_95_ci"] == [0.0, 0.0]
    assert not any(key.startswith("D_") for key in summary["primary_contrasts"])


def test_a_duplicate_record_raises_instead_of_entering_a_denominator(tmp_path):
    data_path, _data, _honest, rows = _fixture(tmp_path)
    rows_by_arm = {label: json.loads(json.dumps(rows)) for label in LABELS}
    rows_by_arm["C feedback"].append(dict(rows[0]))
    with pytest.raises(ValueError, match="duplicate records"):
        _execute(tmp_path, data_path, rows_by_arm)


def test_the_primary_contrast_is_test_only_when_the_effect_exists_only_on_train(tmp_path):
    data_path, data, _honest, rows = _fixture(tmp_path)
    payload = json.loads(data_path.read_text())
    train_id, test_id = [task.task_id for task in data.tasks]
    payload["split"] = {"train": [train_id], "test": [test_id]}
    data_path.write_text(json.dumps(payload), encoding="utf-8")
    rows_by_arm = {label: json.loads(json.dumps(rows)) for label in LABELS}
    train_honest = next(c.candidate_id for t, c in data.candidates()
                        if t.task_id == train_id and not c.is_attack)
    target = next(row for row in rows_by_arm["C feedback"] if row["candidate_id"] == train_honest)
    target.update(catches=["test_1"], n_pairs_by_outcome={"pass": 1, "catch": 1})
    summary = _execute(tmp_path, data_path, rows_by_arm)
    assert summary["primary_split"] == "test"
    assert summary["primary_contrasts"]["C_minus_B_honest_fpr"]["difference"] == 0.0
    assert summary["by_split"]["train"]["contrasts"]["C_minus_B_honest_fpr"]["difference"] == 1.0
    assert "pooled" not in summary["by_split"]


def test_recomputing_from_the_same_records_is_free_and_a_changed_input_refuses(tmp_path):
    data_path, _data, honest, rows = _fixture(tmp_path)
    rows_by_arm = {label: json.loads(json.dumps(rows)) for label in LABELS}
    first = _execute(tmp_path / "one", data_path, rows_by_arm)
    second = _execute(tmp_path / "two", data_path, rows_by_arm)
    assert first == second and first["schema_version"] == 1
    arms = {label: ArtifactArm(label, data_path, rows_by_arm[label], tmp_path / "three")
            for label in LABELS}
    (arms["A initial"].directory / ANALYSIS_FILE).write_text('{"stale": true}\n')
    with pytest.raises(ValueError, match="derived analysis differs"):
        exec(compile(_cell(), "analysis cell", "exec"), {"multi_turn_arms": arms})


@pytest.mark.parametrize("empty_cluster", [False, True])
def test_the_chunked_bootstrap_matches_the_one_draw_at_a_time_reference(empty_cluster):
    task_by_candidate = {"c0": "t0", "c1": "t0", "c2": "t1", "c3": "t2", "c4": "t2", "c5": "t2"}
    left, right = {"c0", "c3", "c5"}, {"c1", "c2", "c3"}
    records = {"left": {cid: {"catches": ["t"] if cid in left else []} for cid in task_by_candidate},
               "right": {cid: {"catches": ["t"] if cid in right else []} for cid in task_by_candidate}}
    candidates = [(cid, "honest") for cid in task_by_candidate]
    task_ids = sorted(set(task_by_candidate.values())) + (["t_empty"] if empty_cluster else [])
    actual, undefined = _bootstrap(task_by_candidate, records)(task_ids, candidates, "left", "right")

    rng = np.random.default_rng(300)
    expected, expected_undefined = [], 0
    for _ in range(10000):
        sampled = rng.choice(task_ids, size=len(task_ids), replace=True).tolist()
        members = [cid for task in sampled for cid, _ in candidates if task_by_candidate[cid] == task]
        if not members:
            expected_undefined += 1
            continue
        expected.append(sum(bool(records["left"][c]["catches"]) for c in members) / len(members)
                        - sum(bool(records["right"][c]["catches"]) for c in members) / len(members))
    np.testing.assert_array_equal(actual, expected)
    assert undefined == expected_undefined


@pytest.mark.parametrize("task_ids", [[], ["single"]])
def test_no_interval_is_claimed_below_two_task_clusters(task_ids):
    candidates = [("c0", "honest")] if task_ids else []
    mapping = {"c0": "single"} if task_ids else {}
    records = {"left": {"c0": {"catches": ["t"]}}, "right": {"c0": {"catches": []}}}
    assert _bootstrap(mapping, records)(task_ids, candidates, "left", "right") == ([], 0)
