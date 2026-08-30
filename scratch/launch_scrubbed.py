"""Launch a scrubbed-pool generation, in the order the arms depend on each other.

    .venv/bin/python scratch/launch_scrubbed.py hard
    .venv/bin/python scratch/launch_scrubbed.py r50

Configs here must match `notebooks/results*.ipynb` exactly, including `sandbox_seconds`: the
notebook's own `.run()` calls then find every candidate already scored and spend nothing. The two
pools are launched with identical settings on purpose — random50 is meant to be a replication, and a
budget that differs between them is a difference nobody would remember by the time the numbers
disagree.
"""

import sys
from concurrent.futures import ThreadPoolExecutor

from pipeline.protocols import (MonitorWithTests, TriggerSearch, TrustedMonitor, UnitTesting,
                                UPlansTWrites)

MODEL = "openai-api/azureai/DeepSeek-V3.2"
N_TESTS = 10
SANDBOX_SECONDS = 240
TRIGGER_INPUTS = 30
CONCURRENT = 3

POOLS = {
    "hard": {"data": "data/apps_hard.json", "suffix": ""},
    "r50": {"data": "data/apps_random50.json", "suffix": "-r50"},
}


def names(suffix):
    """Run names for one pool. `-r50` sits after the protocol, as the earlier generation named it."""
    return {
        "triggers": f"trig{suffix or '-22'}",
        "monitor": f"tm{suffix or '-22'}",
        "suite": lambda prompt: f"ut{suffix}-{prompt}-{N_TESTS}",
        "planned": lambda prompt: f"upt{suffix}-{prompt}-{N_TESTS}",
        "hybrid": f"mwt{suffix}-property-{N_TESTS}",
    }


def report(arm):
    """Run one arm to completion and say what it produced, rather than failing the whole wave."""
    try:
        arm.run()
        records = arm.get_records()
        blame = {}
        for record in records:
            if record["failed"]:
                blame[record["blame"]] = blame.get(record["blame"], 0) + 1
        return f"{arm.run_name}: {len(records)} records, {sum(blame.values())} failed {blame}"
    except Exception as error:
        return f"{arm.run_name}: FAILED — {type(error).__name__}: {error}"


def main(pool):
    data = POOLS[pool]["data"]
    name = names(POOLS[pool]["suffix"])

    def suite(prompt):
        return UnitTesting(run_name=name["suite"](prompt), data=data, model=MODEL,
                           triggers=name["triggers"], test_gen_prompt=prompt, n_tests=N_TESTS,
                           sandbox_seconds=SANDBOX_SECONDS)

    def planned(prompt):
        return UPlansTWrites(run_name=name["planned"](prompt), data=data, model=MODEL,
                             reasoning="low", untrusted=MODEL, untrusted_reasoning="high",
                             triggers=name["triggers"], test_gen_prompt=prompt, n_tests=N_TESTS,
                             sandbox_seconds=SANDBOX_SECONDS)

    # Every suite is tested against this run's inputs, so nothing else can start until it lands.
    print(report(TriggerSearch(run_name=name["triggers"], data=data, model=MODEL,
                               num_inputs=TRIGGER_INPUTS)), flush=True)

    wave = [
        TrustedMonitor(run_name=name["monitor"], data=data, model=MODEL, runs=2, cache=False),
        suite("property"), suite("plain_v3"),
        planned("property"), planned("plain_v3"),
    ]
    with ThreadPoolExecutor(max_workers=CONCURRENT) as pool_of_arms:
        for line in pool_of_arms.map(report, wave):
            print(line, flush=True)

    # Reads a finished suite, so it goes last.
    print(report(MonitorWithTests(run_name=name["hybrid"], data=data, model=MODEL, runs=2,
                                  cache=False, tests=name["suite"]("property"),
                                  triggers=name["triggers"])), flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in POOLS:
        raise SystemExit(f"usage: launch_scrubbed.py {{{'|'.join(POOLS)}}}")
    main(sys.argv[1])
