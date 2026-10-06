import json
import hashlib
from pathlib import Path

import pytest

from pbt_runner.analysis import analyze


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _row(cid, task, attack, caught=False, *, ntests=10, failed=False, error=False):
    expected = ntests * 2
    names = [f"test_{i}" for i in range(ntests)]
    execution = {
        "ok": True,
        "complete": True,
        "n_expected": expected,
        "records": [
            {"prop": name, "i": index, "outcome": "candidate_crash" if error and index == 0 and name == names[0] else "pass"}
            for index in range(2) for name in names
        ],
    }
    return {
        "candidate_id": cid,
        "task_id": task,
        "is_attack": attack,
        "failed": failed,
        "abstained": False,
        "reason": "synthetic failure" if failed else None,
        "test_names": names,
        "tests_src": "def test_one(): pass",
        "tests_retained": ntests,
        "catches": ["test_0"] if caught else [],
        "n_pairs_expected": expected,
        "n_pairs_run": expected,
        "n_pairs_by_outcome": {"pass": expected - int(error), "catch": 0, "candidate_crash": int(error), "prop_error": 0},
        "execution": execution,
    }


def _project(tmp_path):
    project = tmp_path / "project"
    candidates = [("honest-a", "task-a", False), ("attack-a", "task-a", True),
                  ("honest-b", "task-b", False), ("attack-b", "task-b", True)]
    for arm in ("baseline", "no-feedback", "feedback", "delete-only"):
        rows = []
        for ix, (cid, task, attack) in enumerate(candidates):
            ntests = 4 if arm == "delete-only" else 10
            caught = attack and (arm != "delete-only" or ix == 1)
            row = _row(cid, task, attack, caught, ntests=ntests)
            if cid == "honest-b" and arm == "feedback":
                row["n_pairs_run"] -= 1
            rows.append(row)
        _write_jsonl(project / "runs" / f"p-{arm}" / "records.jsonl", rows)
    inputs = [{"candidate_id": cid, "failed": False, "inputs": [{"x": 1}, {"x": 2}]}
              for cid, _, _ in candidates]
    _write_jsonl(project / "runs" / "inputs" / "records.jsonl", inputs)
    return project


def test_analyze_reports_denominators_exclusions_and_variable_delete_grid(tmp_path):
    project = _project(tmp_path)
    output = tmp_path / "derived" / "analysis.json"
    report = analyze(project, "p", "inputs", output, include_delete=True)

    assert output.is_file()
    assert json.loads(output.read_text(encoding="utf-8")) == report
    assert report["population"] == {"candidates": 4, "tasks": 2, "previously_exposed": True, "confirmatory": False}
    assert report["primary"]["matched_abc"]["matched_n"] == 3
    assert report["primary"]["matched_abc"]["strata"]["honest"]["baseline"] == {"n": 1, "caught": 0, "rate": 0.0}
    assert report["primary"]["matched_bc"]["exclusions"]["honest-b"]["feedback"] == "incomplete grid"
    assert report["paired"]["delete_vs_baseline"]["matched_n"] == 4
    assert report["paired"]["delete_vs_feedback"]["matched_n"] == 3
    assert report["arms"]["feedback"]["excluded"] == {"honest-b": "incomplete grid"}
    assert report["delete_only"]["retained_test_count_distribution"] == {"4": 4}
    assert report["whole_suite_clean"]["status"] == "not_measured"


def test_missing_or_failed_input_cache_is_not_scored_as_zero(tmp_path):
    project = _project(tmp_path)
    path = project / "runs" / "inputs" / "records.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[0]["failed"] = True
    _write_jsonl(path, rows)
    with pytest.raises(ValueError, match="input measurement unavailable"):
        analyze(project, "p", "inputs", tmp_path / "out.json", include_delete=False)


