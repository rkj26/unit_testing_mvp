# Why the multi-turn study is slow, and what would speed it up

The full-pool chain (MT5) took **112.7 h end to end, but only 21.9 h of that was compute**. The
other **90.7 h (80%)** the chain sat stopped at `UnretriedInfraFailures` after arm A, waiting for a
person to retry and accept 14 infra lines. The compute itself is slow because every model call now
produces about 55–60k characters of reasoning plus answer and takes about 100–130 s of worker time,
with 8 calls in flight per run. Before 10 October the same prompts produced 2.5–6× less output, so
the provider change accounts for about two-thirds of the compute but none of the wait. Docker is
under 1% of the time.

Recommendation: (1) apply the retry-once-then-accept policy automatically at the gate, which saves
about 91 h with no effect on comparability; (2) raise in-flight requests from 8 to 24–32 per run,
with a separate cap on concurrent Docker grids, which cuts compute about 3× and keeps results
comparable. The runner-up, shorter outputs via a non-reasoning deployment, would make results
incomparable.

---

## Sources, and what cannot be measured

- **No record carries a timing field.** `calls[]` holds `prompt, raw, reasoning, rep, stop_reason`
  and nothing else. Inspect's trace logs (`~/Library/Application Support/inspect_ai/traces/`) only
  go back to August. Per-call latency, HTTP retries that succeeded inside inspect, and per-grid
  Docker time are therefore **not measured** anywhere.
- **Spans** come from APFS file birth and modification times: `console.log` birth is the first
  launch, and its mtime is the end of the last session, because `tee` truncates on resume. They
  also come from the pre-retry backups in `archived/mt-failed-2026-10-13/`, the driver logs
  `archived/mt-{full,u400}-driver*.log` and `archived/r2_smoke_driver.log` (the only log with
  timestamps), and the times written in `experiments/multi_turn_plan.md` and `scale_plan.md`. Every
  `records.jsonl` birth time was reset by a bulk rewrite at 2026-10-20 19:34, so those were not
  used.
- **Worker-seconds per call** = span × 8 workers ÷ calls. This assumes all 8 workers stay busy. The
  last wave of each run under-uses them, so the figure is an upper bound on mean call time. It
  includes the ~2 s sandbox run and any retry time.
- Output size is characters, `len(reasoning) + len(raw)`. Token counts in `archived/r1_cost.tsv`
  are these characters ÷ 3.5, not provider-reported.

## 1. Wall clock per arm and per candidate

### Full pool, MT5: 2,776 candidates, `data/apps_full.json`

| Stage | From | To | Span | Model calls | Wall s / candidate | Worker-s / call |
|---|---|---|---|---|---|---|
| Smoke chain (1 task) | 10-15 10:02:05 | 10:10:52 | 8.8 min | 8 | — | — |
| Triggers | reused `trig-all` | — | 0 | 0 | 0 | — |
| A traceable, main | 10-15 10:11:15 | ≤ 22:19:52 | 12 h 09 m | 2,761 | 15.7 | **127** |
| A, retry of 21 API failures | 22:19:52 | ~22:30 | ~10 min | 21 | 0.2 | — |
| **Stopped at infra gate** | 10-15 ~22:30 | 10-19 17:11:24 | **90 h 41 m** | 0 | **117.6** | — |
| A, retry of 14 infra lines | 17:11:24 | 17:16:43 | 5.3 min | 14 | 0.1 | — |
| Replay (Docker only) | 17:18:07 | 17:30:40 | 12.6 min | 0 | 0.27 | 2.2 per grid |
| B ‖ C, main | 17:30:44 | ≤ 10-20 02:39:15 | 9 h 08 m | 2,741 + 2,741 | 11.9 | **96** each |
| B/C, retry of 4 API failures | 02:39:49 | 02:41:56 | 2.1 min | 4 | 0.05 | — |
| **Total** | 10-15 10:02 | 10-20 02:42 | **112.7 h** | 8,243 + retries | **146** | — |

Compute only, without the gate: **21.9 h, 28.4 s per candidate**.

### uniform400, MT2: 800 candidates, ran alongside MT5

