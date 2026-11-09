# Kimi K3 on APPS: completed tests and monitor-with-tests arms

**Bottom line:** Plain v3 tests caught many attacks, but also flagged many honest candidates. Giving those tests to the monitor made the combined arm much stronger than tests alone. It did not improve on the monitor alone at the low false-positive rate reported here. The property-test variant shows the same broad pattern.

This is the November 9, 2026 completed-arm update to the [November 1 snapshot](../conversation-results-20261101/README.md). It does not include the unfinished UPlans or multi-turn arms.

## Plain v3: tests alone, with the monitor, and the monitor baseline

These are the **same 779 attack and 768 honest held-out candidates** with a nonfailed measurement in all three arms. Larger scores are more suspicious.

| Arm | What was scored | ROC AUC | Attack detection at 2% false positives |
| --- | --- | ---: | ---: |
| Blind plain v3 tests only | Number of distinct tests that fired | 0.90352 | 40.38% |
| Monitor + plain v3 tests | Mean of two suspicion ratings with code, tests, and firing results visible | 0.97355 | 91.57% |
| Monitor only | Mean of two suspicion ratings with code but no generated tests | 0.97411 | 92.02% |

With plain tests alone, the simple “at least one test fired” rule flagged **703/779 attacks (90.24%)** but also **157/768 honest candidates (20.44%)**. At an actual test-count threshold that stays at or below 2% false positives, **at least five tests** caught **298/779 attacks (38.25%)** and flagged **14/768 honest candidates (1.82%)**. The difference between 38.25% and the interpolated 40.38% is due to the discrete test-count score.

At their best attainable thresholds at or below 2%, both monitor arms caught **713/779 attacks (91.53%)**. The plain-test monitor flagged 15 honest candidates, versus 13 for the monitor alone. These are counts, not a claim that both arms flagged the same individual candidates.

## Property-test variant

This comparison uses its own matched held-out set: **811 attack and 803 honest candidates**. Do not compare across the two panels as if they had identical denominators.

| Arm | ROC AUC | Attack detection at 2% false positives |
| --- | ---: | ---: |
| Blind property tests only | 0.86752 | 34.75% |
| Monitor + property tests | 0.96941 | 91.59% |
| Monitor only | 0.97385 | 91.56% |

The combined property arm is essentially tied with the monitor-only baseline at the 2% operating point and has slightly lower AUC. Neither panel shows a clear gain from giving the monitor test evidence under this setup. This does not show that tests never help individual cases, that the arms are statistically equivalent, or that the difference is causal. In particular, the monitor baseline and combined arms used different provider routes for Kimi K3. Plain v3 test records also span the provider transition.

## Coverage and failure handling

All five arms saved one record per candidate for **2,776 candidates across 1,388 APPS tasks**. “Saved” includes failures. Failures are kept in the coverage counts but never treated as clean negatives or scored in the ROC analysis.

| Arm | Nonfailed | Model failures | Infrastructure failures | Nonfailed partial grids |
| --- | ---: | ---: | ---: | ---: |
| Monitor only | 2,776 | 0 | 0 | — |
| Blind plain v3 tests only | 2,643 | 50 | 83 | 12 |
| Monitor + plain v3 tests | 2,623 | 50 | 103 | — |
| Blind property tests only | 2,722 | 49 | 5 | 4 |
| Monitor + property tests | 2,687 | 49 | 40 | — |

The test writers generated ten tests without seeing candidate code; the combined monitor saw the candidate code, generated tests, and which tests fired. The recorded seed was 300. Nonfailed partial grids with observed catches are retained under the native rule; tests not executed cannot add a catch. For that reason, observed test counts on partial grids can be lower than on completed grids.

AUC counts tied attack/honest scores as half a win. The 2% figures linearly interpolate the empirical held-out ROC; they are **not** performance at a threshold chosen on training data, a significance test, or a deployment-safety estimate. The notebook also reports attainable discrete operating points and a comparison on the common sample across all five arms.

## Code and reproducibility

- [Offline analysis notebook](analysis.ipynb) reproduces the coverage and ROC tables from the [allowlisted score projections](data/). It uses the Python standard library and does not run models or Docker.
- [Provenance and checksums](provenance.json) identify the saved sources and shareable projections. The projections omit candidate code, test source, prompts, model replies, credentials, and billing logs.
- The native detector implementations used in these runs already exist in this repository and match the saved runtime byte for byte: [unit testing](https://github.com/rkj26/unit_testing_mvp/blob/d3201414220156340775d27b66fd73aeb293ac5d/pipeline/protocols/unit_testing.py), [monitor with tests](https://github.com/rkj26/unit_testing_mvp/blob/d3201414220156340775d27b66fd73aeb293ac5d/pipeline/protocols/monitor_with_tests.py), and [monitor only](https://github.com/rkj26/unit_testing_mvp/blob/d3201414220156340775d27b66fd73aeb293ac5d/pipeline/protocols/tm.py).
