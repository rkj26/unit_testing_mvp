# Why the Kimi Stage 1/2 runs were slow, and what would speed them up

**The main cause is per-call latency that the pipeline's defaults were not built for.** Kimi calls
often took longer than the 120 s per-attempt budget that `main` gives `reasoning="low"`. That budget
was tuned on DeepSeek, so every call over 120 s became a paid INFRA failure after holding a worker
for up to 240 s. Nothing retries INFRA records automatically (`Run.pending` treats a failed record as
done), so each batch of failures had to be found, deleted and relaunched by hand. The relaunches
used a patched 600/1,200/1,260 s ladder that exists only on Omar's machine, plus retries of single
cases (983, 4122) and a late recovery (1413). All of it ran at 8 calls in flight. **No stage
duration was measured anywhere in the repo,** so the time split below is bounded and inferred,
not measured.

Recommendation: (1) retry INFRA records automatically once, then accept the rest; (2) raise
`WORKERS` from 8 to 24; (3) give Kimi its own per-call timeout so no call is aborted only to be
re-run. None of these changes prompts, caps or sampling. The runner-up, one TrustedSolve call per
task instead of two, halves Stage 1 but changes results.

---

## 1. What the pipeline is, and which code it ran

| | Stage 1: TrustedSolve | Stage 2: TriggerSearch |
|---|---|---|
| Run | `apps1388-411bf4e-20261018-kimi-solve` | `apps1388-411bf4e-20261018-kimi-trig` |
| Code | `pipeline/protocols/solve.py` `TrustedSolve` | `pipeline/protocols/trigger_search.py` `TriggerSearch` |
| Revision | `411bf4e` (10-18). `pipeline/` on `origin/main` is byte-identical to it | same |
| Per candidate | 1 model call, then 1 Docker grid over ≤30 provided pairs (`sandbox_seconds` 210) | 1 model call. No Docker |
| Calls in final artifact | 2,776 (1,388 tasks × 2, **byte-identical prompt per task**, cache off) | 2,776 (cache on) |
| Model | `openai-api/azureai/FW-Kimi-K3`, `low`, seed 300, runs 1 | same |
| Reads | dataset only | dataset only |
| Read by | no protocol (notebooks only) | `UnitTesting`, `UPlansTWrites`, the multi-turn chain |

- **The stages do not depend on each other.** Each reads only `data/apps_full.json`, and nothing
  downstream reads Stage 1. Stage 1 is therefore off the critical path. Whether Omar ran the two
  stages serially or side by side is not recorded.
- **The multi-turn gate does not apply.** Neither stage goes through
  `multi_turn._stop_on_infra_failures`. The equivalent stop is in `base.py`: `Run.pending()`
  (lines 292–299) skips every candidate that has a record, failed ones included, and
  `Run.execute()` never retries. Every INFRA line therefore needs a person to delete it and
  relaunch the run.
- **What the defaults on `main` give `low`** (`pipeline/model.py`):

  | Setting | Value |
  |---|---|
  | Attempt timeout (`MEASURED_CALL_SECONDS_BY_EFFORT[LOW]`) | 120 s |
  | Retries inside inspect (`INSPECT_HTTP_RETRIES`) | 1 |
  | Total HTTP budget (`TimeoutLadder.derive`) | 240 s |
  | Bridge wait (`complete_sync`) | 300 s |
  | Token cap (`MAX_TOKENS_BY_EFFORT[LOW]`) | 12,000 |
  | Pool size (`MODEL_POOL_CONNECTIONS`) | 16 |
  | Workers (`WORKERS`) | **8** |

  The report says the continuation ran on a "600-second attempt / 1,200-second SDK HTTP /
  1,260-second bridge ladder". That is exactly `TimeoutLadder.derive` with a 600 s call. On `main`
  it can only be injected from outside the code. On this branch it is the `call_seconds` parameter
  (commit `56c7af2`, 10-26), which `main` does not have.
- Omar's runtime patches (transport fixes, the STDIO garbage-collection template) are in no
  branch. Searching every remote branch for "kimi" finds only the publication commit `6136d84`.

## 2. Stage timings: what exists