| Stage | Span | Worker-s / call |
|---|---|---|
| A main, 10-15 10:07:16 → ≤ 13:17:37 | 3 h 10 m | 115 |
| Stopped at infra gate, 10-15 ~13:20 → 10-19 17:11 | **~99 h 50 m** | — |
| Replay, 17:15:15 → 17:19:59 | 4.7 min | 2.8 per grid |
| B ‖ C main, 17:20:00 → ≤ 20:05:59 | 2 h 46 m | 101.5 each |
| **Total**, 10-15 10:02 → 10-19 20:20 | **106.3 h** (compute ≈ 6.2 h, gate 94%) | — |

### smoke30, R2 smoke: 60 candidates, 10-20/21, post-outage, timestamped driver

| Stage | Span | Worker-s / call |
|---|---|---|
| Fresh trigger search `trig-all-r2-smoke` | 14.6 min | 117 (153 at the 64k cap) |
| A | 14.6 min | 123 |
| Replay | 24 s | 3.4 per grid |
| B ‖ C | 12.6 min | 102 / 106 |

### Against a single-turn suite arm on the same pool

| Pool | Single-turn arm, period | Span | Wall s / cand | Worker-s / call | Chain compute | Chain end to end |
|---|---|---|---|---|---|---|
| full | `ut-all-plain_v5-10`, 10-09, pre-outage, ran alone | 4 h 42 m | 6.1 | 49 | 21.9 h (**4.7×**) | 112.7 h (24×) |
| u400 | `ut-u400-property-10`, 09-14, pre-outage | 58 min | 4.3 | 35 | 6.2 h (**6.4×**) | 106.3 h (110×) |
| smoke | `ut-all-property-10-r2-smoke`, 10-20, post-outage | 12.9 min | — | **108** | arm A on the same smoke: 123 | — |

`ut-all-property-10` itself has no clean span: it was spread over 10-05 → 10-09 with a reboot and
concurrent runs.

**Per arm, the multi-turn design is not slower than a single-turn arm.** Under today's provider, a
single-turn suite call (108 worker-s) costs about the same as an arm-A call (123) on the same 57
candidates. The chain is slower for three reasons: three model arms per candidate instead of one
(2.97 calls per candidate); B and C cannot start until A and the replay finish; and the gate.

## 2. Where the time goes

### Per candidate, full pool, wall clock (146 s end to end)

| Cause | s / candidate | Share |
|---|---|---|
| Stopped at arm A's infra gate, waiting for a human | 117.6 | 80.5% |
| Model calls, arm A (8 in flight) | 15.5 | 10.6% |
| Model calls, B ‖ C (16 in flight) | 11.6 | 8.0% |
| Docker sandbox: A grids, replay, B/C grids | 0.8 | 0.5% |
| Relaunches to retry infra or API lines | 0.4 | 0.3% |
| Smoke chain and gaps between stages | 0.2 | 0.2% |

### Model calls

- **One call per candidate per arm**: A, B and C, so 3 per candidate. The trigger search was
  reused, so it made no call. Calls: A 2,761, B 2,741, C 2,741. 15 candidates had no inputs, and a
  further 20 had no saved A response.
- **Duration**: 127 worker-s per call in A and 96 in B and C (115 and 101.5 on u400). This is the
  mean, including the ~2 s sandbox and retries. Per-call latency itself is not recorded.
- **Output length per call**:

| Arm | Mean | p10 | p50 | p90 | p99 | Calls with reasoning | Hit 32k cap |
|---|---|---|---|---|---|---|---|
| A | 59,933 | 39,636 | 58,099 | 82,798 | 109,730 | 100% | 25 |
| B | 53,822 | 36,462 | 51,928 | 73,382 | 97,739 | 100% | 6 |
| C | 51,749 | 35,011 | 50,194 | 70,084 | 95,769 | 100% | 4 |

  Prompts are 10.7k, 14.1k and 17.5k characters, so prefill is small next to decoding.
- **Time tracks output length.** This is the strongest evidence that decoding is the cost:

