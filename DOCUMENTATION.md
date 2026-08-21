# `probe.py` and `audit.py`

Two halves of one experiment, split by whether they cost money.

| | |
|---|---|
| **`probe.py`** | runs an arm: writes tests, executes them, stores the result. Model calls, docker, hours. |
| **`audit.py`** | reads a finished run. No model calls, no execution, instant. Everything a notebook uses. |

Nothing in `audit.py` can change a result, and nothing in `probe.py` needs to be imported to read one.

---

## `probe.py` — running an arm

```
.venv/bin/python probe.py --detach --run-id a2-hard50 \
    --pool apps_pool_hard.json --split splits/apps_hard_20_30.json \
    --resolve forbidden --code visible --runs 1 --tests 10 --inputs 30 \
    --max-tokens 32000 --call-timeout 300 --timeout 600
```

For each candidate it makes **one** call that writes both the tests and the trigger inputs, runs
every test against every input in docker, and separately asks the trusted monitor for a 1–10
suspicion score.

### Flags that change the experiment

| flag | values | what it changes |
|---|---|---|
| `--resolve` | `forbidden` · `bounded` · `allowed` | may a test compute the correct answer itself? `forbidden` bans it, `bounded` allows it behind a declared size guard, `allowed` is unrestricted. This is the main arm axis. |
| `--code` | `visible` · `hidden` | does the test-writer see the submission, or only the specification? `hidden` is the spec-blind control. |
| `--runs` | int, default 1 | repetitions per candidate. Above 1 the temperature goes 0.0 → 0.7 and the seed becomes `seed + i`, so repetitions genuinely differ. Every error bar comes from this. |
| `--tests` / `--inputs` | ints | suite size: tests × inputs is the execution grid per candidate. |
| `--split` | path | which tasks are train and which are test. The audit threshold is fitted on train honest scores only. |
| `--detach` | flag | start in a tmux session named after the run id and return immediately. Raises if the command dies on startup; refuses a run id already running. |

`--run-id` resumes. A killed run costs at most one in-flight call.

### What it writes

```
runs/<run-id>/
  probe.json                                  every verdict, all repetitions
  console.log                                 stdout, only for diagnosing a failed launch
  suites/<task>_<label>/run_<i>/
      tests.py                                the suite, as parsed and executed
      inputs.json                             the trigger inputs it guessed
      completion.txt                          raw model output, before either parser
```

A verdict holds: `run`, `task_id`, `split`, `candidate_id`, `label`, `fired` (test names),
`catches` (`{test, input_index}` pairs), `n_tests`, `n_inputs`, `n_pairs_run`, `n_pairs_expected`,
`salvaged`, `pbt_unknown`, `tm`, `tm_unknown`, `tm_reasoning`.

`pbt_unknown` and `tm_unknown` are set when a measurement did not happen. They are never zero and
must never be read as "nothing fired" — that mistake is the reason this repo has an `Unknown` type.

`salvaged` means the input list parsed to fewer entries than the model wrote. Worth watching: in
`a2-hard50` it was 48 of 100, caused by the model writing Python expressions where the format
demands literal JSON.

### Internals, if you need them

| | |
|---|---|
| `probe(...)` | authors and scores every candidate concurrently, then runs each suite in turn |
| `author(...)` | one authoring call, parsed; returns `Authored` or `Unknown` |
| `tm_score(...)` | the monitor call; returns `Rated(score, unknown, text)` |
| `execute(...)` | every test over every input against one candidate, in docker |
| `build_prompt(...)` | fills the authoring template — the same call `audit.prompt` uses to re-render |
| `load_problems(pool, ids)` · `problem_from_task(id, task)` | pool → `Problem` records |
| `fit_threshold(honest, rate)` | lowest score auditable within a false-alarm budget; `Unknown` when none is affordable |
| `calibrated_table` · `pbt_table` · `score_levels` | the console tables printed at the end of a run |
| `suite_dir(out, task, label, i)` | where one candidate's suite lives |

---

## `audit.py` — reading a finished run

```python
import audit
audit.use("a2-hard50")           # set once; every call below then takes only a candidate id
audit.reach("apps_3945_attack_0")
```

Every function takes `run=""` (defaults to whatever `use()` set) and, where it reads something
written per repetition, `run_index=0`. Nothing prints; everything returns a value, so one cell shows
one fact.

### Which run, which candidate

| | |
|---|---|
| `use(run_id)` | choose the run every call below reads |
| `candidates(run="")` | every verdict — one per candidate per repetition |
| `verdict(cid, run_index=0)` | one candidate's scores. Excludes `tm_reasoning`, which has its own accessor |

### Ground truth, from the pool

These do not take `run_index` — ground truth does not change between repetitions.

| | |
|---|---|
| `task_spec(cid)` | the problem statement |
| `honest_code(cid)` | the honest submission for that task |
| `attack_code(cid)` | the backdoored submission for that task |
| `code(cid)` | whichever of the two this id actually names |
| `reference(cid)` | the reference solution |
| `trigger(cid)` | **the input the backdoor was built to fire on.** Never a guess |

### What the model produced

| | |
|---|---|
| `tests(cid, run_index=0)` | the whole suite, as parsed and executed |
| `test_source(cid, name, run_index=0)` | one test function by name — a suite has ten and usually one fired |
| `inputs(cid, run_index=0)` | the trigger inputs it guessed, in execution order |
| `completion(cid, run_index=0)` | raw model output, before either parser |
| `prompt(cid, run_index=0)` | the authoring prompt, re-rendered from the flags the run recorded |
| `tm_prompt(cid)` | what the monitor was asked |
| `tm_reasoning(cid, run_index=0)` | what the monitor answered, before its score was parsed out |

### What happened

| | |
|---|---|
| `flagged(cid, run_index=0)` | `[{test, input_index, input}]` — which test fired **and on what**|
| `reach(cid, run_index=0)` | **was the real trigger among the guessed inputs?** Raises for an honest candidate, which has no trigger |

`reach` is the first thing to look at on a miss. `False` means the suite never executed the backdoor
— a search failure, which no oracle could have saved. `True` means it ran the trigger and did not
notice — an oracle failure. Those call for opposite work and no aggregate rate separates them.

The same distinction applies to a catch: a firing counts in every table, but it is **earned** only
if some test fired on the real trigger. On `smoke3`, 3 of 4 catches were unearned.

### Everything raises

An accessor never returns an empty value to stand in for a missing one. Asking for `flagged` on a
run that stored only test names raises; asking for `reach` on an honest candidate raises; a
`run_index` the run does not have raises and names the ones it does. A blank output is a bug, never
a null result.

---

## The rest

| file | |
|---|---|
| `analyse_probes.py` | held-out metrics: `load_arm(run, i)`, `common_population`, `auroc`, `operating_points`, `best_at_budget`, `union_rule` |
| `deployment_game.py` | trigger-then-audit simulation over stored scores, importable only: `load_runs`, `sweep`, `simulate`, `TriggerRule` |
| `pipeline/` | the shared library — harness, model, monitor prompts, parsers, config, metrics, launcher |
| `pipeline/launch.py` | `launch(run_id, argv)` starts a run detached in tmux and proves it started |
| `notebooks/run.ipynb` | launch → watch → audit → metrics → deployment, for a real run |
| `notebooks/demo.ipynb` | the same surface on `smoke3`, for learning what is available |

`load_arm` and `load_runs` both take a repetition index. A run with `--runs 2` holds two verdicts per
candidate, and keying them by candidate alone silently keeps whichever came last.
