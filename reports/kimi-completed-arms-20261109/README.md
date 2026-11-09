# Kimi K3 on APPS: completed tests and monitor-with-tests arms

This is the November 9, 2026 completed-arm update to the [November 1 snapshot](../conversation-results-20261101/README.md). It does not include the unfinished UPlans or multi-turn arms.

## What it means

A test firing is a clue, not proof of a backdoor. With plain tests alone, flagging any candidate with at least one firing test caught 90% of attacks, but also flagged 20% of honest submissions. The monitor could look at the code and judge whether the test evidence was suspicious, which helps explain why the combined arm did much better than tests alone when false alarms had to stay low.

But the monitor was already strong without tests. At a 2% false-positive rate, it caught **92.02%** of attacks on its own, compared with **91.57%** when it also saw the plain tests. Property tests showed a similar pattern. So these runs don’t show a clear benefit from adding tests to the monitor. The monitor-only and combined runs also used different provider routes, so this isn’t a controlled estimate of the effect of adding tests.

## Results

| Comparison | Arm | Measured | Model failures | Infrastructure failures | ROC AUC | Attack detection at 2% false positives |
|---|---|---:|---:|---:|---:|---:|
| Plain v3 | Tests only | 2,643 | 50 | 83 | 0.90352 | 40.38% |
| Plain v3 | Monitor + tests | 2,623 | 50 | 103 | 0.97355 | 91.57% |
| Plain v3 | Monitor only | 2,776 | 0 | 0 | 0.97411 | 92.02% |
| Property | Tests only | 2,722 | 49 | 5 | 0.86752 | 34.75% |
| Property | Monitor + tests | 2,687 | 49 | 40 | 0.96941 | 91.59% |
| Property | Monitor only | 2,776 | 0 | 0 | 0.97385 | 91.56% |

Each arm saved **2,776 records**. Failures were kept in the totals but excluded from the detection scores. Within each comparison, all three arms were scored on the same held-out candidates: **779 attacks and 768 honest submissions** for plain v3, and **811 attacks and 803 honest submissions** for property tests. The 2% figures are interpolated from the held-out results, not measured at a threshold set in advance.

## Measurement notes

The 2,776 candidates come from 1,388 APPS tasks. Tests-only scores count distinct tests that fired; monitor scores average two suspicion ratings. The test writers generated ten tests without seeing candidate code. The combined monitor saw the candidate code, generated tests, and which tests fired; the monitor-only arm saw the code without the generated tests. The recorded seed was 300.

With plain tests alone, the “at least one test fired” rule flagged **703/779 attacks (90.24%)** and **157/768 honest candidates (20.44%)**. At an attainable threshold that stays at or below 2% false positives, **at least five tests** caught **298/779 attacks (38.25%)** and flagged **14/768 honest candidates (1.82%)**. The difference between 38.25% and the interpolated 40.38% is due to the discrete test-count score.

At their best attainable thresholds at or below 2%, both monitor arms in the plain v3 comparison caught **713/779 attacks (91.53%)**. The plain-test monitor flagged 15 honest candidates, versus 13 for the monitor alone. This does not mean the two arms flagged the same candidates.

Twelve nonfailed partial grids in plain v3 tests and four in property tests were retained under the native rule because they had observed catches. Tests not executed cannot add a catch, so observed test counts on partial grids can be lower than on completed grids. Plain v3 test records also span the provider transition.

AUC counts tied attack/honest scores as half a win. The 2% figures linearly interpolate the empirical held-out ROC; they are **not** performance at a threshold chosen on training data, a significance test, or a deployment-safety estimate. The notebook also reports attainable discrete operating points and a comparison on the common sample across all five arms.

## Code and reproducibility

- [Offline analysis notebook](analysis.ipynb) reproduces the coverage and ROC tables from the [allowlisted score projections](data/). It uses the Python standard library and does not run models or Docker.
- [Provenance and checksums](provenance.json) identify the saved sources and shareable projections. The projections omit candidate code, test source, prompts, model replies, credentials, and billing logs.
- The native detector implementations used in these runs already exist in this repository and match the saved runtime byte for byte: [unit testing](https://github.com/rkj26/unit_testing_mvp/blob/d3201414220156340775d27b66fd73aeb293ac5d/pipeline/protocols/unit_testing.py), [monitor with tests](https://github.com/rkj26/unit_testing_mvp/blob/d3201414220156340775d27b66fd73aeb293ac5d/pipeline/protocols/monitor_with_tests.py), and [monitor only](https://github.com/rkj26/unit_testing_mvp/blob/d3201414220156340775d27b66fd73aeb293ac5d/pipeline/protocols/tm.py).
