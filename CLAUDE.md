# Working rules for this repo

Conventions that came out of real defects here. Each one exists because breaking it cost us
something. `CHANGELOG.md` is the operational log; `METRICS.md` defines every metric.

## The rule that matters most

**A failure must never silently become a value.**

Six separate bugs in this repo were the same shape: a measurement that did not happen, written down
as if it had — always as the falsy default, which always read as *"the model failed"*. That is the
direction that flatters our infrastructure and penalises the thing under study, which is backwards
for a project whose claim is about model capability.

- Never write `x or 0`, `.get(k, False)`, or a falsy default on any path that feeds a metric.
- Use `pipeline/outcome.py`: `Unknown(Blame.INFRA | Blame.MODEL, reason)`. Its `__bool__` raises, so
  `if unknown:` and `unknown or 0` fail loudly instead of lying.
- State blame **where the failure is detected**. Never infer it later from an error message — we did
  that, and it mislabelled every crash whose text lacked a marker word.
- Substituting a default must be spelled `known(x, default)` so it is visible in review.
- Every unknown must reach the report: `scoring_coverage`, `pbt_invalid_blame`.

## Code style

- **No inline comments.** Name things instead: a named constant rather than an annotated literal, a
  named function rather than an annotated block, a raised error rather than a warning comment. Short
  docstrings stating a contract are fine; running commentary is not. Provenance ("why 12 concurrent")
  goes in the constant name plus `CHANGELOG.md`.
- **No `None` in the config layer.** Every optional gets a real default. `""` for absent strings,
  `0` for "all", a fallback object rather than an optional one.
- **Reuse over hand-rolling.** Statistics go through scipy/sklearn, config through pydantic-settings.
  We hand-rolled ROC curves, a t-table, a bootstrap and Wilson intervals; one of them had a bug that
  silently misreported every partial-AUC figure.
- **Fail fast.** No defensive `.get()` on keys the config guarantees, no None-defaults on the compute
  path. Validate in `__post_init__` / `model_validator` and raise.
- **No abstraction with one implementation.** A Protocol with a single implementation that forwards
  to a function is ceremony; we deleted one that was threaded through eight signatures.

## Running an experiment

**Write the entry before the run, not after.** Every experiment gets an entry in the current
`reports/*-experiments.md` log, appended *before* the command is launched, with four fields:

```
### E<n> — <name>
**Setup.**      pool, n tasks, models, seed, budget — everything needed to re-run it.
**Change.**     the ONE thing different from the run above. If there is more than one, split it.
**Hypothesis.** what we expect and *why*, stated so it can be wrong.
**Prediction.** the number that decides it, with a threshold, written down first.
**Observed.**   filled in after. Verified against the artifact, never from memory.
```

Reasons this is not optional:

- A hypothesis written after seeing the number is not a hypothesis. A4's density correlation
  (+0.574) was formed on data already inspected and came back **−0.142 on held-out tasks**.
- Without a recorded **Change**, two runs cannot be compared. `apps-hard10` vs
  `apps-hard10-densesearch` is only interpretable because the configs happened to differ in one
  field, and the baseline's `run.json` predates `search_prompt` so even that is inferred.
- A **Prediction** with a threshold is what stops a null result from being retold as a positive one.
- One change per entry. Bundled changes cost us the ability to attribute anything.

State the headline metric in the same units across entries so the log reads as a series.

## Before claiming a result

- **Verify every number against the artifact.** Do not quote from memory or from a previous message.
  Read `metrics.json`.
- **Check n before interpreting.** Runs that abstained are dropped, so `n` can be below the run
  count. A "5-run" delta was actually n=4.
- **Report the mechanism, not just the delta.** `false_positive` is measured at a fixed threshold the
  deployment game never applies — it is descriptive only. What the audit rule spends is *rank*; see
  `honest_score_levels` and `tie_mass_at_top`.
- **Say when a threshold was fitted.** A number chosen by looking at the data is not evidence until
  it is validated on tasks it was not chosen on.
- **Check for tautology.** Ask what the metric would report if the effect were absent. A 0% false
  positive rate that arises because the filter mechanically removes every offender is not a finding.

## After changing anything

```
.venv/bin/python -m pytest -q                                   # must stay green
.venv/bin/python run.py --domain mock --mock --runs 2 --run-id smoke   # values must not move
```

Mock output is deterministic. If a refactor changes a number, that is a bug until proven otherwise.

## Running experiments

- `--run-id` resumes. A killed run costs at most one in-flight call.
- Diagnose in this order: `status.json` heartbeat → artifact counts → the log **last**. The log lied
  to us for an hour once; the artifacts never have.
- The machine must not sleep mid-run (`run.py` holds a `caffeinate` assertion on darwin).
- Attacks written by a human or by Claude are a **different distribution** from attacks sampled from
  an untrusted policy. Never pool them; they answer different questions.