| Run | Period | In flight | Worker-s / call | Mean output chars | chars / s |
|---|---|---|---|---|---|
| `mwt-full-all-plain_v3-10` | pre | ~24 | 24.9 | 9,210 | 370 |
| `mwt-full-postoutage-plain_v3-10` (same protocol and prompt) | post | ~16 | 62.1 | 22,706 | 366 |
| `ut-u400-property-10` | pre | 16–24 | 35.0 | 9,991 | 285 |
| `ut-all-plain_v5-10` | pre | 8 | 49.0 | 22,661 | 462 |
| A full | post | 8–16 | 126.7 | 59,933 | 473 |
| B / C full | post | 16–32 | 96.1 | 53,822 / 51,749 | 560 / 539 |
| A u400 | post | 16 | 115.4 | 60,229 | 522 |
| B / C u400 | post | 32 | 101.5 | 53,584 / 52,395 | 528 / 516 |

  Within the one paired protocol, time rose ×2.49 and output ×2.47.

### Docker sandbox

The replay runs exactly A's suites over A's inputs, with nothing else in the process. It is the
clean measurement: **2,718 grids in 753 s at 8 workers, 2.2 worker-s per grid** (u400 2.8, smoke30
3.4). Two of the 2,718 hit the 246 s kill (8% of the replay's worker time) and 8 were OOM (exit
137, fast). In A, B and C the 246 s kill fired on 1, 2 and 5 grids: at most 0.5% of any arm. The
sandbox is not worth optimising.

- R2's per-call `python -c` stdio runner (committed 10-26) starts a fresh interpreter for every
  `run(x)`, at least 300 per grid. Its cost per grid is not measured at scale, and whether smoke30
  used it is not recorded in the artifact.

### Retries and timeouts

- **A:** 21 API failures in the main session (9 `AttemptTimeoutError`, 12 connection or other), all
  recovered in a ~10 min relaunch. Each held a worker for at most 2 × 300 s + 60 s, so they cost at
  most **3.9% of A's worker time**, an upper bound. The 14 infra lines left after that were
  11 sandbox and 3 carried over from `trig-all`. None came from the API.
- **B/C:** 1 and 3 API failures, retried in 2 min.
- Retries that succeeded inside inspect (`max_retries=1`, attempt 300 s, budget 600 s) leave no
  trace in the records and cannot be counted.

### Waiting on upstream

- B and C depend on A's complete records plus the replay. `write_source_bundle` hashes them whole,
  so 12.4 h of A and replay are strictly serial before B and C start. The trigger search was reused,
  so it added no wait in MT5. A fresh one, as R2 needs (`trig-all-r2`), would add about **14.7 h**
  before A: 2,776 × 153 worker-s ÷ 8, projected from `trig-cap64k-r2-smoke`.
- **The gate.** `_stop_on_infra_failures` raises after A whenever any infra line exists, and the
  chain then waits for a person. That cost 90.7 h on the full pool and ~100 h on u400. The same
  stop will recur in R2: `experiments/rerun_r2.py` calls `study.run(allow_paid=True)` without
  `accept_infra_failures`, and only records the error.

### Serial versus concurrent

- **Within a run:** `ThreadPoolExecutor(WORKERS=8)` (`pipeline/protocols/base.py:49`). Each worker
  makes one model call, then one Docker grid, in series. `max_connections = WORKERS = 8` is per model
  and per process (`unit_testing.py:730`), so it does not bind. `model.MEASURED_SAFE_CONCURRENCY =
  12` is unused, and its measurement is not in the repo.
- **Across runs:** A and the replay run alone. B and C run concurrently (16 in flight). MT2 and MT5
  overlapped, which put 16 in flight on 10-15 and 32 in flight from 10-19 17:20 to 20:06.
- **The provider kept scaling with load as far as anything has measured.** u400 B/C ran entirely
  at 32 in flight and averaged 101.5 s per call. Full B/C, splitting their span into 2 h 46 m at
  32 and 6 h 22 m at 16, imply about 94 s per call at 16. That is about **+8% latency for 2× the
  requests in flight** (derived, assuming equal call lengths: 53.6k against 53.8k characters). The R2
  smoke had about 7 runs × 8 = ~56 in flight from 23:50 to 23:57 with **zero API failures** and
  102–123 worker-s per call (n = 57 per run, a 13-minute window). Azure's per-deployment quota is
  not recorded anywhere in the repo.
