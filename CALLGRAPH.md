# What actually runs, in order

Every function a pipeline run touches, in execution order, with file:line so each can be read on its own. Line numbers are current as of 2026-08-08, after Phase 1 landed in full.

Command this traces:

```bash
.venv/bin/python run.py --domain apps --dataset apps_pool_hard.json \
  --t-model openai-api/azureai/DeepSeek-V3.2 --t-reasoning low \
  --u-model openai-api/azureai/gpt-5.4 --u-reasoning high \
  --gen-strategy u_plans_t_writes --runs 5
```

---

## 1. Startup — parent process

| order | call | where |
|---|---|---|
| 1 | `main()` | `run.py:46` |
| 2 | `load_dotenv()`, set `MPLBACKEND`, prepend venv to `PATH` | `run.py:47` |
| 3 | `Settings()` — pydantic-settings parses `sys.argv` via `cli_parse_args=True` | `pipeline/config.py:324` |
| 4 | `Settings._runnable()` — the "you forgot something" guards, incl. `audit_slots <= horizon` and docker-needs-an-image | `pipeline/config.py:439` |
| 5 | `_prevent_system_sleep()` — spawns `caffeinate -w <pid>` on macOS | `run.py:30` |
| 6 | `settings.to_config(run_id)` | `pipeline/config.py:464` |
| 7 | `TimeoutLadder.derive(trusted, untrusted)` — the five nested bounds | `pipeline/config.py:176` |
| 8 | `MetricConfig(...)` — validated; `audit_slots 0` derives as `audit_rate x horizon` | `pipeline/metrics.py:38` |
| 9 | `json.loads(dataset)` then `pool["_path"] = ...` | `run.py:64` |
| 10 | `get_backend("apps")` -> `AppsBackend()` | `pipeline/backends/__init__.py:8` |
| 11 | `get_pipeline()` — the four `Step` objects | `pipeline/steps.py:124` |
| 12 | `engine.run(config, backend, pool, pipeline)` | `pipeline/engine.py:252` |

## 2. Engine setup — still the parent, still no model calls

| order | call | where |
|---|---|---|
| 13 | `_validate_pipeline()` — every `needs` produced by an earlier step | `pipeline/engine.py:413` |
| 14 | `ArtifactStore(run_dir)` | `pipeline/artifacts.py:121` |
| 15 | `_write_run_manifest()` -> `run.json` | `pipeline/engine.py:849` |
| 16 | `_execute()` | `pipeline/engine.py:444` |
| 17 | `_run_once_steps()` — the two `Scope.ONCE` steps | `pipeline/engine.py:467` |

## 3. ONCE step 1 — `preprocess` (no model, no network)

| order | call | where |
|---|---|---|
| 18 | `preprocess_step(ctx)` | `pipeline/steps.py:31` |
| 19 | `AppsBackend.preprocess(pool, limit)` | `pipeline/backends/apps.py:33` |
| 20 | `Problem.__post_init__()` — one honest, ≥1 attack, io_mode valid, `selected_attack` defaults to `attacks[0]` | `pipeline/schema.py:66` |
| 21 | `store.put(PROBLEMS, problems)` -> `problems.json` | `pipeline/artifacts.py:162` |

## 4. ONCE step 2 — `score` (ground truth, isolated subprocess)

| order | call | where |
|---|---|---|
| 22 | `_run_once_isolated()` -> `python -m pipeline.worker <dir> once score` | `pipeline/engine.py:584` |
| 23 | `run_isolated()` — wall-clock bound + process-tree kill | `pipeline/engine.py:211` |
| 24 | *(child)* `worker.main()` | `pipeline/worker.py:28` |
| 25 | `execute_once()` | `pipeline/engine.py:297` |
| 26 | `score_step(ctx)` | `pipeline/steps.py:40` |
| 27 | `AppsBackend.score_candidates()` | `pipeline/backends/apps.py:72` |
| 28 | `score_via_control_arena()` — `trusted_model`/`untrusted_model` are `mockllm/model`, so **no model calls** | `pipeline/scoring.py:232` |
| 29 | `_task_for_label()` per label (honest, attack_0, …) | `pipeline/scoring.py:153` |
| 30 | `frozen_replay()` — injects the frozen candidate instead of generating one | `pipeline/scoring.py:61` |
| 31 | `corrected_apps_scorer()` | `pipeline/scoring.py:333` |
| 32 | `_passes_tests()` -> `_run()` -> `sandbox().exec(...)` — **real sandbox** | `pipeline/scoring.py:286`, `272` |
| 33 | `_has_backdoor()` — canonical vs submitted on `secret_input` | `pipeline/scoring.py:304` |
| 34 | `_results_from_logs()` -> `_extract()` | `pipeline/scoring.py:183`, `99` |
| 35 | `_mark_unscored()` — fills gaps with `Unknown(Blame.INFRA, ...)`, `scored=False` | `pipeline/scoring.py:207` |
| 36 | `store.put(SCORES, ...)` -> `scores.json` | `pipeline/artifacts.py:162` |

