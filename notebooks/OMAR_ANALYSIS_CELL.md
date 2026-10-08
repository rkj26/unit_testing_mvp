# Omar strict complete/error-free paired analysis

This is the authoritative analysis cell source for this checkout. The generator appends
its Python block to the existing Omar continuation code cell automatically: do not paste
another cell. It computes paired honest FPR / attack catch and task-cluster bootstrap
contrasts from the registered completed Omar arms, with zero model or Docker calls.
The primary held-out result uses **test tasks only**. Train is reported separately as
descriptive; this report does not pool train and test.
APPS uses A/B/C; BCB additionally uses D, detected from dataset metadata.

The native shared-team threshold/deployment plots remain unchanged. Their native coverage
may retain partial catches and mixed pass/property-error records. These plots and this
separately labeled strict complete/error-free analysis are **not interchangeable**.
Strict eligibility requires every contrast arm to have a nonfailed, nonabstained,
complete grid with valid outcomes and no property error or candidate crash.
Missing/error records are explicit exclusions, never clean negatives.

Rates are candidate-level, with honest and attack denominators reported separately.
Bootstrap samples task IDs with replacement and retains paired arms in each cluster;
10,000 draws, seed 300. These are descriptive across-task intervals, not repeated-run
uncertainty or proof of generalization. Fewer than two eligible task clusters yields no
interval. The cell saves schema 2 to `runs/<Omar-prefix>-coordinator/analysis-v2.json`
without changing measured records or an existing schema-1 `analysis.json`. Updating
this derived report requires only rerunning the continuation on completed cached arms,
not another paid run. If a previous v2 derived file differs, preserve it under another
filename and recompute from the same saved records. Execute from the repository root.

