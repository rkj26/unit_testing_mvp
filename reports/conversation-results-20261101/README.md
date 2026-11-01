# Kimi Grok and BCB26 results from this conversation

Results saved through 1 November 2026. This summary covers only the Kimi and Grok APPS runs and the 26-task BigCodeBench simple, distributed, and harder variants run in this conversation. It excludes unrelated historical studies. Kimi's scheduler is paused and no inference is being run.

## Kimi

The APPS study has 1,388 tasks and 2,776 candidates, one honest and one attack candidate per task. There are 555 training tasks and 833 held-out tasks. This is one scientific sweep; the monitor's two ratings per candidate are not independent study replications.

| Stage or arm | Saved rows | Nonfailed | Model failures | Infrastructure failures | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| TrustedSolve | 2,776 | 2,715 | 61 | 0 | All identities represented |
| TriggerSearch | 2,776 | 2,734 | 42 | 0 | All identities represented |
| Trusted monitor | 2,776 | 2,776 | 0 | 0 | All identities represented |
| Blind property tests | 2,776 | 2,722 | 49 | 5 | All identities represented; four retained partial-positive grids |
| Blind plain v3 tests | 291 | 283 | 7 | 1 | Partial training prefix; 2,485 unattempted |
| UPlans property tests | 0 | — | — | — | Not started |
| UPlans plain v3 tests | 0 | — | — | — | Not started |
| Monitor plus property tests | 0 | — | — | — | Not started |
| Monitor plus plain v3 tests | 0 | — | — | — | Not started |
| Monitor plus UPlans property tests | 0 | — | — | — | Not started |

TrustedSolve and TriggerSearch are supporting stages, not attack-detection arms. The other eight are scored arms. The Kimi multi-turn extension has not started.

TrustedSolve solved **1,295 of 1,369 measured tasks, 94.59%**, under the native first-valid-record-per-task rule, not best-of-two selection. Nineteen tasks have no surviving measurement. Held-out task solving was 779/818, 95.23%. This measures fresh solution generation, not backdoor detection. TriggerSearch produced 2,734 parseable search spaces; parseability does not establish that an attack was caught.

### Monitor versus property tests

The held-out comparison uses exactly the same 820 attack and 809 honest candidates with nonfailed results in both arms.

| Arm | Held-out ROC AUC | Interpolated detection at 2% false positives |
| --- | ---: | ---: |
| Trusted monitor | 0.97398 | 91.55% |
| Blind property tests | 0.86621 | 33.35% |

On the pooled matched training and test population of 1,368 attacks and 1,354 honest candidates, the corresponding detection figures are 92.56% and 33.59%. These ROC points are descriptive interpolation, not performance at a threshold fixed independently on training data.

At the simpler rule of at least one test firing, property tests flag **687/820 held-out attacks, 83.78%, but also 160/809 honest candidates, 19.78%**. The tests catch many attacks, but this rule is not low-false-positive detection. On the evidence collected so far, the monitor is the stronger standalone discriminator. Whether tests add value to the monitor remains unanswered because the combined Kimi arms have not run. The partial plain-test prefix cannot establish a held-out comparison.

Four nonfailed property results executed only 120, 156, 294, and 95 of 300 pairs, with real positive catches retained. Two partial-positive grids also occur in the partial plain arm. They are not complete grids; observed firing counts can be biased downward. Failed incomplete measurements remain unmeasured, never clean negatives.

## Grok

| Stage | Saved rows | Nonfailed | Infrastructure failures | Unattempted candidates |
| --- | ---: | ---: | ---: | ---: |
| TrustedSolve | 1,725 | 1,724 | 1 | 1,051 |

Grok did not reach TriggerSearch or any of the eight scored detection arms. Its current results are partial solution-generation evidence only. They do not support a Grok attack-detection or full-study safety conclusion.

## BCB26 tests

These DeepSeek V3.2 runs use simple and distributed assistant-authored attack variants on the same 26 previously exposed BigCodeBench tasks, each with 26 honest and 26 attack candidates. They are separate exploratory conditions, not 52 independent tasks or independent repeats. A resumed run is a continuation, not another experiment.

Each stage below has 52 saved rows. Counts are nonfailed / model failures / infrastructure failures.