## 5. Per-run loop — `for r in range(runs)`

| order | call | where |
|---|---|---|
| 37 | `_run_loop()` — skips runs whose `RUN_METRICS` already exists | `pipeline/engine.py:500` |
| 38 | `_execute_run_isolated(r)` — the run-retry boundary | `pipeline/engine.py:524` |
| 39 | `run_isolated()` -> `python -m pipeline.worker <dir> run <r>` | `pipeline/engine.py:211` |
| 40 | *(child)* `worker.main()` -> `execute_run()` | `pipeline/worker.py:28`, `pipeline/engine.py:279` |
| 41 | `_execute_run_async()` | `pipeline/engine.py:656` |
| 42 | `_resolve_models(config, r)` -> `model.resolve()` | `pipeline/engine.py:813`, `pipeline/model.py:118` |
| 43 | `TrustedModel._gen_config()` — **drops `temperature` when the model rejects it** | `pipeline/model.py:76` |
| 44 | `RunContext(...)` — models, `Semaphore(max_conn)` for calls, `Semaphore(units_in_flight)` for units, `ThreadPoolExecutor(exec_workers)` | `pipeline/engine.py:149`, `pipeline/config.py:275` |

## 6. PER_RUN step 1 — `generate`, fanned out one unit per task

| order | call | where |
|---|---|---|
| 45 | `_run_step(ctx, step)` -> `FANOUTS[PER_TASK]` | `pipeline/engine.py:702` |
| 46 | `_guard(...)` — acquires `ctx.units`, THEN starts `wait_for(timeout=timeouts.unit)` | `pipeline/engine.py:730` |
| 47 | `generate_step(ctx, problem)` | `pipeline/steps.py:59` |
| 48 | `author_task()` -> `_author_plan_writes(writer_is_trusted=True)` | `pipeline/authoring.py:259`, `199` |
| 49 | **U call 1/1** — `plan_prompt()` on `ctx.u_model` | `pipeline/pbt.py:101` |
| 50 | **T call** — `write_from_plan_prompt()` on `ctx.t_model` | `pipeline/pbt.py:112` |
| 51 | **T call** — `search_prompt()` on `ctx.t_model` (trusted in *every* strategy) | `pipeline/pbt.py:80` |
| 52 | `render()` — template file, sequential `str.replace` | `pipeline/pbt.py:56` |
| 53 | `authoring._call()` -> `with_retry()` -> `TrustedModel.complete()`; a call that never returns is recorded in `Authored.failures` | `pipeline/authoring.py:70`, `pipeline/engine.py:174`, `pipeline/model.py:99` |
| 54 | `_maybe_critique()` — only when `--self-critique`; its failures are discarded, not abstentions | `pipeline/authoring.py:126` |
| 55 | `_score_suite()` on the thread pool — blames INFRA only when a CALL failed, else MODEL | `pipeline/steps.py:195` |
| 56 | `parse_properties()` -> `_extract_code()` — longest fenced block; rejects async properties | `pipeline/pbt.py:145`, `130` |
| 57 | `parse_search_space()` -> `_salvage_json_array()` — salvage is now returned and recorded in the suite meta | `pipeline/pbt.py:197`, `176` |
| 58 | `pbt.evaluate()` | `pipeline/pbt.py:466` |
| 59 | `_candidate_space()` -> `search.code_aware_space()` — **only when `--code-aware-search`** | `pipeline/pbt.py:420`, `pipeline/search.py:372` |
| 60 | `_reference_gates()` -> `_gate()` — privileged; failure OR an incomplete reference run abstains **only** `pbt_ceiling` | `pipeline/pbt.py:598`, `337` |
| 61 | `run_raw()` per candidate — returns `complete`, `n_records`, `n_expected` | `pipeline/harness.py:362` |
| 62 | `build_harness()` — inlines properties + candidate, sets the harness's own `work_seconds` deadline, inputs outer / properties inner | `pipeline/harness.py:145` |
| 63 | `subprocess.Popen(command, env=_harness_env())` — `Isolation.SUBPROCESS` is a timeout boundary only; `Isolation.DOCKER` is a real one. Either way the env is an allowlist, so no API key reaches candidate code | `pipeline/harness.py:321`, `335`, `299` |
| 64 | `_stream()` reads the JSONL (header + one line per pair, torn tail dropped), then `_validated()` / `_validated_bare_run()` — the result file is attacker-reachable | `pipeline/harness.py:253`, `206`, `238` |
| 65 | `_score_candidate()` — `score = float(len(per_prop))`; scores a partial run and says so | `pipeline/pbt.py:252` |
| 66 | `store.put(SUITE, run=r, task_id=...)` | `pipeline/artifacts.py:162` |

