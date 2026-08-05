# Parked, not deleted

Validated work that nothing on the run path imports. Kept because re-deriving it would cost real
effort, moved here so it stays out of review sweeps and test runs.

## `scorer_corrected.py` (+ `test_scorer_corrected.py`, 19 tests)

`CorrectedBigCodeBenchSetting` — a hybrid semantic-equality grader for BigCodeBench side tasks.

**Why it is not in use.** `pipeline/backends/bcb.py` uses control_arena's stock
`BigCodeBenchSetting`, having verified stock == corrected == ground truth against the pool's
recorded `official_validation`. The project rule is "use control_arena where it is right, use
inspect where it is wrong" — BCB is the right case. APPS is the wrong case, and its correction
(`CorrectedAppsSetting`) lives in `pipeline/scoring.py` because it *is* on the run path.

**When to bring it back.** If the stock side-task comparison misjudges complex outputs — DataFrames,
dicts, multi-line text — on the full BCB pool. Drop-in: import it in `bcb.py` and swap the setting.

Note: DeepDiff was evaluated for this and rejected; do not re-propose it.

To run its tests: `.venv/bin/python -m pytest unused/test_scorer_corrected.py`
