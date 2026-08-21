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

## Before writing a loader, adapter or parser

**Search `pipeline/` for the abstraction before writing the second one.** If two functions would
answer the same question, there is one function.

`probe.py` wrote an APPS-only loader while `schema.Backend` already normalised both benchmarks. The
cost was not the duplicated lines — it was that BigCodeBench stopped being a flag and became a
refactor, discovered only when someone asked for it.

**"Deliberately outside `pipeline/`" is a decision with a bill.** Sometimes right; write down what
it will cost, in the module docstring, so the bill arrives visibly rather than as a surprise.

## Where a change goes

**A new measurement is a flag on the harness, never a new script.** The repo accumulated
`regrade.py`, `reaggregate.py`, `sweep_table.py`, `poll.py`, `differential_sim.py` and
`solve_rate.py` — six entry points that each re-derived a number the pipeline already computed, then
drifted from it. They were deleted on 2026-08-18 and do not come back.

- A new arm is a value in an existing `choices=` list (`--resolve`, `--code`), not a new entry point.
- A new score is a field on the artifact, written by the code that already writes the artifact.
- A rescoring reads `runs/<id>/` and writes back into `runs/<id>/`, as a flag on the tool that made
  the run — never as a sibling script that reimplements the read.
- If two entry points would compute the same number, there is one entry point.

The test: could a later run need this? Then it is a flag. Only a genuinely single-use diagnostic —
one question, one answer, discarded the same day — belongs outside the harness, and it goes in a
notebook, not a `.py` at the repo root.

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
.venv/bin/python probe.py --run-id smoke3 --pool apps_pool_hard10.json \
    --split splits/smoke_3.json --runs 2 --tests 3 --inputs 10   # 24 calls, ~4 min
```

The old `run.py --domain mock --mock` determinism check went with the orchestrator it belonged to.
The smoke run above is the replacement: it is cheap, it exercises both model paths and docker, and
`--run-id` resumes it. It is not deterministic, so compare shapes — every candidate reaching a
verdict, suites written under `run_0/` and `run_1/` — not exact numbers.

## Two modules, one experiment

`probe.py` runs an arm and costs money. `audit.py` reads a finished run and cannot change one.
Nothing in a notebook should import `probe` except to launch. See `DOCUMENTATION.md` for the full
surface of both.

## Launching a run

- **Detached, always.** A run goes into tmux and writes to `runs/<run-id>/`:

  ```
  tmux new-session -d -s <run-id> '.venv/bin/python -u audit_probe.py --run-id <run-id> ... 2>&1 | tee runs/<run-id>/console.log'
  tmux capture-pane -pt <run-id> | tail -20     # check on it without attaching
  ```

  `-u` is not optional. Piped into `tee`, Python block-buffers stdout and the log stays empty for
  the whole run, which reads exactly like a hung job.

  Nothing that takes more than a minute runs in a foreground shell, an agent tool call, or a
  notebook cell. All three die with their session and take the run with them.
- `--run-id` resumes. A killed run costs at most one in-flight call.
- The machine must not sleep mid-run (`run.py` holds a `caffeinate` assertion on darwin). tmux does
  not prevent sleep; `caffeinate` does. Both are needed.
- Diagnose in this order: `status.json` heartbeat → artifact counts → the log **last**. The log lied
  to us for an hour once; the artifacts never have.
- Attacks written by a human or by Claude are a **different distribution** from attacks sampled from
  an untrusted policy. Never pool them; they answer different questions.

## Notebooks

A notebook **reads artifacts; it never produces a number.** Every figure in it loads from
`runs/<id>/*.json` and plots. None is computed in a cell.

This follows from verifying against the artifact. A number computed in a cell has no run id, no
config, and no record of which cells ran in what order, so it cannot be re-derived and cannot be
cited. Out-of-order execution has already cost this project one retracted correlation.

- **Explore in the notebook; graduate what gets reported.** Pivots, groupings and plots belong in
  cells, where they are fastest. The moment a number goes on a slide or into a report it moves into
  `analyse_probes.py` and is *called* from the cell, so it has a name, a test, and can be recomputed
  from a run id by someone who never opens this notebook. Statistics always go through
  scipy/sklearn — hand-rolling them here is how a partial-AUC figure was silently wrong once already.
- `%load_ext autoreload` in the setup cell, so editing the harness needs no kernel restart. Friction
  is not a reason to redefine a metric in a cell.
- A notebook may **launch** a run but never **hosts** one. `pipeline/launch.py` starts it detached in
  tmux and returns in milliseconds. A cell that blocks on the run dies with the kernel and takes the
  run with it, so no `subprocess.run`, no `await`, no `asyncio.run` of an experiment in a cell.
- Restart-and-run-all must reproduce the whole notebook, or it is not evidence.
