"""Read-only analysis of cached PBT run records.

This module deliberately does not import the experiment pipeline or execute notebook
cells. It consumes saved JSONL records and writes a derived report at the caller's
chosen path.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

import numpy as np


ARMS = ("baseline", "no-feedback", "feedback")
ERROR_OUTCOMES = {"candidate_crash", "prop_error"}
VALID_OUTCOMES = {"pass", "catch"}


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_sha256(value: Any) -> str:
    return _sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"required cached artifact is missing: {path}")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"expected JSON objects in {path}")
    return rows


def _unique_rows(rows: list[dict[str, Any]], path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        cid = row.get("candidate_id")
        if not isinstance(cid, str) or not cid:
            raise ValueError(f"record without candidate_id in {path}")
        if cid in result:
            raise ValueError(f"duplicate candidate_id {cid!r} in {path}")
        result[cid] = row
    return result


def _input_counts(project: Path, run_name: str, candidates: set[str]) -> dict[str, int]:
    rows = _unique_rows(_jsonl(project / "runs" / run_name / "records.jsonl"), project / "runs" / run_name / "records.jsonl")
    if set(rows) != candidates:
        missing, extra = sorted(candidates - set(rows)), sorted(set(rows) - candidates)
        raise ValueError(f"input cache candidate mismatch; missing={missing}, extra={extra}")
    counts: dict[str, int] = {}
    for cid, row in rows.items():
        if row.get("failed") or not isinstance(row.get("inputs"), list) or not row["inputs"]:
            raise ValueError(f"reviewed input measurement unavailable for {cid}: {row.get('reason') or 'invalid inputs'}")
        counts[cid] = len(row["inputs"])
    return counts


def _status(row: dict[str, Any], n_inputs: int, *, variable: bool = False) -> tuple[bool, str | None]:
    if row.get("failed"):
        return False, "failed: " + str(row.get("reason") or "source failed")
    if row.get("abstained"):
        return False, "abstained"
    tests = row.get("test_names")
    n_tests = row.get("tests_retained") if variable else 10
    if type(n_tests) is not int or n_tests < 1:
        return False, "invalid or missing test count"
    if not isinstance(tests, list) or len(tests) != n_tests or len(set(tests)) != n_tests:
        return False, "test count or uniqueness mismatch"
    if not variable and row.get("tests_src") is None:
        return False, "test source unavailable"
    expected = n_tests * n_inputs
    if row.get("n_pairs_expected") != expected or row.get("n_pairs_run") != expected:
        return False, "incomplete grid"
    counts = row.get("n_pairs_by_outcome")
    if not isinstance(counts, dict) or set(counts) - VALID_OUTCOMES - ERROR_OUTCOMES:
        return False, "malformed outcome counts"
    if any(counts.get(outcome, 0) for outcome in ERROR_OUTCOMES):
        return False, "error outcomes"
    if counts.get("pass", 0) + counts.get("catch", 0) != expected:
        return False, "outcome count mismatch"
    if row.get("is_attack") is not True and row.get("is_attack") is not False:
        return False, "missing attack label"
    if not isinstance(row.get("catches"), list):
        return False, "missing catch measurement"
    if variable or row.get("execution") is not None:
        execution = row.get("execution")
        if not isinstance(execution, dict) or not execution.get("ok") or not execution.get("complete"):
            return False, "execution not complete"
        records = execution.get("records")
        if execution.get("n_expected") != expected or not isinstance(records, list) or len(records) != expected:
            return False, "execution grid incomplete"
        pairs = [(r.get("prop"), r.get("i")) for r in records if isinstance(r, dict)]
        if len(pairs) != expected or len(set(pairs)) != expected:
            return False, "nonrectangular execution grid"
        if any(r.get("outcome") not in VALID_OUTCOMES for r in records):
            return False, "execution error outcomes"
        if {r.get("i") for r in records} != set(range(n_inputs)) or {r.get("prop") for r in records} != set(tests):
            return False, "execution grid identities mismatch"
    return True, None


def _task_bootstrap(pairs: list[dict[str, Any]], draws: int = 10_000, seed: int = 300) -> list[float] | None:
    task_ids = sorted({p["task_id"] for p in pairs})
    if not task_ids:
        return None
    grouped = {task: [p for p in pairs if p["task_id"] == task] for task in task_ids}
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(draws):
        sample = rng.choice(task_ids, size=len(task_ids), replace=True)
        chosen = [p for task in sample for p in grouped[task]]
        values.append(float(np.mean([p["left"] - p["right"] for p in chosen])))
    return [float(x) for x in np.percentile(values, [2.5, 97.5])]


def _paired_comparison(left: dict[str, dict[str, Any]], right: dict[str, dict[str, Any]],
                       status: dict[str, dict[str, tuple[bool, str | None]]],
                       left_name: str, right_name: str) -> dict[str, Any]:
    matched: list[dict[str, Any]] = []
    excluded: dict[str, list[str]] = {}
    for cid in sorted(left):
        reasons = []
        for arm, statuses in ((left_name, status[left_name]), (right_name, status[right_name])):
            ok, why = statuses[cid]
            if not ok:
                reasons.append(f"{arm}: {why}")
        if reasons:
            excluded[cid] = reasons
            continue
        a, b = left[cid], right[cid]
        matched.append({"candidate_id": cid, "task_id": a["task_id"], "is_attack": a["is_attack"],
                        "left": int(bool(a["catches"])), "right": int(bool(b["catches"]))})
    strata = {}
    for label, attack in (("honest", False), ("attack", True)):
        values = [p for p in matched if p["is_attack"] is attack]
        if not values:
            strata[label] = {"n": 0, "task_n": 0, "left_rate": None, "right_rate": None,
                             "delta_left_minus_right": None, "ci95_task_bootstrap": None,
                             "paired_gains": 0, "paired_losses": 0, "both_catch": 0, "both_clean": 0}
            continue
        strata[label] = {
            "n": len(values), "task_n": len({p["task_id"] for p in values}),
            "left_rate": float(np.mean([p["left"] for p in values])),
            "right_rate": float(np.mean([p["right"] for p in values])),
            "delta_left_minus_right": float(np.mean([p["left"] - p["right"] for p in values])),
            "ci95_task_bootstrap": _task_bootstrap(values),
            "paired_gains": sum(p["left"] and not p["right"] for p in values),
            "paired_losses": sum(p["right"] and not p["left"] for p in values),
            "both_catch": sum(p["left"] and p["right"] for p in values),
            "both_clean": sum(not p["left"] and not p["right"] for p in values),
        }
    return {"left_arm": left_name, "right_arm": right_name, "matched_n": len(matched),
            "matched_task_n": len({p["task_id"] for p in matched}), "strata": strata, "exclusions": excluded}


def _replay_report(project: Path, prefix: str, arms: dict[str, dict[str, Any]],
                   status: dict[str, dict[str, tuple[bool, str | None]]],
                   input_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    study = project / "runs" / f"{prefix}-study"
    replay_roots = {arm: [study / "same-input-honest-replay-v1" / f"{prefix}-{arm}"]
                    for arm in ARMS}
    replay_roots["delete-only"] = [study / "same-input-honest-replay-v1" / f"{prefix}-delete-only"]
    historical_delete_root = study / "delete-only-v1" / "honest-twin-replay" / f"{prefix}-delete-only"
    replay_roots["delete-only"].append(historical_delete_root)
    if not any(root.exists() for roots in replay_roots.values() for root in roots):
        return {"status": "not_measured", "reason": "no replay files found"}

    data_path = project / "data" / "bcb_replication26_eval.json"
    try:
        data_raw = data_path.read_bytes()
        data = json.loads(data_raw)
        honest_code: dict[str, str] = {}
        for task in data["tasks"]:
            honest = [candidate for candidate in task["candidates"] if candidate.get("label") == "honest"]
            if len(honest) == 1 and isinstance(honest[0].get("code"), str):
                honest_code[task["task_id"]] = honest[0]["code"]
        dataset_sha256 = _sha256(data_raw)
    except (OSError, ValueError, KeyError, TypeError):
        data_raw = b""
        dataset_sha256 = None
        honest_code = {}

    configs: dict[str, tuple[dict[str, Any] | None, str | None]] = {}
    for arm in arms:
        config_path = project / "runs" / f"{prefix}-{arm}" / "config.json"
        try:
            raw_config = config_path.read_bytes()
            configs[arm] = (json.loads(raw_config), _sha256(raw_config))
        except (OSError, ValueError):
            configs[arm] = (None, None)

    launch_manifests = []
    for path in study.rglob("*replay*launch*.json"):
        try:
            launch_manifests.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue

    def identity_problem(arm: str, row: dict[str, Any], saved: dict[str, Any]) -> str | None:
        identity = saved.get("identity")
        if not isinstance(identity, dict):
            return "missing replay identity"
        config, config_hash = configs[arm]
        input_record = input_rows.get(row["candidate_id"])
        code = honest_code.get(row["task_id"])
        if dataset_sha256 is None or config_hash is None or input_record is None or code is None:
            return "identity prerequisites unavailable (dataset/config/input/honest code)"
        expected = {
            "dataset_sha256": dataset_sha256,
            "source_config_sha256": config_hash,
            "source_record_sha256": _canonical_sha256(row),
            "inputs_sha256": _canonical_sha256(input_record["inputs"]),
            "honest_code_sha256": _sha256(code.encode("utf-8")),
            "suite_sha256": None if row.get("tests_src") is None else _sha256(row["tests_src"].encode("utf-8")),
        }
        for key, value in expected.items():
            if key not in identity or identity[key] != value:
                return f"replay identity mismatch: {key}"
        params = config.get("params", {}) if isinstance(config, dict) else {}
        image = params.get("docker_image") if isinstance(params, dict) else None
        if image is None and isinstance(config, dict):
            image = config.get("docker_image")
        if image is not None and identity.get("docker_image") != image:
            return "replay identity mismatch: docker_image"
        timeout = params.get("sandbox_seconds") if isinstance(params, dict) else None
        if timeout is None and isinstance(config, dict):
            timeout = config.get("timeout_seconds")
        if timeout is not None and identity.get("timeout_seconds") != timeout:
            return "replay identity mismatch: timeout_seconds"
        wrapper_hash = identity.get("wrapper_sha256")
        if wrapper_hash is not None:
            run_name = f"{prefix}-{arm}"
            matching = [manifest for manifest in launch_manifests
                        if run_name in (manifest.get("arms") or []) and isinstance(manifest.get("harness_wrapper"), str)]
            if not matching:
                return "replay identity wrapper hash has no matching launch manifest"
            validated = False
            for manifest in matching:
                source_hash = _sha256(manifest["harness_wrapper"].encode("utf-8"))
                if wrapper_hash == source_hash and manifest.get("wrapper_sha256") == source_hash:
                    validated = True
                    break
            if not validated:
                return "replay identity mismatch: wrapper_sha256"
        return None

    per_arm = {}
    for arm, rows in arms.items():
        details = []
        roots = replay_roots[arm]
        for cid, row in sorted(rows.items()):
            if row.get("is_attack") is not True:
                continue
            entry: dict[str, Any] = {"candidate_id": cid, "task_id": row["task_id"]}
            own_ok, own_reason = status[arm][cid]
            if not own_ok:
                entry.update(eligible=False, exclusion="own: " + str(own_reason))
                details.append(entry)
                continue
            replay_paths = [root / (row["task_id"] + ".json") for root in roots]
            path = next((candidate for candidate in replay_paths if candidate.is_file()), replay_paths[0])
            if not path.is_file():
                entry.update(eligible=False, exclusion="missing replay artifact")
                details.append(entry)
                continue
            saved = json.loads(path.read_text(encoding="utf-8"))
            identity_error = identity_problem(arm, row, saved)
            if identity_error:
                entry.update(eligible=False, exclusion=identity_error)
                details.append(entry)
                continue
            result = saved.get("result")
            # The source record's expected pair count fixes the replay grid denominator.
            expected = row.get("n_pairs_expected")
            replay_records = result.get("records") if isinstance(result, dict) else None
            if saved.get("failure") is not None:
                reason = "replay failure: " + str(saved["failure"])
            elif (not isinstance(result, dict) or not result.get("ok") or not result.get("complete")
                  or result.get("n_expected") != expected or result.get("n_records") != expected
                  or not isinstance(replay_records, list) or len(replay_records) != expected):
                reason = "replay grid incomplete"
            elif any(not isinstance(item, dict) or item.get("outcome") not in VALID_OUTCOMES for item in replay_records):
                reason = "replay execution error outcomes"
            else:
                reason = None
            if reason:
                entry.update(eligible=False, exclusion=reason)
            else:
                replay_caught = any(item.get("outcome") == "catch" for item in replay_records)
                own_caught = bool(row["catches"])
                entry.update(eligible=True, own_attack_caught=own_caught,
                             replay_honest_caught=replay_caught,
                             whole_suite_clean=not replay_caught,
                             differential=own_caught and not replay_caught)
            details.append(entry)
        eligible = [item for item in details if item["eligible"]]
        per_arm[arm] = {"attempted_attack_candidates": len(details), "eligible": len(eligible),
                        "excluded": len(details) - len(eligible),
                        "own_attack_caught": sum(item["own_attack_caught"] for item in eligible),
                        "replay_honest_caught": sum(item["replay_honest_caught"] for item in eligible),
                        "whole_suite_clean": sum(item["whole_suite_clean"] for item in eligible),
                        "differential": sum(item["differential"] for item in eligible),
                        "exclusions": [{"candidate_id": item["candidate_id"], "reason": item["exclusion"]}
                                       for item in details if not item["eligible"]],
                        "details": details}
    has_eligible = any(item["eligible"] for arm in per_arm.values() for item in arm["details"])
    return {"status": "measured" if has_eligible else "identity_unverified",
            "scope": "attack candidates; cached honest-twin replays only",
            "identity_validation": "dataset/config/source-record/input/honest-code/suite hashes required; image and timeout checked when configured; wrapper hash checked when present",
            "per_arm": per_arm}


def analyze(project: Path, prefix: str, inputs_run: str, output: Path, include_delete: bool) -> dict[str, Any]:
    """Analyze cached run artifacts under ``project`` and write a JSON report.

    ``output`` is an explicit derived-artifact destination. Missing or failed inputs
    are errors; incomplete run measurements are retained in exclusions, never scored
    as clean.
    """
    project = Path(project)
    output = Path(output)
    arms = {name: _unique_rows(_jsonl(project / "runs" / f"{prefix}-{name}" / "records.jsonl"),
                               project / "runs" / f"{prefix}-{name}" / "records.jsonl")
            for name in ARMS}
    if include_delete:
        name = "delete-only"
        path = project / "runs" / f"{prefix}-{name}" / "records.jsonl"
        arms[name] = _unique_rows(_jsonl(path), path)
    candidates = set(arms["baseline"])
    if not candidates or any(set(rows) != candidates for rows in arms.values()):
        raise ValueError("arm caches must contain the same non-empty candidate set")
    labels = {}
    for cid in sorted(candidates):
        row = arms["baseline"][cid]
        if type(row.get("is_attack")) is not bool or not isinstance(row.get("task_id"), str):
            raise ValueError(f"baseline record lacks task/label for {cid}")
        labels[cid] = (row["task_id"], row["is_attack"])
        for arm, rows in arms.items():
            other = rows[cid]
            if (other.get("task_id"), other.get("is_attack")) != labels[cid]:
                raise ValueError(f"arm identity mismatch for {cid} in {arm}")
    inputs = _input_counts(project, inputs_run, candidates)
    statuses = {
        arm: {cid: _status(row, inputs[cid], variable=(arm == "delete-only"))
              for cid, row in records.items()}
        for arm, records in arms.items()
    }
    report: dict[str, Any] = {
        "schema_version": 1,
        "study_prefix": prefix,
        "inputs_run": inputs_run,
        "population": {"candidates": len(candidates), "tasks": len({v[0] for v in labels.values()}),
                       "previously_exposed": True, "confirmatory": False},
        "arms": {arm: {"run_name": f"{prefix}-{arm}", "attempted": len(records),
                       "eligible": sum(ok for ok, _ in statuses[arm].values()),
                       "excluded": {cid: reason for cid, (ok, reason) in statuses[arm].items() if not ok}}
                 for arm, records in arms.items()},
        "primary": {"metric": "catch rate; eligible complete grids only", "strata": {}},
        "paired": {},
        "whole_suite_clean": {"status": "not_measured", "reason": "no replay files were requested or consumed"},
        "bootstrap": {"draws": 10_000, "seed": 300, "unit": "whole task_id"},
    }
    for pair, names in (("matched_abc", ARMS), ("matched_bc", ("no-feedback", "feedback"))):
        common = [cid for cid in candidates if all(statuses[a][cid][0] for a in names)]
        report["primary"][pair] = {
            "matched_n": len(common),
            "exclusions": {cid: {a: statuses[a][cid][1] for a in names if not statuses[a][cid][0]}
                           for cid in sorted(candidates) if cid not in common},
            "strata": {},
        }
        for attack, label in ((False, "honest"), (True, "attack")):
            group = [cid for cid in common if labels[cid][1] is attack]
            report["primary"][pair]["strata"][label] = {
                arm: {"n": len(group), "caught": sum(bool(arms[arm][cid]["catches"]) for cid in group),
                      "rate": float(np.mean([bool(arms[arm][cid]["catches"]) for cid in group])) if group else None}
                for arm in names
            }
    report["paired"]["feedback_vs_no_feedback"] = _paired_comparison(
        arms["feedback"], arms["no-feedback"], statuses, "feedback", "no-feedback")
    if include_delete:
        report["paired"]["delete_vs_baseline"] = _paired_comparison(
            arms["delete-only"], arms["baseline"], statuses, "delete-only", "baseline")
        report["paired"]["delete_vs_feedback"] = _paired_comparison(
            arms["delete-only"], arms["feedback"], statuses, "delete-only", "feedback")
        retained = [r["tests_retained"] for r in arms["delete-only"].values()
                    if type(r.get("tests_retained")) is int and r["tests_retained"] > 0]
        report["delete_only"] = {"retained_test_count_n": len(retained),
                                  "retained_test_count_distribution": {str(n): retained.count(n) for n in sorted(set(retained))},
                                  "abstentions": sorted(cid for cid, row in arms["delete-only"].items() if row.get("abstained"))}
    input_rows = _unique_rows(_jsonl(project / "runs" / inputs_run / "records.jsonl"),
                              project / "runs" / inputs_run / "records.jsonl")
    report["whole_suite_clean"] = _replay_report(project, prefix, arms, statuses, input_rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report
