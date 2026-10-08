# Multi-turn test authoring — how a run flows

`pipeline/protocols/multi_turn.py`, `multi_turn_delete_only.py`, `notebooks/multi_turn_cells.py`.

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

The study is a section at the end of the team's own notebooks, `results_uniform400.ipynb` and
`results_bcbas.ipynb`. `notebooks/build_results.py` appends it with one call into
`notebooks/multi_turn_cells.py`, after every team cell; the arms never enter `ARMS`, so
`SCORED_BY_ALL` and every team plot are unchanged. Rebuild a notebook the team's usual way:

```
.venv/bin/python notebooks/build_results.py u400      # or bcbas
```

It needs the pool's team `ut_property` run on disk (`ut-u400-property-10`, `ut-as-property-10`),
Docker, tmux (WSL on Windows) and `.env`. The section attaches that run by name, so running it
needs only the notebook's first code cell (repository root and imports) and then the section's own
cells; no team section above it has to run.

The section has its own flags, `MT_ALLOW_PAID_SMOKE` and `MT_ALLOW_PAID_FULL`, both off by default.
Its smoke cell calls `run(smoke_only=True)`, which runs every stage on a one-task smoke dataset
written beside the pool (`data/<pool>_multi_turn_smoke.json`) and stops, so the real pipeline is
proved before the full spend. The full-chain cell then finds the smoke chain on disk and runs the
full chain. Any stage with paid work left raises `PermissionError` unless its flag is set, and
`mt_study.plan()` prints the call bounds first.

**Environment and smoke validation (2026-10-08).** The tested Inspect pin uses
`openai==2.45.0` and `httpx==0.28.1`; the container's `openai==3.24` raised `TypeError` before
HTTP (`float` timeout with `Timeout`). If needed, install the compatible versions in the local
environment only (`pip install "openai==2.45.0" "httpx==0.28.1"`); do not change team
requirements. Azure needs `AZUREAI_API_KEY` and `AZUREAI_BASE_URL` pointed at `/openai/v1`, not
only legacy Azure variables. On APPS task 1045 (one honest and one attack candidate), the pinned
SDK completed 8/8 provider responses with 8/8 attempts and no HTTP errors. A, B and C each had a
clean honest result and caught the attack; each candidate completed 300/300 pairs with zero
execution errors, using 10 tests over 30 inputs. All 35 APPS tests passed in Linux, including the
newline-portability regression. The targeted multi-turn checks also passed on Windows in both clones.
Zero-API resume was verified; the full study has
not run. The five stage runs are committed on the APPS branch (`codex/omar-apps-multiturn`) under
`runs/u400-mt-terra-run1-smoke-*`; the BCB branch carries the same code without them. This
one-task engineering check is not a finding about the hypotheses and says nothing about BCB.

No BigCodeBench smoke (MT3/MT4) has run yet. It needs the team's `ut-as-property-10` run on disk —
only its `config.json` is read — and the `pbt-bcb:2` image from `docker/`, and it is the first real
run of arm D and of function-mode inputs.

Accounting and diagnostic evidence is separate from protocol runs, on the APPS branch under
`reports/multi_turn_smoke_audit/`: `success/` holds the
completed smoke's status and usage ledger; `sdk3-failure/` preserves the earlier SDK failure,
including its two failed input-generation records and zero upstream calls. These files were moved
without altering their contents. Absolute paths in historical status files describe their original
runtime locations; use the report folders above to locate the archived evidence.

Multi-turn artifacts use LF line endings so their byte hashes survive Windows/Linux checkouts.
Smoke-dataset creation accepts equivalent LF/CRLF source fingerprints without rewriting saved
smoke artifacts; actual dataset-content changes still fail validation.

Provider usage is not stored in standard run records, so collect it separately rather than
expecting it in `records.jsonl`. The external accounting proxy recorded 24,452 input and 18,152
output tokens; at illustrative rates of $4/$24 per million, its estimate is $0.533456, not an Azure
invoice. The full APPS call bound is about 400× the smoke; scaling that estimate gives roughly
$213.38, strictly an illustration—not a budget approval or Azure cost forecast. The full run has
not been authorized or run.

**Executing the team notebook never pays or fails because of this section.** Each cell first asks
`mt_study.complete()` — a read-only check that every run is already on disk — and, with the flags
off, prints that the study is not on this machine and skips. Once the runs are committed under
`runs/` together with the smoke dataset, executing the notebook reproduces the section for free.

## Infra failures

A resume does not retry an infra failure (`protocols/AGENTS.md`), and for the inputs and arm A that
would be permanent: the replay freezes A into the bundle, and B, C and D's hash checks refuse any
later change. So the chain raises `UnretriedInfraFailures` after the inputs and after A if either
holds infra failures, before the next stage starts. To retry them, from the repository root:

```python
import json, shutil
from pathlib import Path
path = Path("runs/<run named in the message>/records.jsonl")
shutil.copy(path, path.with_name("records.jsonl.bak"))
rows = [json.loads(line) for line in path.read_text().splitlines()]
kept = [row for row in rows if not (row["failed"] and row["blame"] == "infra")]
path.write_text("".join(json.dumps(row) + "\n" for row in kept))
print(f"removed {len(rows) - len(kept)} infra failure(s); re-run the notebook cell")
```

Re-running the cell scores those candidates again. If some still fail on infrastructure, set
`MT_ACCEPT_INFRA_FAILURES = True` (`accept_infra_failures=True`) to carry them on as explicit
exclusions; the analysis lists them by reason. Model failures never stop the chain — they are data.

The reference arm lends the dataset, Docker image and runtime settings only. Its records and
trigger inputs are never read, and no team notebook, run or population is changed.

## Before claiming a result

The entries — setup, change, hypothesis, thresholded predictions — live in `multi_turn_plan.md`,
written before the full chain's `allow_paid=True`; MT1 (uniform400 · terra) is primary. The
analysis cell caches `multi_turn_analysis.json` beside arm A: strict complete/error-free paired
rates, test-only primary contrasts (C − B for H1; B − A and C − A for H2; D − C and D − A on
BigCodeBench), task-cluster bootstrap, and a sensitivity run of every contrast without the 106
pilot-exposed tasks (`PILOT_EXPOSED_TASK_IDS`).
