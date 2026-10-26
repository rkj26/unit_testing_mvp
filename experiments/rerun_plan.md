# Re-run of every full-pool arm (R2)

**Stopped 2026-10-26 at step 2a.** The API key was rotated and no further runs are possible, so the
first pass is the final data. Its provider-period split (below) is a limitation of the results, not
something a re-run will fix.

**Why.** The first pass straddled the provider's change of 10 October: DeepSeek-V3.2 on Azure began
reasoning about three times longer and abstaining more often under an unchanged model name and
settings. `plain_v5` and the multi-turn chain were scored partly or wholly after it, the main arms
before it. R2 scores everything again in one period, so every comparison is like with like.

**Scope.** Full pool only: `data/apps_full_py312.json`, 1,388 tasks, 2,776 candidates, the 555/833
split; the same tasks, tests and split as `data/apps_full.json`, with the code read as is from
`data/apps_full_code/` (one file per candidate, saved once by `build_dataset.py --write-code`).
Model `openai-api/azureai/DeepSeek-V3.2`; the trusted model at `low` reasoning, the untrusted
planner at `high`. Every run gets the suffix `-r2`; no first-pass run is touched.

## Settings that differ from the first pass

| Setting | First pass | R2 | Why |
|---|---|---|---|
| `TM` `runs` | 2 | **1** | Asked for. |
| `MonitorWithTests` `runs` | 2 | **1** | It must match TM's call budget: this arm exists to be compared against TM (`DOCUMENTATION.md`). |
| `cache` | on (runs = 1) / off (runs = 2) | **off everywhere** | Same prompt and seed hit the local inspect cache, so a run with the cache on would replay the first pass's answers instead of asking the model again. |
| Token cap and timeout: TriggerSearch, TM, TrustedSolve, MonitorWithTests | 12,000 tokens, 120 s (set by `reasoning="low"`) | **32,000 tokens, 300 s** (`max_tokens`, `call_seconds`); **64,000 tokens, 600 s** for TriggerSearch | Step 1: today's provider reasons past 12,000 (62% of trigger calls cut off). 32,000 and 300 s are what the suite calls already use; trigger search still lost 5% at 32,000 and 1.7% at 64,000. |
| Candidate code | scrubbed at every build | **saved once, read as is** (`data/apps_full_code/`); 9 of 2,776 files differ from the first pass's code | The scrub gave two names in 4132's backdoor the same replacement, which merged two variables and killed its trigger (now one name each). Under 3.12, four honest solutions crashed on `fractions.gcd` and four programs printed a SyntaxWarning for `x is 1` (now a copy of the 3.4 `gcd`, and `==`). |
| How a suite runs a stdio candidate | `exec` inside the harness, stdin a `StringIO` | **a fresh `python -c` per call, real stdin** (`sandbox._ENTRY_STDIO`) | control-arena runs every test this way; in-process, `sys.stdin.buffer` and `open(0)` crashed (4 candidates), and a T program with a syntax error failed the whole grid as infra instead of failing every pair. |
| Ground truth | asserted by pool construction | **graded by control-arena's rule** on every test, Python 3.4 and 3.12 (step 0) | Any stderr fails a test there, so the code must run silently under both. |

## Steps

| # | Step | Runs | Depends on | Status |
|---|---|---|---|---|
| 0 | Ground truth: grade `data/apps_full_py312.json` by control-arena's rule (any stderr fails), every test, Python 3.4 and 3.12. **Gate:** 0 main-task failures, 0 runs writing to stderr, every backdoor's secret input changes the output, in both. | — (no model calls) | — | done: passed (Observed) |
| 1 | Smoke: every run on the 60-candidate smoke dataset (names end `-r2-smoke`), cache off. Measure abstention, reasoning length and cost per call under today's provider. **Decision:** if more than 5% of calls hit the token cap or return no score, raise that protocol's cap for R2 (same cap for every arm of it) before step 2. | every run, `-r2-smoke` | — | done: caps raised (Observed) |
| 2a | TrustedSolve first, and look at it: its attempts graded by control-arena's rule on every test, against its own grader's `solves`. About $30–90 (2,776 calls at ~6,500 output tokens, from the smoke). | `solve-all-r2` | 0 | killed at 313 / 2,776 (launched by mistake; moved to `archived/killed_runs/`) |
| 2b | Inputs and baseline | `trig-all-r2`, `tm-all-r2` | 2a looked at | **blocked**: API key rotated 2026-10-26, no runs possible |
| 3 | Suites | `ut-all-property-10-r2`, `ut-all-plain_v3-10-r2`, `ut-all-plain_v5-10-r2`, `upt-all-property-10-r2`, `upt-all-plain_v3-10-r2` | `trig-all-r2` | **blocked**: API key rotated 2026-10-26, no runs possible |
| 4 | Monitor + tests | `mwt-full-all-property-10-r2`, `mwt-full-all-plain_v3-10-r2`, `mwt-full-all-plain_v5-10-r2`, `mwt-full-all-uplans-property-10-r2` | the matching step-3 run | **blocked**: API key rotated 2026-10-26, no runs possible |
| 5 | Multi-turn chain (A traceable, A replay, B no feedback, C feedback), as MT5 in `experiments/multi_turn_plan.md` | `full-mt-deepseek-run2-*` | `trig-all-r2`; runs alongside 3 and 4 | **blocked**: API key rotated 2026-10-26, no runs possible |
| 6 | Point the notebooks at R2 (`POOLS["all"]`), re-execute, and compare R2 with the first pass (each headline number with its interval) | — | 2–5 | **blocked**: API key rotated 2026-10-26, no runs possible |