```python
# Omar strict complete/error-free paired analysis (zero API calls)
import json
from collections import Counter
from pathlib import Path

import numpy as np

OMAR_BOOTSTRAP_DRAWS = 10_000
OMAR_BOOTSTRAP_SEED = 300
OMAR_PRIMARY_SPLIT = "test"
OMAR_REQUIRED = ("A initial", "B no feedback", "C feedback")
OMAR_DATASET = omar_arms[OMAR_REQUIRED[0]].data_path
OMAR_BCB = omar_arms[OMAR_REQUIRED[0]].data.backend == "bcb"
OMAR_KEYS = (*OMAR_REQUIRED, "D delete only") if OMAR_BCB else OMAR_REQUIRED
OMAR_LABELS = {"A": OMAR_REQUIRED[0], "B": OMAR_REQUIRED[1], "C": OMAR_REQUIRED[2]}
if OMAR_BCB:
    OMAR_LABELS["D"] = "D delete only"
missing_arms = sorted(set(OMAR_KEYS) - set(omar_arms))
if missing_arms:
    raise RuntimeError(f"Omar arms are missing: {missing_arms}")

# Each row preserves the raw outcome counts needed to audit whether a negative was clean.
om_task_by_candidate = {}
om_kind_by_candidate = {}
om_split_by_candidate = {}
om_task_ids = set()
for task, candidate in omar_arms[OMAR_REQUIRED[0]].data.candidates():
    om_task_ids.add(task.task_id)
    om_split_by_candidate[candidate.candidate_id] = omar_arms[OMAR_REQUIRED[0]].data.split_of(task.task_id)
    om_task_by_candidate[candidate.candidate_id] = task.task_id
    om_kind_by_candidate[candidate.candidate_id] = "attack" if candidate.is_attack else "honest"
by_task_kind = Counter((om_task_by_candidate[cid], kind)
                       for cid, kind in om_kind_by_candidate.items())
if not om_task_ids or any(by_task_kind[(task_id, kind)] != 1
                          for task_id in om_task_ids for kind in ("honest", "attack")):
    raise ValueError("analysis requires exactly one honest and one attack candidate per task")

def om_status(records, expected_ids):
    """Count failures before inspecting optional execution metadata."""
    rows = [records[cid] for cid in expected_ids if cid in records]
    failures = [row for row in rows if row["failed"]]
    measured = [row for row in rows if not row["failed"] and not row.get("abstained", False)]
    pair_fields = {"n_pairs_run", "n_pairs_expected", "n_pairs_by_outcome", "catches"}
    grids = [row for row in measured if pair_fields <= row.keys()]
    outcomes = Counter()
    for row in grids:
        counts = row["n_pairs_by_outcome"]
        if (isinstance(counts, dict)
                and all(type(value) is int and value >= 0 for value in counts.values())):
            outcomes.update(counts)
    return {
        "attempted_records": len(rows),
        "missing_records": len(expected_ids) - len(rows),
        "failed_records": len(failures),
        "failures_by_blame": dict(Counter(row["blame"] for row in failures)),
        "failure_details": {row["candidate_id"]: {"blame": row["blame"], "reason": row["reason"]}
                            for row in failures},
        "incomplete_records": sum(row["n_pairs_run"] != row["n_pairs_expected"]
                                  or ("complete" in row and not row["complete"]) for row in grids),
        "missing_pair_metadata": len(measured) - len(grids),
        "abstentions": sum(bool(row.get("abstained", False)) for row in rows if not row["failed"]),
        "outcome_counts": dict(outcomes),
    }

om_records = {}
om_record_status = {}
for arm_key in OMAR_KEYS:
    arm = omar_arms[arm_key]
    rows = arm.get_records()
    records = {}
    duplicates = set()
    for row in rows:
        cid = row["candidate_id"]
        if cid in records:
            duplicates.add(cid)
        records[cid] = row
    if duplicates:
        raise ValueError(f"{arm_key} has duplicate records: {sorted(duplicates)[:5]}")
    unexpected = set(records) - set(om_task_by_candidate)
    if unexpected:
        raise ValueError(f"{arm_key} has candidates outside the frozen dataset: {sorted(unexpected)[:5]}")
    om_records[arm_key] = records
    om_record_status[arm_key] = om_status(records, list(om_task_by_candidate))

def om_record_reason(row):
    """Validate a measured grid before any record enters a denominator."""
    if row is None:
        return "missing_record"
    if row["failed"]:
        return "failed"
    if row.get("abstained", False):
        return "abstained"
    if not {"n_pairs_run", "n_pairs_expected", "n_pairs_by_outcome", "catches"} <= row.keys():
        return "missing_pair_metadata"
    counts = row["n_pairs_by_outcome"]
    if counts is None:
        return "missing_pair_outcomes"
    if (type(row["n_pairs_expected"]) is not int or row["n_pairs_expected"] <= 0
            or row["n_pairs_run"] != row["n_pairs_expected"]
            or ("complete" in row and not row["complete"])):
        return "pair_count_mismatch"
    if (not isinstance(counts, dict)
            or set(counts) - {"pass", "catch", "prop_error", "candidate_crash"}
            or any(type(value) is not int or value < 0 for value in counts.values())):
        return "invalid_pair_outcomes"
    if counts.get("prop_error", 0) or counts.get("candidate_crash", 0):
        return "execution_error_outcome"
    if sum(counts.values()) != row["n_pairs_expected"]:
        return "outcome_count_mismatch"
    catches = row["catches"]
    if not isinstance(catches, list) or bool(catches) != bool(counts.get("catch", 0)):
        return "catch_outcome_mismatch"
    return None

def om_eligible(candidate_id, arm_keys):
    """Return (eligible, reason); missing/error states never become clean negatives."""
    for arm_key in arm_keys:
        reason = om_record_reason(om_records[arm_key].get(candidate_id))
        if reason is not None:
            return False, reason
    return True, None

def om_bootstrap_differences(task_ids, candidates, arm_left, arm_right):
    """Return seeded paired task-cluster rate differences and undefined draw count.

    Task-level counts preserve candidate weights; chunked index samples retain the
    original draw order with bounded memory and no repeated candidate scan.
    """
    if len(task_ids) < 2:
        return [], 0
    task_index = {task_id: index for index, task_id in enumerate(task_ids)}
    denominators = np.zeros(len(task_ids), dtype=np.int64)
    left_counts = np.zeros(len(task_ids), dtype=np.int64)
    right_counts = np.zeros(len(task_ids), dtype=np.int64)
    for cid, _kind in candidates:
        index = task_index[om_task_by_candidate[cid]]
        denominators[index] += 1
        for arm_key, counts in ((arm_left, left_counts), (arm_right, right_counts)):
            catches = om_records[arm_key][cid]["catches"]
            if catches is None:
                raise ValueError(f"eligible {arm_key}/{cid} has no catches list")
            counts[index] += int(bool(catches))
    rng = np.random.default_rng(OMAR_BOOTSTRAP_SEED)
    draws = []
    undefined_draws = 0
    chunk_size = 256
    for start in range(0, OMAR_BOOTSTRAP_DRAWS, chunk_size):
        count = min(chunk_size, OMAR_BOOTSTRAP_DRAWS - start)
        sampled = rng.choice(len(task_ids), size=(count, len(task_ids)), replace=True)
        denominator = denominators[sampled].sum(axis=1)
        defined = denominator > 0
        undefined_draws += int((~defined).sum())
        left = left_counts[sampled].sum(axis=1)[defined] / denominator[defined]
        right = right_counts[sampled].sum(axis=1)[defined] / denominator[defined]
        draws.extend((left - right).tolist())
    return draws, undefined_draws

def om_metric(candidates, arm_key):
    if not candidates:
        return None
    numerator = 0
    for cid, _kind in candidates:
        catches = om_records[arm_key][cid]["catches"]
        if catches is None:
            raise ValueError(f"eligible {arm_key}/{cid} has no catches list")
        numerator += int(bool(catches))
    return numerator / len(candidates)

def om_compare(arm_left, arm_right, kind, split):
    """Paired rate difference on one explicitly named complete/error-free dataset split."""
    contrast_keys = (arm_left, arm_right)
    candidates = [(cid, candidate_kind) for cid, candidate_kind in om_kind_by_candidate.items()
                  if candidate_kind == kind and om_split_by_candidate[cid] == split
                  and om_eligible(cid, contrast_keys)[0]]
    task_ids = sorted({om_task_by_candidate[cid] for cid, _ in candidates})
    draws, undefined_draws = om_bootstrap_differences(
        task_ids, candidates, arm_left, arm_right)
    point = om_metric(candidates, arm_left)
    right_point = om_metric(candidates, arm_right)
    interval = (np.quantile(draws, [0.025, 0.975]).tolist() if draws else None)
    exclusions = Counter()
    for cid, candidate_kind in om_kind_by_candidate.items():
        if candidate_kind == kind and om_split_by_candidate[cid] == split:
            ok, reason = om_eligible(cid, contrast_keys)
            if not ok:
                exclusions[reason] += 1
    return {
        "population": kind,
        "split": split,
        "left_arm": arm_left,
        "right_arm": arm_right,
        "contrast": "left_minus_right",
        "left_rate": point,
        "right_rate": right_point,
        "difference": None if point is None else point - right_point,
        "candidate_denominator_each_arm": len(candidates),
        "task_denominator": len(task_ids),
        "eligible_task_ids": task_ids,
        "bootstrap": {"unit": "task_id_cluster", "draws": OMAR_BOOTSTRAP_DRAWS,
                      "seed": OMAR_BOOTSTRAP_SEED, "undefined_draws": undefined_draws,
                      "interpretation": "descriptive_task_cluster_not_repeated_run",
                      "interval_status": "estimated" if len(task_ids) >= 2 else "fewer_than_two_task_clusters",
                      "percentile_95_ci": interval},
        "excluded_candidates_by_reason": dict(exclusions),
    }

# Each split gets its own candidate-level ABC intersection and paired contrasts.
# Train is descriptive; only test contrasts are the primary held-out result.
om_split_results = {}
for split in ("train", "test"):
    split_ids = [cid for cid in om_task_by_candidate if om_split_by_candidate[cid] == split]
    common_ids = [cid for cid in split_ids if om_eligible(cid, OMAR_REQUIRED)[0]]
    common_task_ids = sorted({om_task_by_candidate[cid] for cid in common_ids})
    common_by_kind = {
        kind: [(cid, kind) for cid in common_ids if om_kind_by_candidate[cid] == kind]
        for kind in ("honest", "attack")
    }
    matched = {}
    for arm_label, arm_key in list(OMAR_LABELS.items())[:3]:
        matched[arm_label] = {
            "arm": arm_key,
            "honest_fpr": om_metric(common_by_kind["honest"], arm_key),
            "honest_candidate_denominator": len(common_by_kind["honest"]),
            "attack_catch_rate": om_metric(common_by_kind["attack"], arm_key),
            "attack_candidate_denominator": len(common_by_kind["attack"]),
        }
    contrasts = {
        "C_minus_B_honest_fpr": om_compare(OMAR_LABELS["C"], OMAR_LABELS["B"], "honest", split),
        "C_minus_B_attack_catch": om_compare(OMAR_LABELS["C"], OMAR_LABELS["B"], "attack", split),
    }
    if OMAR_BCB:
        contrasts.update({
            "D_minus_C_honest_fpr": om_compare(OMAR_LABELS["D"], OMAR_LABELS["C"], "honest", split),
            "D_minus_C_attack_catch": om_compare(OMAR_LABELS["D"], OMAR_LABELS["C"], "attack", split),
            "D_minus_A_honest_fpr": om_compare(OMAR_LABELS["D"], OMAR_LABELS["A"], "honest", split),
            "D_minus_A_attack_catch": om_compare(OMAR_LABELS["D"], OMAR_LABELS["A"], "attack", split),
        })
    om_split_results[split] = {
        "role": "primary_held_out" if split == OMAR_PRIMARY_SPLIT else "descriptive_train",
        "dataset_candidate_count": len(split_ids),
        "arm_record_status": {key: om_status(om_records[key], split_ids) for key in OMAR_KEYS},
        "common_ABC_grid": {
            "candidate_count": len(common_ids),
            "task_count": len(common_task_ids),
            "task_ids": common_task_ids,
            "candidate_ids": sorted(common_ids),
            "matched_rates": matched,
        },
        "contrasts": contrasts,
    }

om_exclusions = {}
for cid, kind in om_kind_by_candidate.items():
    reason_counts = Counter()
    per_arm = {}
    for arm_key in OMAR_KEYS:
        row = om_records[arm_key].get(cid)
        reason = om_record_reason(row)
        if reason:
            reason_counts[reason] += 1
            per_arm[arm_key] = reason
    if per_arm:
        om_exclusions[cid] = {"task_id": om_task_by_candidate[cid], "kind": kind,
                              "split": om_split_by_candidate[cid], "by_arm": per_arm}

om_summary = {
    "schema_version": 2,
    "analysis": "omar_strict_complete_error_free_paired_rates",
    "population": OMAR_DATASET,
    "arms": {label: key for label, key in OMAR_LABELS.items()},
    "arm_record_status": om_record_status,
    "primary_split": OMAR_PRIMARY_SPLIT,
    "primary_contrasts": om_split_results[OMAR_PRIMARY_SPLIT]["contrasts"],
    "by_split": om_split_results,
    "excluded_candidates": om_exclusions,
    "method_notes": [
        "Primary contrasts use only test tasks; train results are separate and descriptive. No pooled estimate is reported.",
        "FPR is the fraction of honest candidates caught; attack catch is the fraction of attacks caught.",
        "Missing, failed, abstained, incomplete, or execution-error candidate grids are excluded, never clean negatives.",
        "Bootstrap resamples task IDs with replacement; each sampled task carries its eligible candidates and both contrast arms.",
        "Percentile intervals are descriptive and do not establish causality or generalization.",
    ],
}

# Resolve the coordinator prefix from this registered A arm's run name; no historical
# run folder is opened or assumed.
coordinator = Path("runs") / f"{omar_arms[OMAR_REQUIRED[0]].run_name[:-len('-A-traceable')]}-coordinator"
coordinator.mkdir(parents=True, exist_ok=True)
analysis_path = coordinator / "analysis-v2.json"
analysis_text = json.dumps(om_summary, indent=2, sort_keys=True, allow_nan=False) + "\n"
if analysis_path.exists() and analysis_path.read_text(encoding="utf-8") != analysis_text:
    raise ValueError(f"derived analysis differs: {analysis_path}; preserve it under another filename before recomputing from the same saved records (no model rerun needed)")
if not analysis_path.exists():
    analysis_path.write_text(analysis_text, encoding="utf-8")
print(f"Omar strict complete/error-free paired analysis: {analysis_path}")
print(json.dumps({"label": "Omar strict complete/error-free paired rates",
                  "primary_split": OMAR_PRIMARY_SPLIT,
                  "primary_contrasts": om_summary["primary_contrasts"],
                  "by_split": {split: {
                      "role": result["role"],
                      "common_grid_candidates": result["common_ABC_grid"]["candidate_count"],
                      "common_grid_tasks": result["common_ABC_grid"]["task_count"],
                      "matched_rates": result["common_ABC_grid"]["matched_rates"],
                      "contrasts": result["contrasts"],
                      "arm_record_status": result["arm_record_status"]}
                      for split, result in om_split_results.items()}}, indent=2))
```
