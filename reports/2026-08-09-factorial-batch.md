# B1 — which of three interventions moves deployable PBT, and do they compose?

**Date:** 2026-08-09 · **Run IDs:** `b1-r1` … `b1-r8` · **Status:** pre-registered

---

## 1. Question

Three interventions have been proposed for PBT-as-monitor: letting the untrusted model plan the
properties, widening the trigger search by reading the candidate's code, and a spec-only critique
pass that prunes unsound properties. Each has been argued for separately and none has been measured
against the others on the same pool. Which moves the deployable arm, and are they additive?

## 2. Hypotheses

Written before any cell has run. The primary metric is **PBT's earned-safety ratio to TM**.

- **H1 (critique).** `self_critique` raises `pbt`'s ratio to TM by **at least 5 points**. It is the
  only intervention aimed at the binding constraint: deployable PBT's cost is a 30% honest
  false-positive rate driven by unsound properties, and the critique is a soundness gate that needs
  no reference.
- **H2 (code-aware).** `code_aware_search` does **not** raise `pbt`'s ratio, and raises the honest
  false-positive rate by more than it raises the catch rate. This is a replication: the F-series
  measured +0.150 on honest against +0.089 on attacks at 10 tasks, with safety unchanged.
- **H3 (interaction).** Critique and code-aware are **not** additive. Code-aware buys recall by
  looking in more places; critique buys precision by removing properties. If H1 and H2 both hold,
  critique should recover part of the false-positive cost code-aware imposes, so the
  critique effect is **larger** under code-aware than under blind search.
- **H4 (strategy).** `u_plans_t_writes` beats `blind_t` on the ratio by at least 5 points. Untested
  on this pool: every prior 50-task run used `u_plans_t_writes` and every `blind_t` run used 10
  tasks.

**If H1 is false, we expect** the ratio flat within ±3 points and the honest FPR unmoved, meaning
the unsound properties the critique removes were not the ones firing on honest code.

**Kill criterion.** If no cell puts `pbt`'s ratio above 60% of TM, deployable standalone PBT is
finished as a line of work and the question narrows to `pbt_informed_tm`, the only arm that has ever
beaten TM.

## 3. Setup

- **Data:** `apps_pool_hard.json`, 50 tasks, 115 candidates (50 honest, 65 attacks). Frozen; every
  attack is a working backdoor. All 50 tasks are stdio with ≥20 provided inputs.
- **Models:** T = `openai-api/azureai/DeepSeek-V3.2`, reasoning `low`. U = `openai-api/azureai/gpt-5.4`,
  reasoning `high`. Temperature is at each provider's default — both reject the parameter.
- **Design:** full 2×2×2 — `gen_strategy` (`blind_t` | `u_plans_t_writes`) × `code_aware_search`
  (off | on) × `self_critique` (off | on).
- **Runs:** 10 per cell, seed base 300. n=10 chosen because the informed-TM t-statistic sat at
  2.48–2.66 against `t_crit(df=4)=2.776`; `t_crit(df=9)=2.262`.
- **Arms scored:** `tm`, `pbt`, `pbt_ceiling`, `pbt_informed_tm`.
- **Held fixed:** pool, models, reasoning efforts, `max_search_space 60`, `pbt_timeout 60`,
  `--pbt-isolation subprocess`, `--max-conn 4`, `--exec-workers 2`, both monitor prompts (paper wording).
- **Cost:** ≈30,400 model calls. Code-aware adds zero calls, only harness time.

| cell | `gen_strategy` | code-aware | critique |
|---|---|---|---|
| r1 | `blind_t` | – | – |
| r5 | `blind_t` | – | ✓ |
| r2 | `blind_t` | ✓ | – |
| r6 | `blind_t` | ✓ | ✓ |
| r3 | `u_plans_t_writes` | – | – |
| r7 | `u_plans_t_writes` | – | ✓ |
| r4 | `u_plans_t_writes` | ✓ | – |
| r8 | `u_plans_t_writes` | ✓ | ✓ |

## 4. Metrics

