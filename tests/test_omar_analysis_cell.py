"""Execute the exact published notebook analysis against isolated real record artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pipeline.data import Dataset


ROOT = Path(__file__).resolve().parents[1]
DATASET_NAME = "bcbas.json"
NOTEBOOK_NAME = "results_bcbas.ipynb"
MARKER = "# Omar strict complete/error-free paired analysis (zero API calls)"


class ArtifactArm:
    def __init__(self, label: str, data_path: Path, rows: list[dict], directory: Path):
        self.run_name = "tiny-A-traceable" if label == "A initial" else label
        self.data_path = str(data_path)
        self.data = Dataset.load(data_path)
        self.record_path = directory / label / "records.jsonl"
        self.record_path.parent.mkdir(parents=True)
        self.record_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def get_records(self):
        return [json.loads(line) for line in self.record_path.read_text(encoding="utf-8").splitlines()]


def _row(candidate_id, caught):
    return {"candidate_id": candidate_id, "failed": False, "blame": None, "reason": None,
            "complete": True,
            "n_pairs_expected": 2, "n_pairs_run": 2,
            "n_pairs_by_outcome": {"pass": 1, "catch": 1} if caught else {"pass": 2},
            "catches": ["test_1"] if caught else []}


def _fixture(tmp_path):
    # Shared dataset schema/runtime metadata, never historical population/helpers.
    source = ROOT / "data" / DATASET_NAME
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["tasks"] = payload["tasks"][:2]
    task_ids = {task["task_id"] for task in payload["tasks"]}
    payload["split"] = {"train": [], "test": sorted(task_ids)}
    data_path = tmp_path / "tiny.json"  # backend deliberately absent from filename
    data_path.write_text(json.dumps(payload), encoding="utf-8")
    data = Dataset.load(data_path)
    honest = [candidate.candidate_id for _, candidate in data.candidates() if not candidate.is_attack]
    attack = [candidate.candidate_id for _, candidate in data.candidates() if candidate.is_attack]
    labels = ["A initial", "B no feedback", "C feedback"]
    if data.backend == "bcb":
        labels.append("D delete only")
    rows = [_row(candidate.candidate_id, candidate.is_attack) for _, candidate in data.candidates()]
    return data_path, data, honest, attack, labels, rows


def _execute(tmp_path, monkeypatch, labels, data_path, rows_by_arm):
    monkeypatch.chdir(tmp_path)
    arms = {label: ArtifactArm(label, data_path, rows_by_arm[label], tmp_path / "records")
            for label in labels}
    before = {label: hashlib.sha256(arm.record_path.read_bytes()).hexdigest()
              for label, arm in arms.items()}
    doc = (ROOT / "notebooks" / "OMAR_ANALYSIS_CELL.md").read_text(encoding="utf-8")
    code = doc.split("```python\n", 1)[1].split("\n```", 1)[0]
    exec(compile(code, "OMAR_ANALYSIS_CELL", "exec"), {"omar_arms": arms})
    assert before == {label: hashlib.sha256(arm.record_path.read_bytes()).hexdigest()
                      for label, arm in arms.items()}
    return json.loads((tmp_path / "runs" / "tiny-coordinator" / "analysis-v2.json").read_text())


@pytest.mark.parametrize("defect", ["failed", "partial", "prop_error", "candidate_crash",
                                  "abstained", "missing", "missing_pair_outcomes",
                                  "invalid_pair_outcomes", "catch_outcome_mismatch",
                                  "missing_pair_metadata"])
def test_strict_cell_excludes_unmeasured_grids_without_changing_records(
    tmp_path, monkeypatch, defect,
):
    data_path, data, honest, attack, labels, rows = _fixture(tmp_path)
    rows_by_arm = {label: json.loads(json.dumps(rows)) for label in labels}
    target = next(row for row in rows_by_arm["C feedback"] if row["candidate_id"] == honest[0])
    if defect == "failed":
        target.update(failed=True, blame="infra", reason="synthetic failure")
    elif defect == "partial":
        target.update(complete=False, n_pairs_run=1, catches=["test_1"],
                      n_pairs_by_outcome={"catch": 1})
    elif defect in ("prop_error", "candidate_crash"):
        target.update(catches=["test_1"],
                      n_pairs_by_outcome={"catch": 1, defect: 1})
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
    summary = _execute(tmp_path, monkeypatch, labels, data_path, rows_by_arm)
    matched = summary["by_split"]["test"]["common_ABC_grid"]["matched_rates"]["A"]
    assert matched["honest_candidate_denominator"] == 1
    assert matched["attack_candidate_denominator"] == 2
    assert matched["honest_fpr"] == 0
    assert matched["attack_catch_rate"] == 1
    honest_result = summary["primary_contrasts"]["C_minus_B_honest_fpr"]
    assert honest_result["candidate_denominator_each_arm"] == 1
    assert honest_result["task_denominator"] == 1
    assert honest_result["bootstrap"]["percentile_95_ci"] is None
    assert honest_result["bootstrap"]["interval_status"] == "fewer_than_two_task_clusters"
    assert sum(honest_result["excluded_candidates_by_reason"].values()) == 1
    assert honest[0] in summary["excluded_candidates"]
    attack_result = summary["primary_contrasts"]["C_minus_B_attack_catch"]
    assert attack_result["candidate_denominator_each_arm"] == 2
    assert attack_result["bootstrap"]["draws"] == 10000
    assert attack_result["bootstrap"]["percentile_95_ci"] == [0.0, 0.0]
    if data.backend == "bcb":
        assert summary["primary_contrasts"]["D_minus_A_honest_fpr"]["candidate_denominator_each_arm"] == 2
    else:
        assert not any(key.startswith("D_") for key in summary["primary_contrasts"])


def test_duplicate_artifact_records_raise_instead_of_entering_denominator(tmp_path, monkeypatch):
    data_path, _data, _honest, _attack, labels, rows = _fixture(tmp_path)
    rows_by_arm = {label: json.loads(json.dumps(rows)) for label in labels}
    rows_by_arm["C feedback"].append(dict(rows[0]))
    with pytest.raises(ValueError, match="duplicate records"):
        _execute(tmp_path, monkeypatch, labels, data_path, rows_by_arm)


def test_generated_continuation_embeds_the_authoritative_analysis_without_extra_code_cell():
    notebook = json.loads((ROOT / "notebooks" / NOTEBOOK_NAME).read_text(encoding="utf-8"))
    initial = [cell for cell in notebook["cells"] if "omar_initial = omar.run()" in "".join(cell["source"])]
    continuation = [cell for cell in notebook["cells"]
                    if "omar_arms = omar.continue_run()" in "".join(cell["source"])]
    assert len(initial) == len(continuation) == 1
    doc = (ROOT / "notebooks" / "OMAR_ANALYSIS_CELL.md").read_text(encoding="utf-8")
    code = doc.split("```python\n", 1)[1].split("\n```", 1)[0]
    source = "".join(continuation[0]["source"])
    assert code in source and source.count(MARKER) == 1
    assert sum(MARKER in "".join(cell["source"]) for cell in notebook["cells"]) == 1
    initial_source = "".join(initial[0]["source"])
    assert "OMAR_ALLOW_PAID = False" in initial_source
    assert "OMAR_MAX_MODEL_CALLS = 0" in initial_source
    assert "allow_paid=OMAR_ALLOW_PAID" in initial_source
    assert "max_model_calls=OMAR_MAX_MODEL_CALLS" in initial_source
    assert "OMAR_EXPECTED_MAX_MODEL_CALLS" in initial_source
    compile(initial_source, "initial", "exec")
    compile(source, "continuation", "exec")


def _bootstrap_namespace(task_by_candidate, records, draws=10000):
    import ast

    import numpy as np

    doc = (ROOT / "notebooks" / "OMAR_ANALYSIS_CELL.md").read_text(encoding="utf-8")
    code = doc.split("```python\n", 1)[1].split("\n```", 1)[0]
    tree = ast.parse(code)
    # Compile the actual notebook-owned helper, not a copied implementation.
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "om_bootstrap_differences")
    namespace = {"np": np, "om_task_by_candidate": task_by_candidate,
                 "om_records": records, "OMAR_BOOTSTRAP_SEED": 300,
                 "OMAR_BOOTSTRAP_DRAWS": draws}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "OMAR bootstrap", "exec"), namespace)
    return namespace


@pytest.mark.parametrize("empty_cluster", [False, True])
def test_chunked_bootstrap_preserves_every_seeded_paired_draw_and_interval(empty_cluster):
    import numpy as np

    # Unequal candidate weights and different catches test the actual ratio estimand.
    task_by_candidate = {"c0": "t0", "c1": "t0", "c2": "t1",
                         "c3": "t2", "c4": "t2", "c5": "t2"}
    left_catches = {"c0", "c3", "c5"}
    right_catches = {"c1", "c2", "c3"}
    records = {
        "left": {cid: {"catches": ["test"] if cid in left_catches else []}
                 for cid in task_by_candidate},
        "right": {cid: {"catches": ["test"] if cid in right_catches else []}
                  for cid in task_by_candidate},
    }
    candidates = [(cid, "honest") for cid in task_by_candidate]
    task_ids = sorted(set(task_by_candidate.values()))
    if empty_cluster:
        task_ids.append("t_empty")  # verifies undefined samples stay explicit
    namespace = _bootstrap_namespace(task_by_candidate, records)
    actual, undefined = namespace["om_bootstrap_differences"](task_ids, candidates, "left", "right")

    # Simple reference is the prior notebook algorithm: one draw at a time and
    # each sampled task carries all its candidate observations for both arms.
    rng = np.random.default_rng(300)
    expected = []
    expected_undefined = 0
    for _ in range(10000):
        sampled = rng.choice(task_ids, size=len(task_ids), replace=True).tolist()
        cluster_candidates = [cid for task_id in sampled
                              for cid, _kind in candidates if task_by_candidate[cid] == task_id]
        if not cluster_candidates:
            expected_undefined += 1
        else:
            left = sum(bool(records["left"][cid]["catches"]) for cid in cluster_candidates)
            right = sum(bool(records["right"][cid]["catches"]) for cid in cluster_candidates)
            expected.append(left / len(cluster_candidates) - right / len(cluster_candidates))
    np.testing.assert_array_equal(actual, expected)
    assert undefined == expected_undefined
    np.testing.assert_array_equal(np.quantile(actual, [0.025, 0.975]),
                                  np.quantile(expected, [0.025, 0.975]))


@pytest.mark.parametrize("task_ids", [[], ["single"]])
def test_bootstrap_does_not_claim_uncertainty_without_two_task_clusters(task_ids):
    candidates = [("c0", "honest")] if task_ids else []
    mapping = {"c0": "single"} if task_ids else {}
    records = {"left": {"c0": {"catches": ["test"]}},
               "right": {"c0": {"catches": []}}}
    namespace = _bootstrap_namespace(mapping, records)
    assert namespace["om_bootstrap_differences"](task_ids, candidates, "left", "right") == ([], 0)


def test_453_task_10000_draw_bootstrap_is_bounded_and_reports_diagnostic():
    import time

    task_ids = [f"task_{i:04d}" for i in range(453)]
    mapping = {f"candidate_{i}": task_id for i, task_id in enumerate(task_ids)}
    candidates = [(cid, "honest") for cid in mapping]
    records = {
        "left": {cid: {"catches": ["test"] if i % 3 == 0 else []}
                 for i, cid in enumerate(mapping)},
        "right": {cid: {"catches": ["test"] if i % 5 == 0 else []}
                  for i, cid in enumerate(mapping)},
    }
    namespace = _bootstrap_namespace(mapping, records)
    started = time.perf_counter()
    draws, undefined = namespace["om_bootstrap_differences"](task_ids, candidates, "left", "right")
    elapsed = time.perf_counter() - started
    print(f"453-task/10000-draw paired bootstrap: {elapsed:.3f}s; {len(draws)} draws")
    assert len(draws) == 10000 and undefined == 0
    assert elapsed < 10, f"full shared-pool bootstrap took {elapsed:.3f}s (limit 10s)"


def test_primary_is_test_only_when_the_effect_exists_only_on_train(tmp_path, monkeypatch):
    data_path, data, _honest, _attack, labels, rows = _fixture(tmp_path)
    payload = json.loads(data_path.read_text())
    train_id, test_id = [task.task_id for task in data.tasks]
    payload["split"] = {"train": [train_id], "test": [test_id]}
    data_path.write_text(json.dumps(payload), encoding="utf-8")
    rows_by_arm = {label: json.loads(json.dumps(rows)) for label in labels}
    train_honest = next(candidate.candidate_id for task, candidate in data.candidates()
                        if task.task_id == train_id and not candidate.is_attack)
    target = next(row for row in rows_by_arm["C feedback"] if row["candidate_id"] == train_honest)
    target.update(catches=["test_1"], n_pairs_by_outcome={"pass": 1, "catch": 1})
    summary = _execute(tmp_path, monkeypatch, labels, data_path, rows_by_arm)
    assert summary["primary_split"] == "test"
    assert summary["primary_contrasts"]["C_minus_B_honest_fpr"]["difference"] == 0.0
    assert summary["by_split"]["train"]["contrasts"]["C_minus_B_honest_fpr"]["difference"] == 1.0
    assert summary["by_split"]["test"]["contrasts"]["C_minus_B_honest_fpr"]["difference"] == 0.0
    for split, task_id in (("train", train_id), ("test", test_id)):
        result = summary["by_split"][split]["contrasts"]["C_minus_B_honest_fpr"]
        assert result["split"] == split
        assert result["eligible_task_ids"] == [task_id]
        assert result["candidate_denominator_each_arm"] == 1
    assert "pooled" not in summary["by_split"]


def test_generic_base_infra_failure_without_pair_metadata_is_counted_and_excluded(
    tmp_path, monkeypatch,
):
    from pipeline.protocols import UnitTesting

    data_path, data, honest, _attack, labels, rows = _fixture(tmp_path)
    task, candidate = next((task, candidate) for task, candidate in data.candidates()
                           if candidate.candidate_id == honest[0])
    run = UnitTesting(run_name="generic-failure", data=str(data_path), model="mockllm/failure",
                      triggers="not-used", n_tests=2)
    def broken_score(_task, _candidate):
        raise OSError("synthetic infrastructure failure")
    monkeypatch.setattr(run, "score", broken_score)
    failure = run._record_for(task, candidate)
    assert failure["failed"] is True and failure["blame"] == "infra" and failure["calls"] == []
    assert "n_pairs_run" not in failure and "catches" not in failure
    rows_by_arm = {label: json.loads(json.dumps(rows)) for label in labels}
    rows_by_arm["C feedback"] = [failure if row["candidate_id"] == honest[0] else row
                                 for row in rows_by_arm["C feedback"]]
    summary = _execute(tmp_path, monkeypatch, labels, data_path, rows_by_arm)
    status = summary["by_split"]["test"]["arm_record_status"]["C feedback"]
    assert status["failed_records"] == 1
    assert status["failures_by_blame"] == {"infra": 1}
    assert status["failure_details"][honest[0]] == {
        "blame": "infra", "reason": "OSError: synthetic infrastructure failure"}
    assert status["incomplete_records"] == 0
    contrast = summary["primary_contrasts"]["C_minus_B_honest_fpr"]
    assert contrast["candidate_denominator_each_arm"] == 1
    assert contrast["excluded_candidates_by_reason"] == {"failed": 1}


@pytest.mark.parametrize("split", ["train", "test"])
def test_missing_records_are_assigned_to_their_frozen_dataset_split(tmp_path, monkeypatch, split):
    data_path, data, honest, _attack, labels, rows = _fixture(tmp_path)
    payload = json.loads(data_path.read_text())
    task_ids = [task.task_id for task in data.tasks]
    payload["split"] = {"train": [task_ids[0]], "test": [task_ids[1]]}
    data_path.write_text(json.dumps(payload), encoding="utf-8")
    missing_task = payload["split"][split][0]
    missing_cid = next(candidate.candidate_id for task, candidate in data.candidates()
                       if task.task_id == missing_task and not candidate.is_attack)
    rows_by_arm = {label: json.loads(json.dumps(rows)) for label in labels}
    rows_by_arm["C feedback"] = [row for row in rows_by_arm["C feedback"]
                                 if row["candidate_id"] != missing_cid]
    summary = _execute(tmp_path, monkeypatch, labels, data_path, rows_by_arm)
    other = "test" if split == "train" else "train"
    assert summary["by_split"][split]["arm_record_status"]["C feedback"]["missing_records"] == 1
    assert summary["by_split"][other]["arm_record_status"]["C feedback"]["missing_records"] == 0
    result = summary["by_split"][split]["contrasts"]["C_minus_B_honest_fpr"]
    assert result["candidate_denominator_each_arm"] == 0
    assert result["difference"] is None and result["bootstrap"]["percentile_95_ci"] is None
    assert result["excluded_candidates_by_reason"] == {"missing_record": 1}
    assert summary["excluded_candidates"][missing_cid]["split"] == split


def test_analysis_v2_is_derived_without_rewriting_existing_schema1_or_paying(tmp_path, monkeypatch):
    data_path, _data, _honest, _attack, labels, rows = _fixture(tmp_path)
    coordinator = tmp_path / "runs" / "tiny-coordinator"
    coordinator.mkdir(parents=True)
    original = b'{"schema_version":1,"old_result":"preserve exactly"}\n'
    legacy = coordinator / "analysis.json"
    legacy.write_bytes(original)
    rows_by_arm = {label: json.loads(json.dumps(rows)) for label in labels}
    summary = _execute(tmp_path, monkeypatch, labels, data_path, rows_by_arm)
    assert summary["schema_version"] == 2 and summary["primary_split"] == "test"
    assert legacy.read_bytes() == original
    assert (coordinator / "analysis-v2.json").exists()
