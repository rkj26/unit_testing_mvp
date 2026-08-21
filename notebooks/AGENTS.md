# `notebooks/`

A notebook **reads artifacts; it never produces a number.** Every figure loads from
`runs/<id>/probe.json` through `audit.py`, `analyse_probes.py` or `deployment_game.py` and plots.
None is computed in a cell.

This follows from verifying against the artifact. A number computed in a cell has no run id, no
config, and no record of which cells ran in what order, so it cannot be re-derived and cannot be
cited. Out-of-order execution has already cost this project one retracted correlation.

- **Explore in the notebook; graduate what gets reported.** Pivots, groupings and plots belong in
  cells, where they are fastest. The moment a number goes on a slide or into a report it moves into
  `analyse_probes.py` and is *called* from the cell, so it has a name, a test, and can be recomputed
  from a run id by someone who never opens the notebook. Statistics always go through scipy/sklearn —
  hand-rolling them here is how a partial-AUC figure was silently wrong once already.
- `%load_ext autoreload` in the setup cell, so editing the harness needs no kernel restart. Friction
  is not a reason to redefine a metric in a cell.
- A notebook may **launch** a run but never **hosts** one. `pipeline.launch.launch(run_id, argv)`
  starts it detached in tmux and returns in milliseconds; `alive` and `pane` watch it. A cell that
  blocks on the run dies with the kernel and takes the run with it, so no `subprocess.run`, no
  `await`, no `asyncio.run` of an experiment in a cell.
- **`deployment_game` is driven from here, not from a shell.** It has no command line by design:
  `load_runs`, `simulate` and `sweep` are called from a cell, and `sweep`'s return value is the table.
- Restart-and-run-all must reproduce the whole notebook, or it is not evidence.
