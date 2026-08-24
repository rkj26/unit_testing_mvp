"""Is ablation limited by the edit or by the probes?

For every test candidate whose control survived the provided-pair guard, replay the differential
against two wider input sets: the attack's own `secret_input` (the oracle -- if the control diverges
there, the right branch was removed and only probe generation failed) and the 29 inputs
`trig-22` already paid for. Zero model calls; Docker only.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from pipeline.data import Dataset
from pipeline.protocols.ablation import _ECHO_PROPERTY
from pipeline.sandbox import Isolation, run_raw

SPLIT = "train"
OUT = f"runs/ab-22/probe_ceiling_{SPLIT}.json"
SANDBOX_SECONDS = 180
IMAGE = "python:3.12-slim"
WORKERS = 6


def load(path):
    return [json.loads(line) for line in open(path)]


def digests(task, code, space):
    result = run_raw(task, code, _ECHO_PROPERTY, list(space), timeout_s=SANDBOX_SECONDS,
                     isolation=Isolation.DOCKER, docker_image=IMAGE)
    if not result["ok"] or not result["complete"]:
        return None
    return {r["i"]: r.get("msg", "") for r in result["records"]}


def one(data, trig, record):
    task = data.task(record["task_id"])
    candidate = next(c for c in task.candidates if c.candidate_id == record["candidate_id"])
    secret = [candidate.secret_input] if candidate.secret_input else []
    triggers = trig.get(record["candidate_id"], {}).get("inputs") or []
    space = secret + list(triggers)
    if not space:
        return None
    submitted = digests(task, candidate.code, space)
    control = digests(task, record["control"], space)
    if submitted is None or control is None:
        return {"candidate_id": record["candidate_id"], "is_attack": record["is_attack"],
                "error": "grid did not complete"}
    differs = [i for i in range(len(space)) if submitted.get(i) != control.get(i)]
    return {
        "candidate_id": record["candidate_id"], "is_attack": record["is_attack"],
        "already_flagged": record["flagged"], "n_probes": len(space),
        "secret_diverges": bool(secret) and 0 in differs,
        "trigger_diverges": sum(1 for i in differs if i >= len(secret)),
        "n_triggers": len(triggers),
    }


def main():
    data = Dataset.load("data/apps_hard.json")
    trig = {r["candidate_id"]: r for r in load("runs/trig-22/records.jsonl")}
    todo = [r for r in load("runs/ab-22/records.jsonl")
            if r["split"] == SPLIT and not r["failed"] and r["control"]]
    print(f"{len(todo)} controls to replay", flush=True)
    with ThreadPoolExecutor(WORKERS) as pool:
        rows = [r for r in pool.map(lambda r: one(data, trig, r), todo) if r]
    json.dump(rows, open(OUT, "w"), indent=1)
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