def test_replay_identity_is_required_and_new_delete_replay_root_is_supported(tmp_path):
    project = _project(tmp_path)
    data = {"tasks": [
        {"task_id": task, "candidates": [
            {"candidate_id": cid.replace("attack", "honest"), "label": "honest", "code": f"honest {task}"},
            {"candidate_id": cid, "label": "attack", "code": f"attack {task}"},
        ]}
        for cid, task in (("attack-a", "task-a"), ("attack-b", "task-b"))
    ]}
    data_path = project / "data" / "bcb_replication26_eval.json"
    data_path.parent.mkdir(parents=True)
    data_path.write_text(json.dumps(data), encoding="utf-8")
    config = {"params": {"docker_image": "fixture@sha256:abc", "sandbox_seconds": 120}}
    config_path = project / "runs" / "p-delete-only" / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    source_rows = [json.loads(line) for line in (project / "runs" / "p-delete-only" / "records.jsonl").read_text(encoding="utf-8").splitlines()]
    input_rows = [json.loads(line) for line in (project / "runs" / "inputs" / "records.jsonl").read_text(encoding="utf-8").splitlines()]
    root = project / "runs" / "p-study" / "same-input-honest-replay-v1" / "p-delete-only"
    root.mkdir(parents=True)

    def sha(value):
        return hashlib.sha256(value).hexdigest()

    def canonical(value):
        return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))

    for cid, task in (("attack-a", "task-a"), ("attack-b", "task-b")):
        row = next(item for item in source_rows if item["candidate_id"] == cid)
        input_record = next(item for item in input_rows if item["candidate_id"] == cid)
        identity = {
            "dataset_sha256": sha(data_path.read_bytes()),
            "source_config_sha256": sha(config_path.read_bytes()),
            "source_record_sha256": canonical(row),
            "inputs_sha256": canonical(input_record["inputs"]),
            "honest_code_sha256": sha(f"honest {task}".encode()),
            "suite_sha256": sha(row["tests_src"].encode()),
            "docker_image": "fixture@sha256:abc",
            "timeout_seconds": 120,
        }
        if cid == "attack-b":
            identity["source_record_sha256"] = "wrong"
        saved = {"identity": identity, "failure": None, "result": {
            "ok": True, "complete": True, "n_expected": 8, "n_records": 8,
            "records": [{"outcome": "pass"}] * 8,
        }}
        path = root / f"{task}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(saved), encoding="utf-8")

    report = analyze(project, "p", "inputs", tmp_path / "out.json", include_delete=True)
    deletion = report["whole_suite_clean"]["per_arm"]["delete-only"]
    assert report["whole_suite_clean"]["status"] == "measured"
    assert deletion["eligible"] == 1
    assert deletion["whole_suite_clean"] == 1
    assert deletion["exclusions"] == [{"candidate_id": "attack-b", "reason": "replay identity mismatch: source_record_sha256"}]


def test_duplicate_candidates_are_rejected(tmp_path):
    project = _project(tmp_path)
    path = project / "runs" / "p-baseline" / "records.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    _write_jsonl(path, rows + [rows[0]])
    with pytest.raises(ValueError, match="duplicate candidate_id"):
        analyze(project, "p", "inputs", tmp_path / "out.json", include_delete=False)


def test_saved_bcb_reports_match_archived_denominators_and_catches(tmp_path):
    wrapper = Path(__file__).resolve().parents[2]
    project = wrapper / "snapshot"
    if not project.exists():
        project = Path('/opt/archive/snapshot')
    if not (project / "runs" / "azure-terra-pbt-bcb26-s300-v1-baseline" / "records.jsonl").is_file():
        pytest.skip("archived BCB cache is not present")
    report = analyze(project, "azure-terra-pbt-bcb26-s300-v1",
                     "azure-terra-pbt-bcb26-s300-v1-reviewed-inputs",
                     tmp_path / "derived.json", include_delete=True)
    # Counts cross-check the frozen v3 primary supplement and v1 delete analysis.
    assert report["primary"]["matched_abc"]["strata"]["attack"] == {
        "baseline": {"n": 21, "caught": 21, "rate": 1.0},
        "no-feedback": {"n": 21, "caught": 19, "rate": 19 / 21},
        "feedback": {"n": 21, "caught": 19, "rate": 19 / 21},
    }
    assert report["paired"]["delete_vs_baseline"]["matched_n"] == 48
    assert report["paired"]["delete_vs_baseline"]["strata"]["attack"]["n"] == 25
    assert report["paired"]["delete_vs_baseline"]["strata"]["attack"]["delta_left_minus_right"] == pytest.approx(-0.12)
    assert report["paired"]["delete_vs_feedback"]["matched_n"] == 42
    assert report["paired"]["delete_vs_feedback"]["strata"]["attack"]["n"] == 20
    assert report["paired"]["delete_vs_feedback"]["strata"]["attack"]["delta_left_minus_right"] == pytest.approx(-0.05)
    assert report["whole_suite_clean"]["status"] == "measured"
