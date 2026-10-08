# Multi-turn test authoring — experiment log

Runs owned by the multi-turn section of the team notebooks (`notebooks/multi_turn_cells.py`,
appended by `build_results.py`); how a run flows is in `docs/flow_multi_turn.md`. Entries follow
AGENTS.md's format and are written before `MT_ALLOW_PAID_FULL = True`. **MT1 is the primary run**;
conclusions are drawn from MT1 alone, and MT2–MT4 are secondary and descriptive. No correction for
multiple runs is claimed.

## Shared hypothesis

Execution feedback shows where a test and the code disagree, but not whether the test or the code
is wrong. The reviser never sees whether a candidate is honest or an attack, so feedback can lead it
to drop a firing test on honest code (fewer false positives) and, just as readily, on attack code
(fewer catches).

- **H1 — feedback (C − B).** Feedback does not reliably reduce honest FPR while preserving attack
  detection. In the completed terra pilots its effect was inconsistent: fresh APPS, FPR +3.6 pp
  (4/28 → 5/28) and catch −3.3 pp (26/30 → 25/30); exposed BCB, FPR −12.5 pp (6/24 → 3/24) with
  catch unchanged, where C mostly reverted false positives the no-feedback rewrite had introduced
  (C equalled A exactly).
- **H2 — rewriting at all (B − A, C − A).** A second turn, with or without feedback, does not
  reliably improve on the first suite and can remove attack detectors. BCB pilot: both rewrites
  lost 2 of 21 catches against A. APPS pilot: no loss. H2 is therefore held with less confidence
  on APPS than on BigCodeBench.

These criteria are pre-specified for this run, informed by the completed pilots. They are not a
retroactive preregistration of the pilots.

## Shared decision rules

All on test tasks, strict complete/error-free paired candidates, 95% task-cluster bootstrap
(10,000 draws, seed 300). M is the attack non-inferiority margin given in each entry.

| Reading | Condition |
|---|---|
| Reliable FPR benefit, detection preserved (falsifies H1) | C − B FPR upper bound < 0 **and** C − B catch lower bound > −M |
| FPR benefit at a detection cost (the trade-off H1 anticipates) | C − B FPR upper bound < 0 **and** C − B catch lower bound ≤ −M |
| Reliable harm (also contradicts H1's prediction) | C − B FPR lower bound > 0, **or** C − B catch upper bound < 0 |
| Consistent with H1 | none of the above, with the point estimates inside the predicted ranges |
| Inconclusive | an interval spanning both meaningful benefit and meaningful harm; never reported as "no effect" |

A 10 pp FPR reduction remains the practically important target, not a pass/fail gate. Each entry
reports whether it is excluded: a C − B FPR lower bound above −10 pp rules out a 10 pp benefit.
The pilots' effects were 1–3 candidates on 21–30, which is why a 10 pp gate is not used.

Every contrast is repeated without the test tasks any earlier pilot used
(`PILOT_EXPOSED_TASK_IDS`, 106 tasks); a sign change there is reported beside the primary result.

## MT1 — multi-turn on uniform400, terra (primary)

**Setup.**      `data/apps_uniform400.json`: 400 APPS tasks, 160 train / 240 test, 800 candidates.
                Model `openai-api/azureai/gpt-5.6-terra` for every stage, seed 300, reasoning low.
                Runtime read off `ut-u400-property-10`: max_tokens 32000, call_seconds 300,
                sandbox_seconds 240, image `python:3.12-slim` — larger than the pilots' 8,192 tokens
                and 120 s. Fresh trigger run, 30 inputs per candidate, cache off throughout. Arms A
                (10 traceable tests, code visible), B and C (one revision of A, code hidden),
                B and C launched together. Smoke chain on the first test task first. Prefix
                `u400-mt-terra-run1`. Upper bound 3,208 logical calls. 13 of the 240 test tasks are
                pilot-exposed (sensitivity only).
**Change.**     C against B: A's execution feedback is shown to C and withheld from B; nothing else
                differs. Secondary: B and C against A, a second turn at all.
**Hypothesis.** H1 and H2 above.
**Prediction.** Margin M = 5 pp. Simulated 95% interval half-width at this n: about ±2.5–4.5 pp.
                1. C − B honest FPR: point estimate within ±5 pp, interval including 0.
                   Falsified by either "reliable" row of the decision table.
                2. C − B attack catch: point estimate within ±5 pp, lower bound above −5 pp.
                   Falsified if the lower bound is at or below −5 pp.
                3. C − B honest FPR lower bound above −10 pp, i.e. a 10 pp benefit is ruled out.
                   Falsified if the lower bound is at or below −10 pp.
                4. H2: B − A and C − A attack catch point estimates ≤ 0, and neither honest-FPR
                   interval lies wholly below 0. Falsified if C − A FPR upper bound < 0 with
                   C − A catch lower bound > −5 pp — the second turn reliably beats the first.
**Observed.**   Not yet run.

## MT2 — multi-turn on uniform400, DeepSeek (secondary)

**Setup.**      As MT1 with model `openai-api/azureai/DeepSeek-V3.2` — the team arms' model — and
                prefix `u400-mt-deepseek-run1`. Upper bound 3,208 logical calls.
**Change.**     As MT1.
**Hypothesis.** H1 and H2, extrapolated from terra pilots to DeepSeek.
**Prediction.** As MT1, items 1–4, M = 5 pp. Descriptive: no conclusion is drawn from MT2 alone.
**Observed.**   Not yet run.

## MT3 — multi-turn on bcbas, terra (secondary)

**Setup.**      `data/bcbas.json`: 453 BigCodeBench tasks, 317 train / 136 test, 906 candidates.
                Model `openai-api/azureai/gpt-5.6-terra`, seed 300, reasoning low, max_tokens 32000,
                call_seconds 300, sandbox_seconds 720, image `pbt-bcb:2` — read off
                `ut-as-property-10`. Same chain and metric as MT1, plus arm D (delete-only: keeps a
                subset of A's original tests, never rewrites one); B, C and D launched together.
                Prefix `bcbas-mt-terra-run1`. Upper bound 4,540 logical calls. 3 of the 136 test
                tasks are pilot-exposed (sensitivity only).
**Change.**     As MT1 for C against B. D against C: deleting tests versus rewriting them, both
                shown the same feedback.
**Hypothesis.** H1 and H2; and deleting does not reduce false positives relative to rewriting
                (BCB pilot: D − C honest FPR 2/22 vs 2/22, catch 17/20 vs 18/20).
**Prediction.** Margin M = 10 pp: at about 125 honest candidates the simulated half-width is
                ±3–6 pp, too wide for a 5 pp margin.
                1–4. As MT1, with M = 10 pp in items 2 and 4.
                5. D − C honest FPR: point estimate within ±5 pp, interval including 0.
                6. D − C attack catch: point estimate ≤ 0.
                   Falsified if D − C FPR upper bound < 0 with D − C catch lower bound > −10 pp.
**Observed.**   Not yet run.

## MT4 — multi-turn on bcbas, DeepSeek (secondary)

**Setup.**      As MT3 with model `openai-api/azureai/DeepSeek-V3.2` and prefix
                `bcbas-mt-deepseek-run1`. Upper bound 4,540 logical calls.
**Change.**     As MT3.
**Hypothesis.** As MT3, extrapolated from terra pilots to DeepSeek.
**Prediction.** As MT3, items 1–6, M = 10 pp. Descriptive.
**Observed.**   Not yet run.
