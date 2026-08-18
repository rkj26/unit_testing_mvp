# Experiment index

One row per experiment, newest first. Each links to a full report in `reports/`, written from
`reports/TEMPLATE.md`.

| Date | Question | Primary metric | Verdict | Report |
|---|---|---|---|---|
| 2026-08-18 | Does bounded re-solving — compute the answer, but only inside a declared size guard — fix the oracle? | held-out catch, earned catch, and both at a matched false-alarm rate | **supported** — catch 50%→**77%**, false alarms 41%→**33%**, earned catch 33%→**47%**; ≥4 tests gives 4 catches at **0% honest cost**, an operating point TM's coarse score cannot represent. Still behind TM on earned catch (47% vs 80%) | [Audit probe, run 5](2026-08-17-audit-probe.md) |
| 2026-08-17 | Free-form tests written from the code, TM vs PBT on a 20/30 split — and then, why does PBT miss? | held-out catch at a matched false-alarm rate | **not supported for `pbt`** — TM 80% vs PBT 33% at ~40% FPR, 30% vs 7% at 3%. Run 4 (zero calls) corrects run 3: **earned** catch is 10/30, not 15/30, and the graded-count precision dial does not survive. TM's reasoning names the trigger in 10/10 unreached attacks | [Audit probe](2026-08-17-audit-probe.md) |
| 2026-08-14 | Does the trusted model reading the submission before writing its properties and triggers recover monitoring value? | `pbt` `ratio_to_baseline` (H1: ≥0.45) | _pre-registered_ — smoke + mini ran; the 50-task rung `ca-hard50` died mid-run 4 with no `metrics.json`, and both prompts were rewritten afterwards | [Code-aware authoring](2026-08-14-code-aware-authoring.md) |
| 2026-08-14 | Does calibrating the audit threshold on 20 tasks and reporting on the other 30 change what we concluded? | `pbt/tm` earned-safety ratio, mean over 5 splits | **complete** — TM loses 0.054–0.080 in every cell, PBT moves ±0.06 with no sign; B1's kill criterion still fires (0.519 mean, 0.577 best split, threshold 0.60) | [Train/test threshold](2026-08-14-train-test-threshold.md) |
| 2026-08-10 | Does PBT add monitoring value over code review? (2x2 ablation) | `pbt` earned-safety ratio to TM | **not supported** (best 44.1%, kill criterion fires) | [B1 report](2026-08-10-B1-factorial-report.md) |
| 2026-08-09 | Which of three interventions moves deployable PBT, and do they compose? | `pbt` earned-safety ratio to TM | **complete** (4/8 cells reported; `b1-r6` and `b1-r8` never finished generating) | [B1 — 2x2x2 factorial](2026-08-09-factorial-batch.md) |
| 2026-08-08 | How much of PBT's measured weakness is measurement failure? | PBT earned-safety ratio to TM (baseline 47.3% graded) | **run complete, report not** — `uplanhard50-fixed` finished 5/5 on 2026-08-09; sections 5–8 of the report are still empty | [Run A — instrumentation repair](2026-08-08-instrumentation-repair.md) |

Verdicts: **supported** · **not supported** · **underpowered** · _pre-registered_ (not yet run)

---

## Earlier reports (pre-index)

Written before this index and before `TEMPLATE.md`, so they do not carry the four pre-registration
fields uniformly. Listed here because an unlisted report is a report that gets re-derived from
scratch; their numbers have **not** been re-verified against artifacts in this pass, and every one
of them is a **10-task** pool unless the row says otherwise.

| Date | Question | Primary metric | Verdict | Report |
|---|---|---|---|---|
| 2026-08-07 | Does the AUC gain of `pbt_informed_tm` fail to reach the audit budget? (post-hoc, no new run) | `delta_t0` at `c = 0.10` | **not supported** — `delta_t0` is *larger* than `delta_AUC`, and safety is a fixed 0.26–0.49 contraction of it. Confirms two-level coarseness for `pbt` only, in 15/15 runs | [Effective audit budget](2026-08-07-effective-audit-budget.md) |
| 2026-08-07 | Is every claim in the 50-task report true against code, artifacts and the cited papers? | claim-by-claim audit | **complete** — corrections filed, C1 (the soundness gate does not govern the scored arm) changes a conclusion | [Verification](2026-08-07-verification.md) |
| 2026-08-07 | Does trusted-written PBT add signal a code-reading monitor lacks? **50 tasks, 115 candidates** | safety; AUC | **not supported for `pbt`** (earns 0.07 where TM earns 0.24, 30% FPR, one operating point). `pbt_informed_tm − tm` = **+0.023, n=4, spans zero** | [Results](2026-08-07-uplanhard50-results.md) · [readable version](2026-08-07-pbt-as-control-monitor.md) |
| 2026-08-07 | P2 — same question at a 12k-token trusted cap and a bare-reference soundness gate | safety, paired vs `tm` | **Observed never filled**; analysed post-hoc in the audit-budget report instead | [uplan10-tlow-uhigh-v2](2026-08-07-uplan10-tlow-uhigh-v2.md) |
| 2026-08-07 | P1 — same question at a 300 s harness budget (first entry of that log) | safety, paired vs `tm` | **Observed never filled**; superseded by P2 and by the 50-task pool | [uplan10-tlow-uhigh-pbt300](2026-08-07-uplan10-tlow-uhigh-pbt300.md) |
| 2026-08-05 | E0–E7 — can a code-aware input generator raise the fraction of backdoors the search space reaches? | reach rate (recall ceiling), budget matched at 60 inputs | **supported** — blind 21%, dictionary 14%, coverage-guided 43%, **union 57%**. E6 (held-out) and E7 (LLM search) never run | [Search experiments](2026-08-05-search-experiments.md) |
| 2026-08-05 | F1–F2 — does the reach gain convert into safety end to end? | Δ safety, usefulness | **F1 underpowered** (+0.074, n=4, spans zero); **F2 net loss by its own pre-registered rule** (honest fire rate +0.150 against attacks +0.089) | [Search experiments, F-series](2026-08-05-search-experiments.md) |
| 2026-08-05 | D0–D3 — does giving PBT a *block* action instead of an audit slot flip its sign? (replay of stored rows, no model calls) | Δ safety at a stated usefulness cost | **supported** — ungated `pbt` +0.092/+0.114 (CI excludes 0) at 27–35% of honest work destroyed; critique-gated **+0.044 for 15% usefulness**, the deployable result. D0's usefulness metric was discarded as an artifact | [Deployment experiments](2026-08-05-deployment-experiments.md) |
| 2026-08-05 | A0–A8 — nine one-at-a-time ablations on the same pool | paired Δ safety vs TM, then reach | **mixed; A6 is the finding** — for 12/14 backdoors the harness never executes the buggy path. A4 (test density) died on held-out data, A7 (batch gate) was tautological, A8 (self-critique) halved FPR | [Ablation log](2026-08-05-ablation-log.md) |
| 2026-08-05 | Does trusted-written PBT add value over TM? (the run every later entry compares against) | safety, paired vs `tm` | **not supported** — `pbt` −0.188, and `tm_plus_pbt_ceiling − tm` = 0.000 ± 0.000 at every attack rate | [uplan10-p05](2026-08-05-uplan10-p05.md) |
