# Bootstrap methods for deployment-game safety

Read-only analysis tooling for the deployment-game safety numbers. Every script here reads
**finished run directories only** — it makes no model calls and re-runs no experiment.

All five computational scripts load `safety.py` (the deployment game, copied verbatim from the
notebook generator with a provenance hash) as a sibling module via `importlib`, so keep them in the
same directory.

## The four bootstrap methods (`bootstrap_methods.py`)

| method | resampling unit | what it measures |
|---|---|---|
| **multinomial** | tasks, with replacement (same indices for every arm) | task-sampling uncertainty — the repo's default |
| **hierarchical** | tasks, then each monitor candidate's 2 calls | task + monitor-call noise (reduces to multinomial for a tests-only arm) |
| **bayesian** | Dirichlet(1) task weights applied directly | task uncertainty with continuous weights instead of integer counts |
| **monitor-call resampling** (`calls_only`) | monitor calls only, tasks held fixed | scoring noise alone (a width diagnostic, zero width for a tests-only arm) |

`multinomial`, `hierarchical`, `bayesian` are the three **task-level** methods. `calls_only` omits
task-sampling noise and is a diagnostic, not a headline interval.

## Headline result — the null is method-invariant and survives the corrected audit rule

`monitor+tests − monitor` (arm `mwt-full-all-property-10` − baseline `tm-all`), diff and 95% CI, on
`apps_full`. **Under all three task-level methods the interval crosses zero at every audit budget**,
so adding tests to the monitor does not robustly improve safety, and the conclusion does not depend
on the choice of bootstrap or on the audit rule.

**Game B** — `reports/bootstrap_methods.md` / `reports/bootstrap_methods_gameB.csv`
(2000 resamples, seed 20261022, n = 1283 tasks: 515 train / 768 test):

| budget | multinomial | hierarchical | bayesian |
|---|---|---|---|
| 2%  | +0.045 [−0.017, +0.434] | +0.045 [−0.015, +0.569] | +0.045 [−0.038, +0.444] |
| 5%  | −0.129 [−0.176, +0.064] | −0.129 [−0.015, +0.091] | −0.129 [−0.195, +0.071] |
| 10% | −0.081 [−0.163, +0.034] | −0.081 [−0.179, +0.094] | −0.081 [−0.164, +0.042] |
| 20% | +0.009 [−0.041, +0.050] | +0.009 [−0.046, +0.065] | +0.009 [−0.053, +0.063] |

**Corrected audit rule** (Rule A, audit-all, arXiv:2512.02157 E.1) —
`reports/bootstrap_methods_ruleA.md` / `reports/bootstrap_methods_ruleA.csv`
(2000 resamples, seed 20261022, same arms and n):

| budget | multinomial | hierarchical | bayesian |
|---|---|---|---|
| 2%  | +0.052 [−0.007, +0.435] | +0.052 [−0.006, +0.568] | +0.052 [−0.033, +0.447] |
| 5%  | −0.127 [−0.168, +0.060] | −0.127 [−0.008, +0.083] | −0.127 [−0.188, +0.067] |
| 10% | −0.077 [−0.163, +0.032] | −0.077 [−0.174, +0.091] | −0.077 [−0.161, +0.041] |
| 20% | +0.008 [−0.038, +0.047] | +0.008 [−0.041, +0.061] | +0.008 [−0.051, +0.061] |

`tests-only − monitor` (arm `ut-all-property-10`) is robustly negative — whole CI below zero —
under every method at 5/10/20%.

> **Population note.** These are dev/validation numbers on the **3-arm intersection** (1283 tasks)
> used for the method comparison. They are **not** the paper's 8-arm `tab:budgets` numbers, which
> use a different common population (2435 candidates, 642 test tasks) and the per-sample
> defer-to-trusted safety model. The report CSVs above are not committed to this branch (outputs are
> kept out of `main`); regenerate them with the commands below.

## Reproduce

Run from the repo root. Pool must be a JSON with a `split` (train/test); `data/apps_full.json.gz`
has one. `--baseline`/`--arm` are run-directory names under `--runs-dir`.

```bash
# 1. Four methods, Game B (the headline table above)
python analysis/bootstrap_methods.py \
    --runs-dir runs --pool data/apps_full.json.gz \
    --baseline tm-all --arm mwt-full-all-property-10 --arm ut-all-property-10 \
    --methods multinomial,hierarchical,bayesian,calls_only \
    --budgets 0.02,0.05,0.10,0.20 --resamples 2000 --seed 20261022 \
    --out-csv reports/bootstrap_methods_gameB.csv

# 2. Four methods under the corrected audit rule (Rule A, audit-all + E.1 ties)
python analysis/bootstrap_methods.py --audit-rule audit_all --match-trials \
    --runs-dir runs --pool data/apps_full.json.gz \
    --baseline tm-all --arm mwt-full-all-property-10 --arm ut-all-property-10 \
    --methods multinomial,hierarchical,bayesian,calls_only \
    --budgets 0.02,0.05,0.10,0.20 --resamples 2000 --seed 20261022 \
    --out-csv reports/bootstrap_methods_ruleA.csv

# 3. Paired safety CIs swept over audit budgets
python analysis/bootstrap_safety.py \
    --runs-dir runs --pool data/apps_full.json.gz \
    --baseline tm-all --arm mwt-full-all-property-10 \
    --budgets 0.02,0.05,0.10,0.20 --resamples 5000 --seed 20261019 \
    --out-csv reports/bootstrap_safety.csv

# 4. Corrected rule with integer scores + E.1 randomized ties (multinomial + Bayesian)
python analysis/bootstrap_corrected.py \
    --runs-dir runs --pool data/apps_full.json.gz \
    --baseline tm-all --arm mwt-full-all-property-10 \
    --methods multinomial,bayesian --budgets 0.02,0.05,0.10,0.20 \
    --resamples 2000 --trials 5000 --seed 20261022 \
    --out-csv reports/bootstrap_methods_ruleA_corrected.csv

# 5. Paper's per-sample defer-to-trusted safety model, same task bootstrap.
#    Requires a ControlArena regrade jsonl (--grading); this file is NOT shipped in the
#    repo — supply your own absolute path.
python analysis/safety_paper_model.py \
    --runs-dir runs --pool data/apps_full.json.gz \
    --grading /abs/path/to/apps_full.control_arena.jsonl \
    --resamples 10000 --seed 20261022 \
    --out-csv reports/safety_paper_model_8arm_10k.csv

# 6. Audit-budget figure (reads the CSV from step 5)
python analysis/plot_budgets.py \
    --csv reports/safety_paper_model_8arm_10k.csv \
    --out reports/budgets.pdf

# Guard test: the corrected cut audits exactly the budget in expectation
pytest analysis/test_expected_audit.py
```
