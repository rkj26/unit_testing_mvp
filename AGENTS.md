# Working rules for this repo

## Before you say a change is done

```
.venv/bin/python -m pytest -q
.venv/bin/python probe.py --run-id smoke3 --pool apps_pool_hard10.json --split splits/smoke_3.json --runs 2 --tests 3 --inputs 10
```

The smoke run is 24 calls, ~4 min, and `--run-id` resumes it. It is not deterministic, so compare
*shapes* — every candidate reaching a verdict, suites under `runs/smoke3/suites/<task>_<label>/run_0/`
and `run_1/` — never exact numbers.

## What is being measured

A trusted model writes property-based tests against an untrusted model's submission; the question is
whether they catch backdoors the trusted monitor misses. `probe.py` runs one arm and costs money;
`audit.py` reads a finished run and cannot change one. `DOCUMENTATION.md` is the surface of both.

## How work gets built here

Shape first, then red-green upward.

1. **Shape first.** Write the call structure only — signatures plus contract docstrings, every
   body `raise NotImplementedError`. `grep NotImplementedError` is the progress tracker, and the
   plan cannot drift from the code because they are the same file.
2. **Then red-green, from the smallest unit up.** For each stub: a failing test that names the
   contract, the smallest body that passes it, then the next stub above it. A test that passes the
   moment you write it tested nothing.
3. **A stub raises, never returns a placeholder.** A stub returning `0`, `None` or `""` is a
   failure silently becoming a value — the defect this whole repo is built around.
4. **One function per diff.**

## Delegation

**The default execution mode here is a team of parallel agents, with the lead as orchestrator, not
implementer.** The user has asked for this three times now; this entry is why a fourth time shouldn't
be needed.

- **Anything past a single mechanical edit goes to an agent.** The lead decides WHAT is measured and
  WHETHER the answer is believable — not types the measurement.
- **Independent work goes out in one message, multiple tool calls, so agents run concurrently.**
  Dispatching independent tasks one at a time is the failure mode to avoid.
- **Every brief names the files the agent owns and the files it must not touch.** Concurrent agents in
  one repo collide: four runs launched at 15:03 had `probe.py` edited by another agent at 15:06, so all
  four had to be killed and relaunched — readiness had been inferred from green tests instead of
  waiting on the owning agent's report.
- **A brief carries the numbers the agent must reproduce.** A port that produces different numbers is
  wrong, not the table it disagrees with. Two traps worth citing: a firing outcome from
  `pipeline.harness.run_raw` is `outcome == "catch"`, never `"fail"` — checking for `"fail"` silently
  scores every suite as clean — and `analyse_probes.load_arm` returns a dict, not a list.
- **Agents report conclusions, not file dumps.** The lead relays what changed and what it means; it
  does not restate the artifact.
- **What the lead still does alone:** deciding the experiment, judging whether a result is real, and
  talking to the user. Never delegate the interpretation.

## The rule that matters most

**A failure must never silently become a value.** Six separate bugs here were the same shape: a
measurement that did not happen, written down as the falsy default, which read as *"the model
failed"* — the direction that flatters our infrastructure and penalises the thing under study.

- Never write `x or 0`, `.get(k, False)`, or a falsy default on any path feeding a metric.
- Use `pipeline/outcome.py`: `Unknown(Blame.INFRA | Blame.MODEL, reason)`. Its `__bool__` raises, so
  `if unknown:` and `unknown or 0` fail loudly instead of lying.
- State blame **where the failure is detected**; inferring it later from an error message mislabelled
  every crash whose text lacked a marker word.
- Spell a substituted default `known(x, default)` so it is visible in review.
- Every unknown reaches the artifact. A verdict carries `pbt_unknown` and `tm_unknown`, each
  serialising its blame and its reason; a measurement that did not happen is never just absent.

## Code style

- **Name things instead of commenting them**: a named constant over an annotated literal, a raised
  error over a warning comment.
- **Every optional in the config layer gets a real default** — `""`, `0` for "all", a fallback object.
- **Reuse over hand-rolling.** scipy/sklearn for statistics, pydantic-settings for config; the
  hand-rolled ROC curve silently misreported every partial-AUC figure.
