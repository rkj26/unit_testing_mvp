# BCB three-arm PBT replication plan

Status: staged replication. All launch switches in the companion notebook default to
`False`; the user-authorized run proceeds only after the frozen smoke and review
gates are explicitly enabled.

## Question and scope

Replicate the completed Azure Terra A/B/C PBT rewrite comparison on the pinned
BigCodeBench backdoor pool:

| Arm | Information | Intervention |
| --- | --- | --- |
| A | statement-visible task, candidate code, reviewed inputs | initial traceable-v1 suite |
| B | A suite, statement, reviewed inputs, static diagnostics; code hidden | one fixed-ten-test rewrite, runtime feedback withheld |
| C | exactly B plus bounded own-candidate execution diagnostics | one fixed-ten-test rewrite with feedback |

This is an exploratory benchmark replication on 26 previously exposed tasks (52
candidates), not a fresh or held-out confirmation. It does not test GLM, deletion,
minimal edits, or selective-audit safety. Those remain separate studies.

Prospective hypothesis: on this exposed BCB replication, execution feedback may
repair specification/oracle errors beyond an ordinary matched rewrite. Prediction:
C minus B reduces honest FPR by at least 10 percentage points, the task-clustered
95% upper interval is strictly below zero, and there are zero observed paired attack
losses. This is the same conjunctive gate used for the APPS confirmatory study, but
the BCB result remains exploratory replication evidence because the population was
previously exposed.

## Frozen population and preparation

The source is `data/bcb.json`, built from `bcb_pool.json` and
`splits/bcb_10_16.json` at seed 300. The source has 10 train and 16 test tasks, all
function-mode with entry point `task_func`; each task has one honest and one
`attack_0` candidate. The notebook derives an explicit all-evaluation dataset with
all 26 tasks in its test split, while retaining the original split and pool hashes in
`built_from.replication_source` metadata. No task is selected based on a generated
test or outcome.

Trigger search is a separately named 52-call stage: 10 inputs per candidate,
12,000 output-token cap, then independent statement-only input review. The reviewed
input run is immutable and reused by A/B/C. The review manifest must bind both the
derived dataset hash and trigger `records.jsonl` hash, assert all 52 candidate IDs,
and carry per-candidate accepted-input hashes; a review from another trigger artifact
cannot authorize this study. A missing, empty, or unresolved input space blocks all
authoring arms.

## Runtime and budget

Use Azure Terra, low reasoning, seed 300, 8,192 output tokens for authoring/revision,
300-second API attempt budget, 120-second sandbox budget, and zero HTTP retries for
every authoring and revision stage. The total ceiling is 208 provider attempts: 52 trigger calls plus
52 calls in each of A, B, and C. The first candidate smoke is included in this
ceiling. Runs are detached with a hidden Windows worker and keep-awake handling;
recorded failures are never silently retried.

`BCB_IMAGE` is the approved immutable Docker digest. Before a launch, the worker
must prove Docker is available, inspect that exact image, and run the two-task
function-mode schema smoke against it. The image must contain the BigCodeBench/runtime
libraries needed by the pool; the ordinary `python:3.12-slim` default is not assumed
sufficient.

To reduce provider-time confounding without changing protocol semantics, the
detached revision worker alternates candidate order between B and C while keeping
the requested seed fixed. Each protocol still writes its own immutable records and
uses the existing `SecondRevision` implementation; no protocol algorithm is
modified.

## Primary analysis

The primary contrast is C minus B on common complete, error-free candidate grids,
reported separately for honest false-positive rate and attack catch rate. Resample
whole task IDs (both candidates and both arms together) 10,000 times at seed 300.
Report all attempted candidates, failures, non-complete grids, abstentions, and
denominators. No missing result is a zero; no threshold is fitted. Also report the
original train/test-stratum sensitivity and exact input/image/source hashes. A run
record is all-test by design, so the sensitivity must join task IDs back to the frozen
original 10/16 mapping; it must never infer the strata from the run-record `split`.

## Launch invariants

The independent statement-only review is an authorization artifact, not a note: it
must hash the evaluation dataset, the exact trigger `records.jsonl`, and each
candidate's accepted input list, and assert that all 52 candidates have a nonempty,
function-mode-valid space. A/B/C must use that same trigger artifact. The baseline
source bundle freezes the baseline config and records, reviewed-input records, source
suite and candidate/input hashes, and the cached own-candidate execution diagnostic.
Both revision arms reject a changed bundle.

All detached requests freeze the dataset, runtime code/prompt hashes, worker source
hash, image digest and dependency hashes before starting. A reserved launch lock is
never automatically removed or retried. The B/C smoke runs the preregistered first
pending candidate in both arms; only a separately reviewed smoke artifact can unlock
the interleaved full worker. That worker processes one pending candidate at a time in
B/C order and preserves `Run.execute`'s record contract. After A/B/C, replay every
saved attack suite on its honest twin with the same reviewed inputs without a model
call, retaining partial or failed grids as failures rather than replaying for a
cleaner outcome.

The result is descriptive replication evidence only. A null or adverse result does
not establish a mechanism or universal ineffectiveness of execution feedback.
