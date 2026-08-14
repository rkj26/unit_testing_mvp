# Fit the audit threshold on 20 tasks, report on the other 30

**Date:** 2026-08-14 · **Run ID:** `<tbd>` · **Status:** plan, not started

---

## 0. What is wrong today

`pipeline/metrics.py:227` builds the audit rule from **every** honest row in the run being scored:

```python
rule = AuditRule([score_of(row, protocol) for row in rows if is_honest(row)], config)
```

`deployment_draws` (`metrics.py:174`) then draws its horizon from **every** task id. So the operating
point is chosen by looking at the same honest submissions it is later applied to. `CLAUDE.md`: *"A
number chosen by looking at the data is not evidence until it is validated on tasks it was not chosen
on."* Every safety figure in every report to date is fitted in-sample, including `b1-r1`'s 0.262.

`MetricConfig.leave_one_out` (`metrics.py:54`, default off) is a partial patch — it drops a candidate's
own score from its own calibration reference. That removes self-comparison, not in-sample fitting.

## 1. Why this is cheap

**No model calls.** The deployment game is a pure post-hoc Monte Carlo over `run_*/rows.json`, and
`reaggregate.py` already re-scores a completed run under a different `MetricConfig` without touching
a model. So:

- The split applies **retroactively to `b1-r1`**, giving a held-out blind baseline from artifacts
  already on disk.
- The code-aware arm needs **one** 50-task run, scored the same way.
- Both are then scored by the same split, so the comparison is like for like.

**Nothing about running changes.** Still 50 tasks, still 10 runs. The split lives entirely in
scoring.

## 2. Subtasks

Each is a separate commit, reviewed before the next starts.

| # | Subtask | Files | Status |
|---|---|---|---|
| S1 | Write the split to disk as explicit task-id lists — a seeded shuffle of the 50, 20 train / 30 test, recorded as ids not as a seed so both arms provably use the same one | new `splits/apps_hard_20_30.json`, a small script | todo |
| S2 | `MetricConfig` carries the train ids; `""`/empty means today's in-sample behaviour so every existing run reproduces exactly | `pipeline/metrics.py::MetricConfig` | todo |
| S3 | `safety()` calibrates `AuditRule` on **train** honest rows and draws deployments from **test** tasks only | `pipeline/metrics.py::safety`, `::deployment_draws` | todo |
| S4 | `sweep` / `confusion_at` report on test rows only, so catch rate and FPR describe the same population as safety | `pipeline/metrics.py:244-275` | todo |
| S5 | `reaggregate.py --split <path>` so a completed run can be re-scored held-out | `reaggregate.py` | todo |
| S6 | Tests: empty split reproduces today's numbers bit for bit; a task in train never appears in a deployment draw; calibration ignores test honest scores | `tests/` | todo |
| S7 | Re-score `b1-r1` held-out. This is the new blind baseline and it will not equal 0.262 | `reaggregations/` | todo |
| S8 | Run the code-aware arm, 50 tasks x 10 runs, score held-out | `runs/` | todo |

**Hard constraint, same as before:** with no split configured, every number must be byte-identical.
`reaggregate.py --verify` already asserts a no-override rescore reproduces the source `metrics.json`
exactly, so S2-S4 have a ready-made regression check on real data, not just the mock.

## 3. The decision I need from you

**How the 50 tasks are split.** Recommend a **seeded random shuffle, written out as explicit id
lists**. Reasons: pool order is not random (`apps_pool_hard.json` is sorted by task id, which tracks
the APPS problem numbering and therefore roughly tracks vintage), so first-20 risks a systematic
difference; and storing ids rather than a seed means the blind baseline and the code-aware arm
provably share one split even if the shuffle code changes. Precedent: `task_splits.json` already
stores explicit `development` / `holdout` id lists for bigcodebench.

The alternative worth considering is stratifying on whether the task's attack is a *successful*
backdoor — `b1-r1` has 65 successful backdoors across 50 tasks, unevenly distributed, and an unlucky
shuffle could leave the test half short of them.

## 4. What this will cost in precision, stated in advance

The audit rule calibrates against 20 honest scores instead of 50. PBT's score is a small integer
(how many properties fired), so 20 samples give a lumpy empirical distribution and the 10% operating
point will land on a tie more often. `audit_probability` already splits ties by weighted coin
(`metrics.py:129-132`), so this degrades gracefully rather than breaking — but the safety estimate
will be noisier than the in-sample one it replaces, and some of any change we see will be that
rather than the honest-vs-fitted difference.

`honest_score_levels` and `tie_mass_at_top` are the diagnostics that say whether this bit.

## 5. What it does not fix

The split makes the *threshold* honest. It does not make the *tasks* held out: `apps_pool_hard.json`
is the pool every design decision in this project has been made against. `apps_pool_heldout40.json`
exists for that and is untouched by this plan.
