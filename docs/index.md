# run & cell

Two halves of one experiment, split by whether they cost money.

| | |
|---|---|
| **a run** | one protocol over one dataset: `pipeline/protocols/`, detached in tmux, appending to `runs/<run_name>/records.jsonl`. Model calls, docker, hours. |
| **a cell** | every metric, in `notebooks/apps.ipynb`. Reads records, executes code where it has to, caches beside the run it measures — `runs/<run_name>/differential.json`. |

**Calls a model → a run. Everything else → a cell.** The line is money, not runtime: a
measurement pass that runs candidate code in Docker is still a cell. Only the model-call
protocols run long enough to need to outlive the kernel, which is why only they are
detached.

A cell writes its own cache into the run directory and never `records.jsonl`, so nothing
in a cell can change a result. A run records observations and derives no rate, so no rate
is computed in two places. That was the defect: one pass authored tests, executed them
**and** scored the trusted monitor, and every reader afterwards re-derived the rates it
needed until they disagreed.

```{toctree}
:maxdepth: 2

guide
pipeline
protocols
test_visibility
api
```
