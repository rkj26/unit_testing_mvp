# Experiment index

One row per experiment, newest first. Each links to a full report in `reports/`, written from `reports/TEMPLATE.md`.

| Date | Question | Primary metric | Verdict | Report |
|---|---|---|---|---|
| 2026-08-10 | Does PBT add monitoring value over code review? (2x2 ablation) | `pbt` earned-safety ratio to TM | **not supported** (best 44.1%, kill criterion fires) | [B1 report](2026-08-10-B1-factorial-report.md) |
| 2026-08-09 | Which of three interventions moves deployable PBT, and do they compose? | `pbt` earned-safety ratio to TM | **complete** (4/8 cells) | [B1 — 2x2x2 factorial](2026-08-09-factorial-batch.md) |
| 2026-08-08 | How much of PBT's measured weakness is measurement failure? | PBT earned-safety ratio to TM (baseline 30.1%) | _pre-registered_ | [Run A — instrumentation repair](2026-08-08-instrumentation-repair.md) |

Verdicts: **supported** · **not supported** · **underpowered** · _pre-registered_ (not yet run)

---

Reports in this directory dated before 2026-08-07 predate this index and have not been re-checked against the template. They are deliberately not listed until reviewed.
