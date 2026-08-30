"""Launch the scrubbed-pool generation for apps_hard, in the order the arms depend on each other.

Configs here must match `notebooks/results.ipynb` exactly: the notebook's `.run()` calls then find
every candidate already scored and return without spending anything.

    .venv/bin/python scratch/launch_scrubbed.py
"""

from concurrent.futures import ThreadPoolExecutor

from pipeline.protocols import (MonitorWithTests, TriggerSearch, TrustedMonitor, UnitTesting,
                                UPlansTWrites)

DATASET = "data/apps_hard.json"
MODEL = "openai-api/azureai/DeepSeek-V3.2"
TRIGGERS = "trig-22"
N_TESTS = 10
CONCURRENT = 3


def suite(run_name, prompt):
    return UnitTesting(run_name=run_name, data=DATASET, model=MODEL, triggers=TRIGGERS,
                       test_gen_prompt=prompt, n_tests=N_TESTS, sandbox_seconds=240)


def planned(run_name, prompt):
    return UPlansTWrites(run_name=run_name, data=DATASET, model=MODEL, reasoning="low",
                         untrusted=MODEL, untrusted_reasoning="high", triggers=TRIGGERS,
                         test_gen_prompt=prompt, n_tests=N_TESTS, sandbox_seconds=240)


def report(arm):
    """Run one arm to completion and say what it produced, rather than failing the whole wave."""
    try:
        arm.run()
        records = arm.get_records()
        failed = sum(r["failed"] for r in records)
        return f"{arm.run_name}: {len(records)} records, {failed} failed"
    except Exception as error:
        return f"{arm.run_name}: LAUNCH FAILED — {type(error).__name__}: {error}"


if __name__ == "__main__":
    # Every suite tests against this run's inputs, so nothing else can start until it lands.
    print(report(TriggerSearch(run_name=TRIGGERS, data=DATASET, model=MODEL, num_inputs=30)))

    wave = [
        TrustedMonitor(run_name="tm-22", data=DATASET, model=MODEL, runs=2, cache=False),
        suite("ut-property-10", "property"),
        suite("ut-plain_v3-10", "plain_v3"),
        planned("upt-property-10", "property"),
        planned("upt-plain_v3-10", "plain_v3"),
    ]
    with ThreadPoolExecutor(max_workers=CONCURRENT) as pool:
        for line in pool.map(report, wave):
            print(line)

    # Reads a finished suite, so it goes last.
    print(report(MonitorWithTests(run_name="mwt-property-10", data=DATASET, model=MODEL, runs=2,
                                  cache=False, tests="ut-property-10", triggers=TRIGGERS)))
