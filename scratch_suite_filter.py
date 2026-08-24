"""Does the ablation control tell a wrong unit test from a real catch?

A suite fires on the submission. Run the same suite against the control -- the submission with only
the monitor-flagged branch removed. A test that fires on both is asserting something the submission
never promised, so it is the test that is wrong. A test that fires only on the submission fires
*because of* the flagged branch. Keep those; drop the rest.

Zero model calls: suites come from the `ut-*` runs, controls from `ab-22`, inputs from `trig-22`.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from pipeline.data import Dataset
from pipeline.sandbox import Isolation, run_raw

ARMS = ("ut-with-plain_v2", "ut-without-property")
OUT = "runs/ab-22/suite_filter.json"
SANDBOX_SECONDS = 240
IMAGE = "python:3.12-slim"
WORKERS = 6


def load(path):
    return [json.loads(line) for line in open(path)]


def catches_on(task, code, tests_src, space):
    """`{(test_name, input_index)}` the suite fires on, or None if the grid did not complete."""
    result = run_raw(task, code, tests_src, list(space), timeout_s=SANDBOX_SECONDS,
                     isolation=Isolation.DOCKER, docker_image=IMAGE)
    if not result["ok"] or not result["complete"]:
        return None
    return {(r["prop"], r["i"]) for r in result["records"] if r["outcome"] == "catch"}


def one(data, trig, control, arm, record):
    cid = record["candidate_id"]
    task = data.task(record["task_id"])
    space = trig.get(cid, {}).get("inputs") or []
    row = {"arm": arm, "candidate_id": cid, "split": record["split"],
           "is_attack": record["is_attack"],
           "submission_catches": len({c["test"] for c in record["catches"]}),
           "has_control": cid in control}
    if not row["has_control"] or not space:
        return row
    on_control = catches_on(task, control[cid], record["tests_src"], space)
    if on_control is None:
        row["error"] = "control grid did not complete"
        return row
    fired = {(c["test"], c["input_index"]) for c in record["catches"]}
    survivors = fired - on_control
    row["surviving_pairs"] = len(survivors)
    row["surviving_tests"] = len({t for t, _ in survivors})
    row["dropped_pairs"] = len(fired & on_control)
    return row


def main():
    data = Dataset.load("data/apps_hard.json")
    trig = {r["candidate_id"]: r for r in load("runs/trig-22/records.jsonl")}
    control = {r["candidate_id"]: r["control"]
               for r in load("runs/ab-22/records.jsonl") if r["control"]}
    jobs = [(arm, r) for arm in ARMS for r in load(f"runs/{arm}/records.jsonl")
            if not r["failed"] and r["catches"]]
    print(f"{len(jobs)} fired suites to re-run against their control", flush=True)
    with ThreadPoolExecutor(WORKERS) as pool:
        rows = list(pool.map(lambda j: one(data, trig, control, *j), jobs))
    json.dump(rows, open(OUT, "w"), indent=1)
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