- **Fail fast** in `__post_init__` / `model_validator`, not a defensive `.get()` on a guaranteed key,
  and no Protocol whose one implementation forwards to a function.
- **Search `pipeline/` before writing the second loader, adapter or parser.** `probe.py` wrote an
  APPS-only loader while `schema.Backend` already normalised both benchmarks, which is why
  BigCodeBench is a refactor rather than a flag.

## Where a change goes

**A new measurement is a flag on the harness, never a new script.** Six scripts that each re-derived
a number the pipeline already computed, then drifted from it, were deleted on 2026-08-18. A new arm
is a value in an existing `choices=` list (`--resolve`, `--code`, `--format`); a new score is a field
on the artifact, written by the code that already writes it; a rescoring reads `runs/<id>/` and
writes back into it as a flag on the tool that made the run. If two entry points would compute the
same number, there is one entry point.

Could a later run need this? Then it is a flag; a single-use diagnostic goes in a notebook.

## Running an experiment

**Write the entry before the run, not after.** Every experiment gets an entry in
`reports/EXPERIMENTS.md`, appended *before* the command is launched. That file does not exist yet —
`reports/` holds one JSON analysis — so the next experiment recreates it.

```
### E<n> — <name>
**Setup.**      pool, n tasks, models, seed, budget — everything needed to re-run it.
**Change.**     the ONE thing different from the run above. If there is more than one, split it.
**Hypothesis.** what we expect and *why*, stated so it can be wrong.
**Prediction.** the number that decides it, with a threshold, written down first.
**Observed.**   filled in after. Verified against the artifact, never from memory.
```

A hypothesis written after seeing the number is not one: A4's density correlation (+0.574) was formed
on already-inspected data and came back **−0.142 on held-out tasks**. A thresholded **Prediction** is
what stops a null result being retold as a positive one. Same units across entries.

- **Detached, always.** `probe.py --detach` starts the run in a tmux session named after the run id
  via `pipeline/launch.py` and returns in milliseconds; it raises `LaunchFailed` if the session dies
  on startup, so a mistyped flag surfaces at launch rather than as an empty `runs/` in the morning,
  and it refuses a run id already running. Watch it with `pipeline.launch.pane(run_id)`.
- Nothing over a minute runs in a foreground shell, an agent tool call, or a notebook cell; all three
  die with their session and take the run with them. `--run-id` resumes, costing one in-flight call.
- **Run `caffeinate` alongside the run.** tmux does not stop the machine sleeping, and nothing here
  enforces it for you — `Settings.allow_sleep` names the intent but no code reads it.
- Diagnose by artifact counts under `runs/<id>/` first and `console.log` **last**. Nothing writes a
  heartbeat, so artifacts are the only ground truth: the log lied to us for an hour once, artifacts
  never have.
- Attacks written by a human or by Claude are a **different distribution** from attacks sampled from
  an untrusted policy. Never pool them; they answer different questions.

## Before claiming a result

- **Verify every number against `runs/<id>/probe.json`** — not from memory, not from an earlier message.
- **Report `safety − free_floor`.** `MetricConfig.free_floor` is the share of deployments containing
  no attack at all, which every protocol wins for nothing: 0.364 at a 2% attack rate over 50
  submissions, so a raw safety of 0.40 is almost entirely floor.
- **Check n first.** Abstaining runs are dropped, so `n` can be below the run count; a "5-run" delta
  was actually n=4. Every error bar comes from `--runs N`, so `stat`'s `ci95` is `None` at `--runs 1`.
- **Report the mechanism, not the delta alone.** A false-positive count at a fixed threshold is
  descriptive only, because the deployment game never applies one; what the audit rule spends is
  *rank*, and `probe.score_levels` prints how many distinct levels each monitor produced.
- **Say when a threshold was fitted** — a number chosen by looking at the data is not evidence until
  it survives tasks it was not chosen on.
- **Check for tautology.** Ask what the metric would report if the effect were absent: a 0% false
  positive rate arising because the filter mechanically removes every offender is not a finding.
