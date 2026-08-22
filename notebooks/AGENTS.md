# `notebooks/`

**Calls a model → a run. Everything else → a cell.** Every metric in `apps.ipynb` is computed in a
cell: the threshold sweep (§2), trigger hit rate (§3), earned catches (§4), clean wins (§5), the
deployment game (§6). This file used to say the opposite — *"a notebook reads artifacts; it never
produces a number"* — and that rule died with the three scripts it routed numbers through.
`probe.py`, `audit.py` and `analyse_probes.py` are deleted; what it was protecting is now held by the
run directory, which carries its own `config.json` and so needs no external module to say what an
arm meant.

## Why the line sits at "calls a model"

Only a model call has to outlive the kernel. The passes that execute code in Docker do not, and the
cost is measured, not assumed:

| pass | cost |
|---|---|
| trigger divergence — §3 `hit_rate` | 81 s |
| differential replay | ~40 s |
| clean wins across six arms — §5 `clean_wins` | ~4 min |
| any model-call protocol | tens of minutes to hours |

The first three were timed on the cells §3 and §5 replace. So *expensive* and *must survive a dead
kernel* are not the same axis, and only the second one buys a detached process. If a measurement cell
ever grows past ~10 minutes, reach for `pipeline.launch.launch`; none is close.

## What still holds

- **Restart-and-run-all must reproduce the notebook, or it is not evidence.** A number is citable
  only when the order that produced it is the order on the page. Out-of-order execution has already
  cost this project one retracted correlation.
- **A notebook may launch a run; it may never host one.** `Run.run()` writes `config.json`, starts
  the run detached in tmux through `pipeline.launch.launch`, and then only *follows*
  `records.jsonl` — Ctrl-C on the follow, or a dead kernel, leaves the run going. `run.status()`
  reports `{"scored", "total", "alive"}`, `launch.pane(run_id)` shows the tail, and
  `TM.attach("tm-v1")` rejoins from a fresh kernel; §1's `attach_all()` rejoins all of them at once.
  A cell may shell out for seconds — §3's `output_of` runs one submission on one input under a
  10 s timeout — but never for the hour a protocol takes.
- **A measurement cell caches beside the run it measures, so a rerun is free.** `hit_rate` writes
  `runs/trig-v1/hit_rate.json` and `clean_wins` writes `runs/<arm>/clean_wins.json`, both under
  `Run.directory`, both returning the cached document when it exists. That is what makes
  restart-and-run-all affordable, and therefore what makes the first rule something you will
  actually do rather than skip.
