# PBT design assessment: deletion intent versus implemented revisions

## Bottom line

The current revision protocols implement **replacement-suite rewriting**, not a
deletion or minimal-edit intervention. `TestRepair` and `SecondRevision` ask the
model for a new JSON suite containing exactly ten named `test_name(run, x)`
functions. The parser validates the returned suite structurally, but does not match
tests to the original suite or require any test to survive. A change in catch rate
therefore combines deletion, replacement, oracle changes, and newly generated tests.

That is a legitimate question, but it is not the narrower question suggested by an
original intent of “delete the offending assertion/branch and measure what remains.”
The existing code should be described as a rewrite study wherever it is cited.

The explanatory provenance comments for the frozen runs live in the two analysis
notebooks (`azure_pbt_multiturn_confirmatory.ipynb` and `azure_pbt_multiturn.ipynb`).
They are intentionally kept out of `pipeline/*.py`: the frozen manifests hash those
source files, including docstrings, so changing them would invalidate cached-study
provenance without changing any measured behavior.

## What the code actually compares

`SecondRevision` is the completed fresh holdout design's matched A/B/C setup:

- A is the saved initial one-turn authoring run. It saw candidate code.
- B gets A's suite, fixed inputs, the task statement, and static parser/test-count
  information, but runtime diagnostics are withheld.
- C gets exactly B's information plus bounded own-candidate execution counts and
  indexed outcome events.

B and C each make one additional call using the same prompt template and the same
  fixed-ten-test schema. `execution_diagnostics` is the intended B→C intervention;
  the prompt does not contain an edit script, deletion mask, or identity mapping to
  preserve individual A tests. `TestRepair` is the older training-only feedback
  rewrite and must remain a separate historical arm/artifact.

The source prompt is explicit about this contract: it says “return exactly 10”
tests, permits whole-suite abstention, and requires one direct `run(x)` call per
test. `parse_repair` enforces the count and basic shape. Its conservative
non-vacuity checks are valuable safeguards, but they cannot prove semantic
usefulness, assertion reach, or test preservation.

## What the completed study supports

The completed confirmatory report is
[`azure_pbt_multiturn_confirmatory_results_2026-09-14.md`](azure_pbt_multiturn_confirmatory_results_2026-09-14.md).
On its 30-task fresh holdout, C versus B produced 5/28 versus 4/28 honest false
positives and 25/30 versus 26/30 attack catches. The paired intervals included zero
and the preregistered improvement gate was not met. This is evidence that this
particular one-call feedback-visible rewrite did not deliver the required
improvement on this sample.

It is not evidence that execution feedback is universally ineffective or harmful,
and it does not identify a mechanism. A null or adverse result from a replacement
suite can arise from ordinary extra-call variation, changed assertions, oracle
rewrites, task dependence, or the feedback representation. The report also notes
that B and C were run sequentially rather than interleaved, so provider/time effects
remain possible.

The earlier training-only `TestRepair` result is exploratory and lacks the matched
feedback-free second-generation control needed to isolate feedback from simply
generating again. It should not be presented as a deletion result or pooled with the
fresh holdout estimate.

## Recommended next study

If the scientific target is deletion, run a **distinct, preregistered deletion
study**, coordinated with Palak, rather than relabeling these rewrite artifacts.
Freeze the original suite and give each test a stable ID. Require the intervention
to return only the IDs of whole tests to retain, enforce that these are a subset of
the original IDs, and preserve the retained source bytes exactly. Do not allow
rewriting, replacement, or assertion removal inside surviving tests. Record which
tests survived. Use the same fixed inputs, sandbox, labels, and paired
eligibility rules across deletion and its control. Include an edit-free control that
spends the same additional call budget if a model is involved, and independently
check honest-twin specificity. An empty retained suite is abstention with zero
coverage, not successful repair. Report retained-test counts, attack losses and
whole-suite honest-twin specificity alongside FPR: deleting tests can mechanically
lower FPR while making detection worse. Analyze deletion, replacement, and
abstention as distinct outcomes. Interleave or randomize revision-arm order to
reduce the time/provider confound present in the completed study. Keep honest-twin
evaluation results out of own-candidate feedback, unless explicitly studying a
separate oracle-information condition.

This should be a new run family and report with its own hashes and estimand. It
should not overwrite or reinterpret the saved A/B/C records. BCB and GLM remain
separate replication questions: they should use independently frozen populations and
protocol manifests, rather than being treated as additional evidence for the APPS
rewrite mechanism.