| Quantity | Value | Status |
|---|---|---|
| Per-call latency, per-stage span, session count | — | **Not recorded.** The published records drop `calls`, and `calls` never carried timing anyway. Rows are re-sorted into dataset order (all 2,776 rows sit at their dataset position), so even completion order is lost. No `console.log`, Kimi run directory or inspect trace exists on this machine |
| End to end, both stages plus publication | **≤ 143.5 h** (10-18 15:35 +03 → 10-24 15:04 +03) | Inferred upper bound: source-revision commit time to publication commit time |
| Slowest call disclosed | 853 s, cut off at the token cap (`apps_1413_attack_0`) | Measured, one call (report text) |
| Trigger calls cut off at the cap or by bracket repair | **300 / 2,776 (10.8%)**: 260 non-failed with `dropped=null`, plus 40 failures | Measured |
| … of those 40 failures, the answer length | median **0 chars**, max 28,676 | Measured. The whole cap went on reasoning |
| TrustedSolve "no fenced code block" | 51 / 2,776. DeepSeek `solve-all` had 0 | Measured count. That these are cap cut-offs is inferred: the solve record keeps no stop reason |
| Historical INFRA failures, retries, possible charges | — | Exist only in Omar's local lineage ("remain in the locally preserved lineage") |
| Stored output per call (reasoning plus answer) | Solve **~5.8k chars**, trigger **~9.4k chars** | Inferred from `provenance.json` source bytes, after subtracting prompts that are byte-identical to DeepSeek's (templates unchanged since August) and the solution/input sizes |

### Comparator: the same two protocols, pool and code on DeepSeek

| Run | Period | Calls | Span | Worker-s / call | Output chars / call |
|---|---|---|---|---|---|
| `trig-all` | 10-05, before the outage | 2,776 | 90.7 min | 15.7 | 4,940 |
| `solve-u400` (alongside `trig-u400`) | 09-14, before the outage | 800 | 15.7 min | 9.4 | 2,818 (`solve-all`) |
| `solve-all-r2-smoke` | 10-20, after the outage | 60 | 7.3 min | 58 | 24,109 |
| `trig-all-r2-smoke` | 10-20, after the outage | 60 | 14.6 min | 117 | 45,422 |
| **Kimi solve / trig** | 10-18 → 10-24 | 2,776 + 2,776 | — | **not recorded** | ~5.8k / ~9.4k (inferred) |

**Reading.** Kimi writes 5× less per call than post-outage DeepSeek, yet its calls needed a
5× longer timeout. The cost per Kimi call is therefore latency, not volume. One data point puts it
at 12,000 tokens in 853 s, about **14 tokens/s**. Post-outage DeepSeek writes about 400–560
chars/s, roughly 115–160 tokens/s. That is a single call, so treat it as an indication, not a rate.

### Projected compute per stage at 8 workers (2,776 × L ÷ 8)

| Mean worker-s per call L | 60 | 120 | 200 | 300 |
|---|---|---|---|---|
| Hours per stage, 8 workers | 5.8 | 11.6 | 19.3 | 28.9 |
| Hours per stage, 24 workers | 1.9 | 3.9 | 6.4 | 9.6 |

L for Kimi is unmeasured. That the 120 s attempt had to be raised to 600 s says a material share of
calls ran past 120 s.

## 3. Where the time goes

| Cause | Kimi stages | MT chain, for contrast (`multi_turn_runtime.md`) |
|---|---|---|
| Waiting for a person | **Yes, by a different route.** INFRA records are never retried, so each continuation was a hand relaunch. The relaunches include the single-case retries of 983 and 4122 and the 1413 recovery; the runtime name `kimi-983-resume-runtime` comes from one of them. Hours: **not measured** | 90.7 h at `_stop_on_infra_failures` (80%) |
| Model calls aborted at the timeout, then re-run | **Kimi-specific.** Every call over 120 s cost ≤ 240 s of a worker, possibly two paid generations, and a later re-run. Count: **not in the repo** | 21 API failures, ≤ 3.9% of A |
| Model latency × 8 in flight | Same limit (`WORKERS = 8`; the pool of 16 does not bind). Per-call latency is high (above) | 96–127 worker-s per call |
| Token-cap tail | ≥ 300 trigger calls (10.8%) ran to 12k. Capped calls are the slowest (853 s) and give partial (260) or no (40) input sets | 4–25 calls hit 32k |
| Duplicated Stage 1 calls | **Kimi pipeline only.** 1,388 of the 2,776 solve calls are a second draw on a byte-identical prompt. The second draw rescued **13** tasks (1,369 measured, so 0.95%). The two draws disagree on `solves` for 57 of the 1,346 tasks where both are valid | n/a |
| Serial dependency between stages | **None in code.** Stage 1 and 2 are independent. Whether they ran serially is not recorded | 12.4 h of A and replay before B ‖ C |
| Docker (Stage 1 only) | 2,715 grids, 167 crashed pairs. That is ≤ 1,002 s of 6 s timeouts plus about 2.2 s per grid (DeepSeek replay figure): **≈ 1.9 worker-h ≈ 15 min wall at 8**, inferred | < 1% |