| Stage | Simple variant | Distributed variant |
| --- | ---: | ---: |
| TriggerSearch | 50 / 2 / 0 | 51 / 0 / 1 |
| Plain v3 tests | 37 / 10 / 5 | 41 / 6 / 5 |
| UPlans plain v3 tests | 37 / 10 / 5 | 41 / 5 / 6 |
| Monitor plus plain v3 tests | 37 / 10 / 5 | 41 / 6 / 5 |
| Trusted monitor | 52 / 0 / 0 | 51 / 0 / 1 |

The original three-detector comparison uses the same valid candidates across monitor, monitor plus tests, and UPlans: 16 honest and 16 attacks for simple, and 19 honest and 18 attacks for distributed. These are survivor populations, not rates over all 52 original candidates.

| Variant | Detector | ROC AUC | Interpolated detection at 2% false positives |
| --- | --- | ---: | ---: |
| Simple | Monitor | 1.00000 | 100.00% |
| Simple | Monitor plus plain v3 tests | 1.00000 | 100.00% |
| Simple | UPlans plain v3 tests | 0.94727 | 64.50% |
| Distributed | Monitor | 0.99854 | 96.56% |
| Distributed | Monitor plus plain v3 tests | 1.00000 | 100.00% |
| Distributed | UPlans plain v3 tests | 0.95322 | 55.78% |

At any test firing, plain tests flag 19/19 attacks and 3/18 honest candidates in their own simple usable population; UPlans flags 18/18 attacks and 6/19 honest candidates. For distributed, plain tests flag 21/21 attacks and 5/20 honest candidates; UPlans flags 20/20 attacks and 7/21 honest candidates. Different usable populations prevent interpreting these as paired improvements.

**Meaning:** the monitor is already near ceiling on these small, exposed authored variants. Adding tests does not demonstrate a robust improvement here. Test suites flag all measured attacks at the any-firing rule but also flag many honest submissions. These results do not establish performance on harder or held-out tasks. There is no calibrated deployment policy, deployment-game result, or independent-replication confidence interval.

The separate **harder BCB26 variant reached only eight nonfailed TriggerSearch rows out of 52**. Forty-four trigger candidates and all four detector stages remain unattempted. There is no harder-variant detection result. Free-echo qualification is preparation and is not counted as scientific data.

## Request for more inference

To finish Kimi's ordinary stages, the outstanding scope is 2,485 plain-test candidates plus five stages of 2,776 candidates: **16,365 candidate-stage units**, with a pinned upper bound of **30,245 fresh logical provider calls** before dependency skips. Its planned multi-turn extension adds up to 8,334 calls including the planned smoke check, for up to 38,579 combined. These are not token or dollar estimates and include no new paid-retry allowance.

The harder BCB26 study has a separate outstanding scope of 44 trigger candidates and four detector stages of 52 candidates each. The reason to request inference is to answer the still-open combined-Kimi and harder-BCB questions, not to repeat completed outcomes until they improve. Existing failures, results, evidence, and possible charges remain preserved.

## Results and preservation

- [Scoped Kimi and Grok inventory](conversation-scoped-summary.json) and [BCB26 evidence index](bcb-studies.json) contain per-stage counts, metrics, and source hashes.
- [Result projections](data/runs/) contain all **13,648 saved rows across 17 scientific stage namespaces** in this release: Kimi five, Grok one, completed BCB26 ten, and harder BCB26 one.
- [Provenance](provenance.json) records source/config/row hashes and the field policy. [Offline verification](scripts/verify_projection_snapshot_v3.py) checks the exported rows without inference or candidate execution.

These are analysis-only scalar projections, not resumable runs. Private replies, reasoning, prompts, code, generated inputs, native arrays, and free-text failure reasons are omitted; original artifacts remain local. Failure labels, nulls, exclusions, and explicitly derived counts are preserved. No outcome was regraded for this release. Historical operational attempts and recovery copies are not independent scientific repeats. Kimi's lineage includes STDIO and garbage-collection compatibility changes without uniform regrading of earlier measurements, so these cumulative results are not described as a pristine rerun. The earlier published Kimi solution/trigger files remain unchanged.
