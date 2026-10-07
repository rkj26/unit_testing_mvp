# Omar's multi-turn arm: one cell for either shared results notebook

Use this with `results_uniform400.ipynb` or `results_bcbas.ipynb` from this
checkout. Both notebooks already define `ut_property`, `ARMS`, `COVERAGE`,
`SCORED_BY_ALL`, and `coverage` in their section **4 · The arms**.

Insert **one new code cell immediately after** the existing cell that defines
`ARMS` and `SCORED_BY_ALL`, before **5 · Every threshold**. Leave every existing
cell unchanged. Paste the code below into that new cell.

```python
from pathlib import Path
from pipeline.protocols.omar_shared import advance

# First run: inspect the saved source bundle before enabling paid revisions.
# Set this to True only when your model and run budget are approved.
LAUNCH_OMAR_PAID = False

omar_status, omar_arms = advance(
    ut_property,
    prefix=f"omar-{Path(DATASET).stem}-v1",
    launch_paid=LAUNCH_OMAR_PAID,
    include_no_feedback=False,
)
print(omar_status)
if not omar_arms:
    raise RuntimeError("Omar arm is still preparing or running; rerun this cell later")

units.update(omar_arms)
ARMS.update(omar_arms)
COVERAGE = {label: coverage(arm) for label, arm in ARMS.items()}
SCORED_BY_ALL = set.intersection(*(seen["ok"] for seen in COVERAGE.values()))
print(f"{len(SCORED_BY_ALL)} candidates scored by all {len(ARMS)} arms")
```

What happens when you run the cell:

1. It uses the **existing `ut_property` suite** as the first turn. Finish that
   arm and the notebook's trigger search before running this cell.
2. A background job replays those saved tests on the **same candidates and
   trigger inputs**. It writes `runs/omar-<dataset>-v1-source-feedback/source-bundle.json`.
   This step makes no model API calls. Rerun the cell after it finishes.
3. Review the bundle. Set `LAUNCH_OMAR_PAID = True` and rerun the cell to start
   one revised suite per candidate in the team's usual detached runner. It uses
   the notebook's `MODEL`, dataset, Python packages, and sandbox image through
   the baseline arm. Rerun the cell after the revision completes.
4. The completed revision becomes `multi-turn + feedback` in the notebook's
   existing `units` and `ARMS` dictionaries. All later tables and plots include it on their shared
   candidate population. A failed candidate is excluded by the notebook's
   existing `coverage` rule; it is never counted as a clean result.

The temporary `RuntimeError` in steps 2–3 is intentional: it stops the later
plots from silently running without the new arm. Rerun the cell after the
background stage finishes. Check its saved records under `runs/<name>/` or
use `SecondRevision.attach(<name>).status()` to monitor a paid revision.

For the controlled comparison of feedback versus no feedback, change only
`include_no_feedback=True`. That starts a second revision arm using the same
source and prompt, with execution diagnostics withheld. Both arms then appear
in `ARMS` when finished. Plan for **up to one paid call per candidate per
revision arm**; the baseline arm's calls are already recorded. There is no
dollar cap in the full notebook runner, so check pricing and your budget first.

The revision prompt is [`prompts/second_revision_v1.txt`](../prompts/second_revision_v1.txt).
It shows each test its task, first-turn suite, and fixed inputs. In the feedback
arm it also shows bounded execution outcomes; no-feedback gets a withheld marker.
The revision prompt has traceability and oracle rules that the original
`ut_property` prompt does not. Thus the clean feedback contrast is between the
two revision arms; the original-to-revision contrast changes more than one
prompt feature.

All records go into the repo's usual `runs/<name>/` directories. The notebook
does not execute candidate code; the normal Docker sandbox handles replay and
scoring. The `results_*` notebooks remain otherwise unchanged.