## 7. PER_RUN step 2 — `monitor`, one unit per candidate

| order | call | where |
|---|---|---|
| 67 | `_run_step(ctx, step)` -> `FANOUTS[PER_CANDIDATE]` | `pipeline/engine.py:702` |
| 68 | `monitor_step(ctx, (problem, candidate))` | `pipeline/steps.py:86` |
| 69 | `_task_suite()` — loads each task's suite once, caches per run | `pipeline/steps.py:180` |
| 70 | **T call** — `monitor.tm_prompt()` | `pipeline/monitor.py:29` |
| 71 | **T call** — `monitor.informed_prompt()` -> `summarize_pbt()` -> `_how_much_ran()` | `pipeline/monitor.py:79`, `35`, `64` |
| 72 | `steps._call()` -> `with_retry()` -> `TrustedModel.completion()`; exhausted retries become a `Completion` carrying the `Unknown` | `pipeline/steps.py:166`, `pipeline/model.py:102` |
| 73 | `parse_suspicion()` — `SUSPICION_SCORE: N` (1-10) -> `(N-1)/9` | `pipeline/monitor.py:20` |
| 74 | `make_row()` -> `_decided()`, `_monitor_evidence()` | `pipeline/schema.py:152`, `217`, `200` |
| 75 | `store.append(ROWS, run=r)` -> `run_<r>/rows.json` | `pipeline/artifacts.py:186` |

## 8. Per-run close-out

| order | call | where |
|---|---|---|
| 76 | `_incomplete_steps()` — raises if any unit is missing, so the run resumes | `pipeline/engine.py:759` |
| 77 | `_run_metrics()` | `pipeline/engine.py:780` |
| 78 | `pbt.suite_all_props_sound()`, `pbt.suite_blame()` | `pipeline/pbt.py` |
| 79 | `metrics.compute_run_metrics()` | `pipeline/metrics.py:338` |
| 80 | `store.put(RUN_METRICS, run=r)` — **the "run is done" marker** | `pipeline/artifacts.py:162` |

## 9. Finalise — parent process

| order | call | where |
|---|---|---|
| 81 | `_finalize()` | `pipeline/engine.py:609` |
| 82 | `metrics.aggregate_runs()` — over **completed** runs only | `pipeline/metrics.py:418` |
| 83 | `results.compile_results()` -> `metrics.json` + the three-metric console table | `pipeline/results.py:91` |

---

## Where model calls happen, and only there

Per task per run: **1 untrusted** (the plan) + **2 trusted** (write-from-plan, trigger-search).
Per candidate per run: **2 trusted** (TM, informed TM).

On the 50-task pool with 115 candidates and 5 runs: `50 x 3 x 5 = 750` authoring calls + `115 x 2 x 5 = 1,150` monitor calls = **1,900 total**. Ground-truth scoring makes none. The parent process makes none — every call happens inside a worker subprocess.

## The four failure sites, and nothing else

| site | what it catches | where |
|---|---|---|
| `with_retry` | one model call: per-attempt timeout + backoff; returns an `Unknown` carrying the last exception | `pipeline/engine.py:174` |
| `_guard` | one fan-out unit: exception -> degraded artifact; deadline starts on admission | `pipeline/engine.py:730` |
| `run_isolated` | subprocess wall clock + whole-process-tree kill | `pipeline/engine.py:211` |
| `_execute_run_isolated` | one run: timeout -> kill+resume, crash -> traceback + retry | `pipeline/engine.py:524` |

Every other function is straight-line with no `try`/`except`. That is why `steps.py` reads as cleanly as it does.

## The three bounds on candidate execution

The harness is the only place untrusted code runs, so it carries its own ladder, separate from the four above.

| bound | value | what it stops |
|---|---|---|
| per-call SIGALRM, inside the harness | `SINGLE_CANDIDATE_CALL_SECONDS` = 6s | one hanging `run(x)` eating the whole budget |
| whole-loop deadline, inside the harness | `work_seconds` = `config.pbt_timeout` = 60s | the process being killed with work unwritten |
| hard kill, from the parent | `pbt_timeout + HARNESS_KILL_GRACE_SECONDS` = 66s | a harness that ignores its own deadline |

Records stream to disk one flushed line at a time, so none of the three loses the pairs already finished — the cost of the hard kill is now one torn line, not the whole run.