## 4. Changes, ranked by expected saving

| # | File : function | Change | Expected saving | Risk | Changes results? |
|---|---|---|---|---|---|
| 1 | `pipeline/protocols/base.py` : `Run.pending` / `Run.execute` | In the same session, re-queue candidates whose record is `failed and blame == "infra"` once. Append the retry beside the original failure, never in place of it. After that, accept what remains as an INFRA exclusion. This is the retry-once-then-accept policy approved by hand on 10-19 | Removes every hand relaunch. **Not measurable for Kimi.** The bound is the gap between ≤ 143.5 h end to end and the 12–58 h of compute in the table above. On MT5 the same human loop was 80% of wall time | `load_records`/`pending` must keep the first failure visible, with one verdict per candidate. Needs the user's approval, because it moves a decision from a person to code | **No.** Same policy, same records. Persisting failures still leave the denominators |
| 2 | `pipeline/protocols/base.py` : `WORKERS` (line 49), `pipeline/model.py` : `MODEL_POOL_CONNECTIONS`, `solve.py` : `TrustedSolve._graded` | Raise `WORKERS` from 8 to 24. Keep the pool ≥ `WORKERS`. Put a semaphore of about 8 around `sandbox.run_raw`, so Docker load stays where it is | **Compute ÷ ~3**: 11.6 → 3.9 h per stage at L = 120 s. This holds only if the Kimi endpoint scales. DeepSeek showed +8% latency at 2× in flight; Kimi has not been tested | Kimi quota and rate limits unknown. More timeouts under load become INFRA lines, which #1 then absorbs | **No.** `WORKERS` is not written to `config.json` |
| 3 | `pipeline/model.py` : `ModelSpec.resolved_timeout` / `TimeoutLadder.derive` (bring `call_seconds` from `56c7af2` to `main`) | Start Kimi runs at `call_seconds=600`, in place of the 120 s DeepSeek budget | Ends calls aborted at 240 s only to be re-run. Each such call saves ≤ 240 s of worker time plus its share of a relaunch. Per stage that is **f × 23 h wall at 8 workers**, where f is the unmeasured share of calls over 120 s | A hung call now holds a worker for up to 1,260 s. Recorded in `config.json`, so the run gets a new name and does not resume the published one | **No** to prompts, caps or sampling. Calls that used to time out now return |

**Free, no code change:** launch Stage 1 and Stage 2 at the same time, since neither reads the
other. If they ran serially, this takes the whole of Stage 1 off the critical path.

**Considered and not recommended:**

| Change | Saving | Why not |
|---|---|---|
| One TrustedSolve call per task, copied to both candidates (`solve.py` : `TrustedSolve.score`) | −1,388 calls, −50% of Stage 1 | **Changes results.** 13 tasks lose their only measurement, and the 57-task disagreement signal disappears. `solve.py`'s docstring calls the two draws deliberate |
| Lower `max_tokens` at `low` | Cuts the slowest tail | **Changes results.** More truncated or empty input sets (already 300 cut off) |
| Raise `max_tokens` | Recovers 40 failed and 260 truncated sets | **Changes results** and makes calls slower |
| Re-grade a stored solution after a sandbox INFRA failure, without a new model call (`TrustedSolve.score`) | One Kimi call per sandbox INFRA line (count unknown) | Small, and it changes which draw is kept |
| Sandbox tuning | ≤ ~15 min wall | Nothing to win |

## Sources

- `git show origin/main:` `reports/kimi-stage12-20261024/{README.md,provenance.json}` and both
  run directories' `config.json` and `records.jsonl`, at commit `6136d84`.
- `pipeline/` at `411bf4e`, identical on `origin/main`: `protocols/base.py`, `protocols/solve.py`,
  `protocols/trigger_search.py`, `model.py`, `sandbox.py`.
- DeepSeek comparators: local `runs/{trig-all,solve-all,solve-u400,trig-u400,*-r2-smoke}`. Spans
  come from the `console.log` APFS birth and modification times, each a single session, checked
  against the console header.
- Output sizes for Kimi: source bytes from `provenance.json`, minus the DeepSeek prompt bytes
  (prompts are identical because `prompts/trusted_solve.txt` and `audit_inputs*.txt` are unchanged
  since 08-23), minus the solution bytes (Kimi `solution_chars` × 2 copies) and the input bytes
  (DeepSeek bytes per input × Kimi `n_parsed`), divided by the 1.05 JSON-escape factor measured on
  DeepSeek. This assumes Kimi's reasoning was stored in `calls[].reasoning`, which cannot be
  checked from the projection.