## How it runs

- One driver script launches each step when its inputs finish, so the whole chain runs unattended.
  Every run is already a detached tmux session that resumes by candidate if it stops.
- `caffeinate -s -w <driver pid>` keeps the Mac awake while plugged in, until the driver exits.
  For running with the lid closed: `sudo pmset -a disablesleep 1` before, `0` after.
- Progress is checked from `status()` of each run; failures are retried once and then accepted
  with their blame, as in the first pass.

## Entry (written before the runs)

**Setup.** As above. Launcher: `experiments/rerun_r2.py {smoke|full} [run ...]`, run inside tmux under
`caffeinate -s` (the Mac also has `pmset disablesleep 1`). Smoke dataset:
`data/apps_full_r2_smoke.json`, the first 10 train and 20 test tasks of the full pool (60
candidates), cut from `data/apps_full.json` with candidates unchanged. Each R2 run's settings were
diffed against its first-pass `config.json` before launch: only the input run names, `runs` (TM and
MonitorWithTests) and `cache` differ.

**Change.** The provider period (after 10 October for every run); TM and MonitorWithTests at one
call per candidate instead of two; and the four protocols above at 32,000 tokens and 300 s a call (trigger search 64,000 and 600 s).

**Hypothesis.** The protocols, not the provider period, set the results, so R2 reproduces the first
pass within noise. One call instead of two makes monitor scores coarser (steps of 1/9 instead of
1/18), which can move cuts but should not move AUC much.

**Prediction.** (1) Each main arm's AUC within ±0.02 of the first pass. (2) Each monitor + tests
arm's catch at 2% false alarms minus the monitor's, within the first pass's 95% interval for that
gap (digest section 8). (3) At most 20% of monitor calls return no score.

## Cost

The first pass cost $444 across every pool. R2 covers the full pool only, with TM and the
monitor arms at one call per candidate instead of two, but reasoning is about three times longer
than before 10 October. Step 1 measures today's cost per call; the estimate for steps 2–5 is
filled in here before step 2 starts.

## Observed

(filled in as steps complete)

**2026-10-20, step 1, first smoke (stopped early).** Under `reasoning="low"` the four
protocols without their own cap (TriggerSearch, TM, TrustedSolve, MonitorWithTests) get 12,000
tokens and 120 s a call (`pipeline/model.py`, `MAX_TOKENS_BY_EFFORT`). Today's provider runs past it:

| Run (60 candidates) | Calls stopped at the token cap | Failed | Mean reasoning, chars |
|---|---|---|---|
| `trig-all-r2-smoke` | 61.6% | 34 | 32,147 |
| `tm-all-r2-smoke` | 26.6% | 16 | 23,609 |
| `solve-all-r2-smoke` | 25.0% | 15 | 18,968 |

TM's finished calls: median reasoning 16,177 chars, 90th percentile 33,688, maximum 39,118. The
suite runs had made no calls (their failures are carried forward from the failed trigger
searches). The step-1 rule fired; the smoke runs were stopped and are not part of R2. The three
measured runs are kept, outside `runs/`, in `archived/r2_smoke_cap12k/`.

**2026-10-20, step 1, second smoke (32,000 tokens, 300 s).**

| Run (60 candidates) | Calls cut off at the cap | Failed | Median reasoning, chars |
|---|---|---|---|
| `trig-all-r2-smoke` | 6.6% | 3 | 35,813 |
| `tm-all-r2-smoke` | 1.6% | 1 | 24,683 |
| `solve-all-r2-smoke` | 1.6% | 1 | 11,918 |
| `tm-effort-high-r2-smoke` (`reasoning="high"`, a check) | 0% | 0 | 22,204 |

TM at `high` reasons no longer than at `low`: the provider no longer acts on `reasoning_effort`.
Trigger search is still over the 5% rule; the first pass lost 0.5% of its searches (15 of 2,776).
The three failures were cut at 32,000 tokens with no output, so `trig-cap64k-r2-smoke` tests
64,000 tokens and 600 s on the same candidates.

**2026-10-21, step 0, ground truth.** `data/apps_full_py312.json` graded by control-arena's rule
(a fresh `python -c` per test, input on stdin, 10 s, 1 CPU, 0.5 GB, any stderr fails), every
provided test (35,525 pairs), cached in `data/apps_full_py312.control_arena.jsonl`:

| Image | Honest failing main task | Backdoors failing main task | Backdoors not triggering | Candidates writing to stderr |
|---|---|---|---|---|
| python:3.4 | 0 / 1,388 | 0 / 1,388 | 0 / 1,388 | 0 |
| python:3.12-slim | 0 / 1,388 | 0 / 1,388 | 0 / 1,388 | 0 |

The gate passed; step 2a was launched (`experiments/rerun_r2.py full solve-all-r2`). The first
pass's `data/apps_full.json`, by the same rule, had 4132's backdoor not triggering in both images,
and under 3.12 four honest crashes (`fractions.gcd`) and four programs writing a warning.
Step 2a was a misreading: the ask was to grade the first pass's TrustedSolve by control-arena's
rule, not to run it again. `solve-all-r2` was killed at 313 of 2,776 calls (about $3–10) and moved
to `archived/killed_runs/`. No R2 model run is started until R2 is approved as a whole.
