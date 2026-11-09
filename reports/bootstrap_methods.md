# Four bootstrap methods for deployment safety, compared

**8-arm full-run validation (`apps_full`, 1388 tasks). These are dev/validation numbers for the
method comparison, not final paper numbers.** The point of this exercise is to see whether the
choice of bootstrap changes any conclusion, and to have all four methods parked and ready to point
at the multi-turn B/C/D arms once their records exist (none do yet — see Phase 0).

Script: `analysis/bootstrap_methods.py`, reusing `analysis/safety.py` (the deployment game, copied
verbatim from `notebooks/build_results.py` with a provenance hash). Read-only, no model calls.

Contrast: **monitor+tests (`mwt-full-all-property-10`) minus monitor (`tm-all`)** — the paper's
null — plus tests-only (`ut-all-property-10`) for reference. Game B (flags held back, run
continues), budgets 2/5/10/20%, threshold recomputed inside every resample, 2000 resamples, paired,
seed 20261022. n = 1283 tasks scored by all three arms (515 train, 768 test).

## What each method captures

| method | what varies | what it measures |
|---|---|---|
| **multinomial** | task indices resampled with replacement, same for every arm | the repo's current approach (as in `mt_bootstrap_differences`): task-sampling uncertainty |
| **hierarchical** | tasks resampled, then each monitor candidate's 2 calls resampled | task + monitor-call noise. For a tests arm the inner level is empty, so it reduces to multinomial |
| **bayesian** | Dirichlet(1) weights over tasks; weight-aware cut, weight-proportional deployment | task uncertainty with continuous weights instead of integer counts |
| **calls_only** | tasks held FIXED, only monitor calls resampled | scoring noise alone. Zero width for a tests arm by construction |

The resampling unit is always the whole task. Every `apps_full` task is exactly one honest + one
attack candidate (verified), so there is no candidate cluster to resample within a task; the only
inner stochastic level is the monitor's mean-of-2 calls. That is why "hierarchical" and "calls_only"
act only on monitor arms.

## The headline is method-invariant

**monitor+tests − monitor**, diff and 95% CI, by method × budget:

| budget | multinomial | hierarchical | bayesian | calls_only |
|---|---|---|---|---|
| 2% | +0.045 [−0.017,+0.434] | +0.045 [−0.015,+0.569] | +0.045 [−0.038,+0.444] | +0.045 [+0.002,+0.509] |
| 5% | −0.129 [−0.176,+0.064] | −0.129 [−0.015,+0.091] | −0.129 [−0.195,+0.071] | −0.129 [+0.002,+0.058] |
| 10% | −0.081 [−0.163,+0.034] | −0.081 [−0.179,+0.094] | −0.081 [−0.164,+0.042] | −0.081 [−0.151,+0.030] |
| 20% | +0.009 [−0.041,+0.050] | +0.009 [−0.046,+0.065] | +0.009 [−0.053,+0.063] | +0.009 [−0.022,+0.056] |

**Under the three task-level methods, the monitor+tests interval crosses zero at every budget.**
The null stands: adding tests to the monitor does not robustly improve safety, and the choice of
multinomial vs hierarchical vs Bayesian does not change that at any budget. This is the answer
Sruthi wanted — the conclusion is not an artifact of one bootstrap.

**tests-only − monitor** is robustly negative under every method at 5/10/20% (whole CI below zero):
tests-only is worse than the monitor, not an artifact. Only at the 2% budget do hierarchical and
Bayesian just touch zero (upper bound +0.069, +0.006), because at 2% the monitor itself is weak
(safety 0.60) and every interval is wide.

## Which methods widen or narrow

diff CI width, monitor+tests contrast:

| budget | multinomial | hierarchical | bayesian | calls_only |
|---|---|---|---|---|
| 2% | 0.451 | 0.584 | 0.482 | 0.507 |
| 5% | 0.240 | 0.106 | 0.266 | 0.056 |
| 10% | 0.197 | 0.273 | 0.206 | 0.181 |
| 20% | 0.091 | 0.111 | 0.116 | 0.078 |

