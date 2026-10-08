# Multi-turn test authoring — how a run flows

`pipeline/protocols/multi_turn.py`, `multi_turn_delete_only.py`, `notebooks/build_multi_turn.py`.

## The question

Does a trusted model write better tests on a second turn, and does seeing the first suite's execution
feedback help? The primary contrast is **C − B on held-out test tasks**: B and C revise the same
suite with the code hidden, and differ only in whether A's execution feedback is shown.

## The chain

Each stage is its own run, launched by `Run.run()` in tmux and resumed from `runs/<name>/`:

| stage | class | model calls | reads |
|---|---|---|---|
| `<prefix>-triggers` | `TriggerSearch` | one per candidate | the dataset |
| `<prefix>-A-traceable` | `MultiTurnInitial` | one per candidate | the triggers |
| `<prefix>-A-replay` | `MultiTurnReplay` | none — Docker only | A, the triggers |
| `<prefix>-B-no-feedback` | `MultiTurnRevision`, `feedback_visible=False` | one per eligible candidate | the bundle |
| `<prefix>-C-feedback` | `MultiTurnRevision`, `feedback_visible=True` | one per eligible candidate | the bundle |
| `<prefix>-D-delete-only` | `MultiTurnDeleteOnly` (BigCodeBench) | one per eligible candidate | the bundle |

B, C and D are launched together and followed jointly, so the arms being compared run side by side.

`write_source_bundle` freezes the finished replay into `runs/<prefix>-A-replay/source-bundle.json`,
hashing the dataset, A's config and records, and the trigger records. B, C and D are constructed
with that file's SHA-256 and refuse to start if anything it hashed has changed since.

B and C are `SecondRevision` — the same prompt, call and verdict — with the population rules of a
shared notebook pool: train and test both revise, and a candidate without usable inputs is a failed
record carrying the input run's blame, with no call made.

## Running it

```
.venv/bin/python notebooks/build_multi_turn.py u400      # or bcbas
```

Open `notebooks/multi_turn_uniform400.ipynb` (or `multi_turn_bcbas.ipynb`). It needs the team's
reference arm under `runs/` (`ut-u400-property-10`, `ut-as-property-10`), Docker, tmux and `.env`.

`MultiTurnStudy.run(smoke_only=True)` runs only the smoke chain and stops, so the real pipeline
is proved on one task first (the notebook's section 2). Without it, `run()` first runs the whole
chain on a one-task smoke dataset written beside the
pool (`data/<pool>_multi_turn_smoke.json`), stops if any smoke stage hit infrastructure, then runs
the full chain. Any stage with paid work left raises `PermissionError` unless `allow_paid=True`, so
re-running a finished study costs nothing. `study.plan()` prints the call bounds first.

The reference arm lends the dataset, Docker image and runtime settings only. Its records and
trigger inputs are never read, and no team notebook, run or population is changed.

## Before claiming a result

The entries — setup, change, hypothesis, thresholded predictions — live in `multi_turn_plan.md`,
written before the full chain's `allow_paid=True`; MT1 (uniform400 · terra) is primary. The analysis cell caches
`multi_turn_analysis.json` beside arm A: strict complete/error-free paired rates, test-only primary
contrasts (C − B for H1; B − A and C − A for H2; D − C and D − A on BigCodeBench), task-cluster
bootstrap, and a sensitivity run of every contrast without the 106 pilot-exposed tasks
(`PILOT_EXPOSED_TASK_IDS`).
