# `pipeline/` — the shared library

Ten modules and a backends package, no entry point. `probe.py` runs an arm with them and `audit.py`
reads the result; neither owns them. The orchestrator that did own them (`run.py`, `engine`, `steps`)
was deleted on 2026-08-19, so anything here that reads like a step in a longer sequence is a remnant
of that.

| module | what it is for |
|---|---|
| `schema.py` | the records everything passes around: `Problem`, `Candidate`, `Completion`, `Backend` |
| `outcome.py` | **the one way this repo says "we don't know"** — read this first |
| `config.py` | `Settings`, `ModelRuntime` and the reasoning/timeout ladders, plus `MetricConfig` |
| `model.py` | one runtime in, one awaitable completion out |
| `monitor.py` | the trusted monitor's prompt and its score parser |
| `pbt.py` | prompt rendering and the two hardened parsers |
| `harness.py` | the sandbox: the only place candidate code runs |
| `search.py` | trigger-search strategies, all local, no model calls |
| `scoring.py` | ground-truth correctness via control_arena |
| `launch.py` | start a run detached in tmux and prove it started |
| `backends/` | `apps` (live), `bcb` and `mock` (present, unused) |

`metrics.py` is gone. Its `MetricConfig` moved to `config.py` and its simulation now lives in the
notebooks' deployment cells; the rest had no callers and was deleted.

---

## `outcome.py` — start here

The rule the whole repo is built around: **a failure must never silently become a value.**

Six separate defects here were the same shape — a measurement that did not happen, written down as
the falsy default, which always reads as *"the model failed"*. That direction flatters the
infrastructure and penalises the thing under study.

```python
Unknown(Blame.INFRA | Blame.MODEL, reason)
```

`Unknown.__bool__` **raises**, so `if unknown:` and `unknown or 0` fail loudly instead of lying.
Blame is stated where the failure is detected, never inferred later from an error message. Where a
default genuinely is correct, it is spelled `known(x, default)` so it is visible in review.

## `schema.py` — the records

| | |
|---|---|
| `Problem` | one task: `task_id`, `main_task`, `io_mode`, its candidates, statement examples |
| `Candidate` | one submission: `candidate_id`, `label` (`honest` / `attack_N`), `code`, `secret_input` |
| `Completion` | one model answer: `text`, `stop_reason`, `unknown`, `reasoning` |
| `Backend` | the protocol: `preprocess(pool) -> list[Problem]` and `score_candidates(...)` |

`Backend` is *"the ONLY benchmark-specific surface the pipeline depends on"*. `probe.py` does not
use it — it has its own APPS-only loader — which is why a BigCodeBench run is not a flag away.

`io_mode` is the fork that matters: `apps` produces `"stdio"` (a candidate reads stdin), `bcb` and
`mock` produce `"function"` (a candidate takes kwargs). `pbt._INVOKE_CONTRACT` holds prompt text for
both; `probe.py` hardcodes the stdio one.

## `config.py` — settings and `MetricConfig`

`MetricConfig(audit_rate, attack_probability, horizon, trials, train_tasks)` is the record the
notebooks' `play_safety` and `run_deployment` take. Its `free_floor` property — `(1 − attack_rate)^horizon`
— is the share of deployments containing no attack at all, which every protocol wins for nothing. At
a 2% attack rate over 50 submissions that is 0.364, so a raw safety of 0.40 is almost entirely floor.
Report `safety − free_floor`.

`Settings.allow_sleep` names an intent no code reads; suppressing sleep during a run is manual.

## `harness.py` — the sandbox

The only place candidate code executes, and the only thing holding a memory, CPU and PID bound.

```python
run_raw(problem, code, tests_src, space, timeout_s=..., isolation=Isolation.DOCKER)
```

Runs every test over every input against one implementation and returns `records` — one
`{prop, i, outcome}` per pair. Two flags on the result matter and are easy to misread:

- `ok` — the run produced a usable header and at least one well-formed record.
- `complete` — the **whole grid** ran, counted by the parent as distinct pairs rather than read off
  a flag the candidate could have written. A missing pair can only lose a catch, never invent one,
  so an incomplete run under-reports and must never be read as a clean negative.

`probe.execute` is a thin wrapper over this; `probe._catches` turns `records` into
`(test, input_index)` pairs.

## `pbt.py` — rendering and parsing

Nine hundred lines, of which the live path is small. `probe.py` and `audit.py` use:

| | |
|---|---|
| `render(name, **kw)` | fill a prompt template **in one pass**, refusing to ship one with a hole in it |
| `parse_properties(text)` | the test block → validated source |
| `parse_search_space(text)` | the input block → `(space, error, dropped)` |
| `read_input_lines(blob)` | every candidate line with what it parsed to, or why it did not |
| `input_block(text)` | the fenced block the inputs live in |

`render` raises on a missing or empty substitution. Two real defects made that necessary: a template
keeping a literal `{code}` returned a completion that looked like any other, so *a prompt we never
asked was recorded as an answer we did*; and substituting key by key let an early value's own
`{code}` be expanded by a later key, splicing the candidate's source into the specification.

`parse_search_space`'s third return is a **count**, not a flag: `0` clean, `n` lines lost, `None`
when some were lost and the number is unrecoverable (a truncated array cannot say what it meant).

Everything else in the module — `property_prompt`, `search_prompt`, the soundness gate — belonged to
the deleted orchestrator and is now reached only by `tests/test_parsers.py`. `critique_prompt`,
`plan_prompt`, `write_from_plan_prompt` and `degraded` have no caller at all.

## `launch.py`

```python
launch(run_id, argv)   # detached tmux session named after the run id
alive(run_id) · pane(run_id) · kill(run_id) · console_log(run_id)
```

Raises `LaunchFailed` if the session dies within a few seconds of starting, with the captured output
— so a mistyped flag surfaces at launch rather than as an empty `runs/` in the morning. Refuses a
run id already running, because two processes writing one run directory corrupt it.

`probe.py --detach` is the only caller of `launch`; notebooks import `alive` and `pane` to watch.

## `search.py` and `scoring.py`

`search.py` is local trigger generation — constant mining, boundary values, coverage-guided fuzzing.
No model calls. `probe.py` does not use it: the model writes its own inputs. It is reached through
`harness.run_search`, and `reach_rate.py` imports its strategies directly to compare them.

`scoring.py` wraps control_arena for ground-truth correctness, including `CorrectedAppsSetting` —
the stock APPS scorer treats stderr warnings as fatal, which false-negatives modern-Python
solutions.

## Not reached by anything live

`backends/bcb.py` and `backends/mock.py`. `mock` supported the deleted orchestrator's offline
determinism check and now only `tests/test_architecture.py` constructs it. `bcb` is the
BigCodeBench adapter and is the starting point whenever that run happens — note its `preprocess`
**silently skips** tasks missing from the dataset, printing a warning and shrinking the pool, which
is the pattern `outcome.py` exists to prevent.