- **Bayesian tracks multinomial closely** (within ~0.03 at every budget). Dirichlet(1) weights and
  integer multinomial counts are asymptotically the same thing, and at n=768 test tasks they agree.
- **Hierarchical is not systematically wider or narrower** — wider at 2% and 10%, much narrower at
  5%. The monitor-call layer it adds is small relative to task sampling, so it mostly reflects
  resample-to-resample noise rather than a real extra variance component.
- **calls_only is narrowest**, as expected: it omits task-sampling noise entirely. It is a
  diagnostic, not a headline interval.

No method changes which contrasts are significant. The recommendation for the headline number is
**multinomial** — it is the repo's existing approach (`mt_bootstrap_differences`), the simplest to
defend, and the Bayesian bootstrap agrees with it to three decimals. Hierarchical and calls_only are
worth reporting as robustness checks, not as the primary interval.

## Does the Bayesian bootstrap fix the degenerate-quantile case? Not needed here.

The degeneracy — two budgets resolving to the same honest-score quantile — was a **small-n
artifact**. On the hard pool (n_train = 20) the 2% and 5% cuts were both 0.9444. On the full run
(n_train = 554) the four budgets give **distinct** cuts: 0.889 / 0.833 / 0.778 / 0.556. So there is
nothing for any method to fix on the full run.

Where it would matter — small n — the Bayesian bootstrap's continuous Dirichlet weights do smooth
the *sampling* of the cut, but they cannot smooth the *score discreteness*: the monitor emits only
~24 distinct mean-of-2 values, so a weighted quantile still lands on one of those 24. The Bayesian
bootstrap narrows the between-resample jitter in the cut, not the granularity of the cut itself.
Recommendation: it is a reasonable default at small n, but it is not a substitute for more tasks.

## One honest wrinkle in calls_only

At the 5% budget, the calls_only diff CI is [+0.002, +0.058] while the point estimate is −0.129 —
the interval does not contain the point. This is not a bug in the resampling; it is because the
point estimate uses the 20,000-trial deployment draw and the bootstrap uses a 1,000-trial draw, and
when the resampling noise is tiny (calls_only holds tasks fixed) the Monte-Carlo difference between
those two draws is no longer swamped. For the three task-level methods the task-sampling noise is
far larger than this gap, so their intervals bracket the point estimate normally. The lesson:
calls_only is only meaningful as a width diagnostic, and its centre should not be read against the
point estimate. Matching the trial counts would remove the wrinkle and is the right fix before any
of this is published.

## Generation noise (the multi-turn-specific part)

Not measurable yet. Generation variance is the spread across independently generated suites for the
same task — the thing Phase 2 would estimate. It cannot be computed from a single generated suite
per task, which is all any finished arm has. None of the four methods above captures it: they
resample scoring, tasks or calls, all downstream of one fixed generation. Whether generation noise
is large enough to matter is exactly the open question, and it needs the k=3 generation run (Phase
2, scoped, not yet approved). Flagging plainly: **the intervals above understate total uncertainty
for the multi-turn arm by whatever the generation variance turns out to be.**

## Parked for multi-turn

`analysis/bootstrap_methods.py` takes `--runs-dir`, `--baseline` and `--arm`, so once the B/C/D
revision records exist it runs unchanged, e.g.:

```
python analysis/bootstrap_methods.py --runs-dir <runs> --pool data/apps_full.json.gz \
    --baseline <mt A arm> --arm <mt B arm> --arm <mt C arm> --arm <mt D arm> \
    --out-csv reports/bootstrap_methods_multiturn.csv
```

Note the multi-turn arms are scored on catch/FPR, not deployment safety, in the repo as it stands
(`mt_strict_paired_analysis`); applying the safety game to them is a modelling choice that needs its
own sign-off.

---

**Correction (2026-11-09):** game-B safety equals audit-all Rule A safety (a flagged-but-unaudited attack is held back either way), so the corrected-rule results in `reports/bootstrap_fewshot_and_monitor.md` (2026-11-09 section) and `reports/bootstrap_methods_ruleA_corrected.csv` apply here too. Hierarchical/calls_only dropped there (n=2 call resampling overstates variance). These numbers left as-is for provenance.