- The driver's `_follow_together` re-reads both ~250 MB `records.jsonl` files every 2 s (12,264
  polls during B ‖ C). This costs CPU in the driver process only, is off the critical path, and is
  unmeasured.

## 3. How much is the 10 October provider change

| Evidence | Pre | Post | Ratio |
|---|---|---|---|
| Same prompt, same 57–59 smoke candidates, output chars: `ut-all-property-10` | 8,921 (0% reasoning) | 56,460 (100%) | **6.3×** |
| … `ut-all-plain_v3-10` | 7,681 | 50,658 | 6.6× |
| … `ut-all-plain_v5-10` | 28,844 | 51,645 | 1.8× |
| … `trig-all` / `tm-all` | 3,401 / 3,793 | 45,422 / 30,220 | 13× / 8× |
| Same protocol and pool, worker-s per call: `mwt-full-*-plain_v3-10` | 24.9 | 62.1 | **2.5×** |
| Same class and pool, arm A against the single-turn suite arm: full | 49 (`plain_v5`) | 127 | **2.6×** |
| … u400 | 35 (`property`) | 115 | **3.3×** |

**Reading.** The provider change multiplies per-call time by about 2.5–3.3×. That puts **about
13–15 h of the 21.9 h compute (60–70%)** on the provider; pre-outage, the same chain would have
taken about 7–9 h of compute. It accounts for **none of the 90.7 h gate wait**, so its share of the
112.7 h end to end is about 12–13%. Caveat: the `traceable_v1` and revision prompts were never run
on DeepSeek before 10 October, so their pre-outage cost is borrowed from the other suite prompts,
not measured.

## 4. Improvements, ranked by expected saving

| # | Change | Expected saving (full pool) | Comparable with existing runs? |
|---|---|---|---|
| 1 | **Retry once, then accept, automatically at the gate.** Have `_stop_on_infra_failures` drop the infra lines, resume once, then carry what remains as exclusions. This is the policy approved by hand on 10-19, which recovered 6 of 14 lines (u400: 3 of 9). At minimum, notify the user when the chain stops. | **−90.7 h** (−80% end to end); u400 −100 h | **Yes.** Same policy, same records. It is a decision about who decides, so it needs the user's approval. |
| 2 | **More requests in flight.** Raise `WORKERS` (and with it `max_connections`) from 8 to 24–32 for model-bound runs, and put a semaphore of ~8 around `sandbox.run_raw`. Docker already shows OOMs and 246 s kills at 8, and E11 ran sandbox jobs two at a time. Never set `max_connections` below `WORKERS`. | Compute 21.9 h → **~8 h at 24, ~6 h at 32** (A 12.1 → 3–4 h; B ‖ C 9.1 → 2.3–3 h), *if* the scaling seen at 32 (full scale) and ~56 (smoke scale) holds | **Yes.** No prompt, cap or model change. `WORKERS` is not in `config.json`, so existing runs resume as themselves. Risk: more API timeouts under load, which become retryable infra lines. Azure quota unknown. |
| 3 | **Shorter outputs.** The provider ignores `reasoning_effort` (TM at `high` reasoned no longer than at `low`), and median A output is about 58k characters (~16.6k estimated tokens). A lower `max_tokens` would cut off about half the calls, so only a non-reasoning deployment recovers the 2.5–3.3×. | Compute ÷ 2.5–3.3 (**−13 to −15 h**) | **No.** It changes the model, so it is incomparable with every existing run. |

**Not recommended.** Each of these was considered and left out:

- **Pipelining B and C behind A per candidate** would save about 9 h at today's concurrency. It
  would require redesigning the whole-run source bundle and the A-level gate, and #2 gives the same
  extra concurrency for a constant change.
- **Fixing B and C's 18% format failures** would not speed anything up. Those 523 and 497 calls
  were paid and produced no measurement, and a prompt fix would break comparability.
- **Sandbox tuning** has nothing to win: under 1% of the time.

**For R2 specifically**, at today's settings: `trig-all-r2` takes about 15 h, then A about 12 h,
then B ‖ C about 9 h, so **about 36 h of compute** at 8 workers before any gate stop. R2 also runs
the chain alongside nine other 8-worker runs (~80 in flight), more than anything measured here.