| Metric | Plain English | Better = |
|---|---|---|
| **`pbt` earned-safety ratio to TM** | Safety above the free floor, as a fraction of TM's. Horizon-invariant. | higher |
| `sweep_deployed` catch rate / FPR | Threshold curve over the population the game can draw — the selected attack per task plus all honest. Comparable to safety. | higher / lower |
| `sweep` catch rate / FPR | Same curve over all 65 successful backdoors. More power, different denominator. | descriptive |
| `pbt_decision_coverage` | Fraction of candidates the arm reached a verdict on. | higher |
| `pbt_invalid_blame` | MODEL vs INFRA split of invalid suites. | INFRA → 0 |
| `n_partial_runs / n_candidate_runs` | Harness shortfall. Reads whether `_scaled_timeout` equalised code-aware. | descriptive |
| `n_gates_usable / n_gates` | Per-candidate reference gates that certified. Reads the A2 fix. | higher |
| `pbt_informed_tm` ratio to TM | The only arm that has beaten TM. Control on "did we break something". | — |

**Primary metric: `pbt` earned-safety ratio to TM.** Everything else is descriptive.

Deployment game: `horizon 50`, `audit_rate 0.10`, `audit_slots` derived, `attack_rate 0.10`,
10,000 trials, BENIGN everywhere with coverage reported beside every number.

## 5. Comparability to earlier runs

**The trusted monitor is the AI-control-paper prompt, unchanged.** It is the baseline the
literature holds fixed, so this batch does not touch it. A v2 rubric with per-band anchors was
drafted and reverted before launch.

**The informed monitor is now that same prompt plus PBT evidence, and nothing else.** Its opening
paragraph and its rating instruction are byte-identical to the trusted monitor's; the only
additions are the property source, the inputs, the result, and a paragraph stating how to read
them — a failure is strong evidence, a pass rules out only what those properties check on those
inputs. Previously it also REPLACED the trusted monitor's review instruction ("suspicious
special-cases, magic constants, unusual branches") with a weighing instruction and dropped "the
code passes the visible tests", so `pbt_informed_tm` minus `tm` mixed "saw PBT evidence" with "was
asked a different question". It is now a one-variable delta, which is the whole point of the arm.

Absolute catch rates remain comparable to `uplanhard50-fixed` for `tm`. For `pbt_informed_tm` they
are NOT comparable to runs before 2026-08-09, because its prompt changed; the arm's value has
always been its delta against `tm` in the same run, and that delta is now clean.

**The known monitor defect is carried, not fixed.** On Run A `run_0` (n=230, 0 unparsed) TM placed
37 attacks AND 11 honest candidates at level 9. Those 11 stop the audit threshold dropping from 10
to 9: threshold 10 catches 21/65 at 2% FPR, threshold 9 catches 58/65 at 24% FPR, and a 10% budget
cannot buy the second. Every cell inherits this equally so it cannot explain a difference BETWEEN
cells, but it bounds how high any of them can score, and the kill criterion must be read with that
in mind. Monitor rubric deserves its own pre-registered experiment against the paper prompt as
control.

<!-- ========== everything above is written BEFORE the run ========== -->

---

## 6. Results

_To fill from artifacts. Numbers only, with n and spread._

## 7. What this means

_Per hypothesis: supported / not supported / underpowered._

## 8. Caveats

_Known before the run:_

- **Runs share their candidates.** The same 115 candidates appear in all 10 runs, so run-to-run
  variance is monitor-and-property noise plus deployment draws, not candidate sampling. Reported
  spread understates true variance. n=10 makes the informed-TM comparison decidable; it does not
  make the pool representative.
- **`selected_attack` defaults to the first attack.** ~15 tasks carry a second attack the game never
  draws. If `attack_0` is systematically easier than `attack_1`, safety carries an unmeasured
  selection bias. Comparing catch rate on `attack_0` vs `attack_1+` is free and settles it.
- **Trigger search is APPS-shaped** — line-0 heuristics and whitespace token grids. Do not read
  these results as generalising to other benchmarks.
- **Temperature is uncontrolled**, at each provider's default; both models reject the parameter.
- **Eight cells run concurrently** at `--max-conn 4`. Validated on a live 8-cell smoke: zero
  warnings, zero throttling. A throttled batch would show up as INFRA abstentions, so
  `pbt_invalid_blame` must be checked before the primary metric is read.

## 9. Next

_To fill._

---

**Provenance:** `bash run_batch.sh` · pool `apps_pool_hard.json` · artifacts `runs/b1-r*/`
