# Multi-turn test authoring — experiment log

Runs owned by the multi-turn section of the team notebooks (`notebooks/multi_turn_cells.py`,
appended by `build_results.py`); how a run flows is in `docs/flow_multi_turn.md`. Entries follow
AGENTS.md's format and are written before `MT_ALLOW_PAID_FULL = True`. **MT5 is the primary run**
(amended 2026-10-15, before any multi-turn result existed: MT1 was dropped, see its entry);
conclusions are drawn from MT5 alone, and MT2–MT4 are secondary and descriptive. No correction for
multiple runs is claimed.

**Amendment 2026-10-15, before any full chain ran.** The Terra deployment is gone, so MT1 and MT3
are dropped. Since the 2026-10-10 outage DeepSeek at low reasoning spends its whole 12,000-token cap
before writing trigger inputs (45 of 62 MT2 trigger calls empty), so the DeepSeek chains reuse the
team's pre-outage trigger runs instead of a fresh search: `trig-u400` for MT2, `trig-all` for MT5
(`MultiTurnStudy(triggers=...)`, which refuses a run that is not the search the chain would have
launched: same dataset, model, seed 300, 30 inputs, code visible, reasoning low; only the cache
setting differs). Their failed candidates carry forward as exclusions, as in the team's arms. Arms
A, B and C still run on the post-outage model (scale_plan.md E12), at max_tokens 32,000.

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

Read the FPR and attack-catch intervals as separate dimensions, not as mutually exclusive bins.
An FPR benefit is established when its upper bound is below 0; FPR harm is established when its
lower bound is above 0; otherwise the FPR direction is unresolved. Attack catch is non-inferior
within margin M when its lower bound is above −M: this rules out losses of M or larger, but does
not mean zero loss. A reliable attack-catch loss is established when its upper bound is below 0.
Both catch conclusions can hold at once: for example, a catch interval [−2, −1] pp with M = 5 pp
shows a reliable small loss while still meeting the non-inferiority criterion.

| Combined reading | Condition |
|---|---|
| FPR benefit with attack catch non-inferior within M (joint success criterion; falsifies H1) | C − B FPR upper bound < 0 **and** C − B catch lower bound > −M |
| FPR benefit; attack-catch preservation unresolved | C − B FPR upper bound < 0, C − B catch lower bound ≤ −M, and catch upper bound ≥ 0 |
| FPR benefit with a reliable attack-catch loss | C − B FPR upper bound < 0 **and** C − B catch upper bound < 0 |
| Reliable harm without an established FPR benefit | C − B FPR lower bound > 0, **or** C − B FPR upper bound ≥ 0 and C − B catch upper bound < 0 |
| Consistent with H1's predicted ranges | None of the conditions above, and point estimates lie inside the predicted ranges; descriptive only, not acceptance of a null |
| Inconclusive | An interval spans both meaningful benefit and meaningful harm; this is unresolved evidence, never reported as "no effect" |

These combined readings can overlap intentionally: joint success is defined by FPR benefit plus
attack-catch non-inferiority within M, so it still meets that criterion when a statistically
reliable catch loss is smaller than M. Report both conclusions rather than treating them as
contradictory. Preservation unresolved or an inconclusive interval is not evidence of no effect.
(Wording revised 2026-10-08, before any paid run; this is a wording clarification and does not
change thresholds, margins, or analysis.)

A 10 pp FPR reduction remains the practically important target, not a pass/fail gate. Each entry
reports whether it is excluded: a C − B FPR lower bound above −10 pp rules out a 10 pp benefit.
The pilots' effects were 1–3 candidates on 21–30, which is why a 10 pp gate is not used.

Every contrast is repeated without the test tasks any earlier pilot used
(`PILOT_EXPOSED_TASK_IDS`, 106 tasks); a sign change there is reported beside the primary result.

## MT1 — multi-turn on uniform400, terra (dropped 2026-10-15)

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
                   The FPR prediction is falsified if the point estimate is outside ±5 pp or the
                   interval excludes 0. The joint H1 success criterion is met only if the FPR
                   upper bound is < 0 and the attack-catch lower bound is > −5 pp; this remains
                   true for a reliable catch loss smaller than 5 pp.
                2. C − B attack catch: point estimate within ±5 pp, lower bound above −5 pp.
                   This prediction is not met if the lower bound is at or below −5 pp: catch
                   non-inferiority is then not established. That alone is unresolved, not evidence
                   of a loss; a reliable loss is claimed only if the upper bound is below 0.
                3. C − B honest FPR lower bound above −10 pp, i.e. a 10 pp benefit is ruled out.
                   Falsified if the lower bound is at or below −10 pp.
                4. H2: B − A and C − A attack catch point estimates ≤ 0, and neither honest-FPR
                   interval lies wholly below 0. Falsified if C − A FPR upper bound < 0 with
                   C − A catch lower bound > −5 pp — the second turn reliably beats the first.
**Observed.**   Launched 2026-10-13 21:17, stopped 21:33. All 800 trigger records infra: Azure 404 `DeploymentNotFound` for `gpt-5.6-terra` (the deployment is gone from this resource; no spend). Arm A never started. Dropped 2026-10-15: no Terra deployment. Failed run set aside to `archived/mt-failed-2026-10-13/`.

## MT2 — multi-turn on uniform400, DeepSeek (secondary)

**Setup.**      As MT1 with model `openai-api/azureai/DeepSeek-V3.2` — the team arms' model — and
                prefix `u400-mt-deepseek-run1`. Upper bound 3,208 logical calls.
**Change.**     As MT1.
**Hypothesis.** H1 and H2, extrapolated from terra pilots to DeepSeek.
**Prediction.** As MT1, items 1–4, M = 5 pp. Descriptive: no conclusion is drawn from MT2 alone.
**Observed.**   Launched 2026-10-13 21:17, stopped 21:35. Smoke "passed" (no infra) but 5 of 10 smoke records were model failures; full trigger stage 45 of 62 model failures (`no JSON array found (stop_reason max_tokens, 0 chars)`) — post-outage DeepSeek spends the whole default token budget reasoning (scale_plan.md E12). All seven run folders set aside to `archived/mt-failed-2026-10-13/`. Relaunched 2026-10-15 with `triggers="trig-u400"` (amendment above); prefix unchanged. Smoke chain 8 of 8 ok; full chain running since 10:08 (driver tmux `mt-u400-driver`). Arm A complete 13:17 (775 ok, 16 model, 9 infra: 4 sandbox, 5 carried from `trig-u400`; 1 API timeout retried and recovered). Held before the replay pending the accept-after-retry decision.

## MT3 — multi-turn on bcbas, terra (dropped 2026-10-15)

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
**Observed.**   Not yet run: `data/bcbas.json` and `ut-as-property-10` are not on this machine.

## MT4 — multi-turn on bcbas, DeepSeek (secondary)

**Setup.**      As MT3 with model `openai-api/azureai/DeepSeek-V3.2` and prefix
                `bcbas-mt-deepseek-run1`. Upper bound 4,540 logical calls.
**Change.**     As MT3.
**Hypothesis.** As MT3, extrapolated from terra pilots to DeepSeek.
**Prediction.** As MT3, items 1–6, M = 10 pp. Descriptive.
**Observed.**   Not yet run: `data/bcbas.json` and `ut-as-property-10` are not on this machine.

## MT5 — multi-turn on the full pool, DeepSeek (primary)

**Setup.**      `data/apps_full.json`: 1,388 APPS tasks, 555 train / 833 test, 2,776 candidates (E11's
                population). Model `openai-api/azureai/DeepSeek-V3.2`, seed 300, reasoning low.
                Runtime read off `ut-all-property-10`: max_tokens 32000, call_seconds 300,
                sandbox_seconds 240, image `python:3.12-slim`. Trigger inputs reused from `trig-all`
                (amendment above), so the chain is arm A, the replay, then B and C launched together.
                Smoke chain on the first test task first. Prefix `full-mt-deepseek-run1`. Upper
                bound 8,334 logical calls. 55 of the 833 test tasks are pilot-exposed
                (sensitivity only). Written 2026-10-15, before launch.
**Change.**     As MT1: C against B, A's execution feedback shown to C and withheld from B. Secondary:
                B and C against A.
**Hypothesis.** H1 and H2, extrapolated from the terra pilots to DeepSeek.
**Prediction.** Margin M = 5 pp. Interval half-width at this n about ±1.5–2.5 pp (MT1's simulated
                ±2.5–4.5 pp scaled by √(240/833); not re-simulated).
                1–4. As MT1, items 1–4, M = 5 pp.
**Observed.**   Smoke chain 8 of 8 ok. Full chain running since 2026-10-15 10:11 (driver tmux `mt-full-driver`). Arm A complete 22:30 (2,707 ok, 55 model, 14 infra: 11 sandbox, 3 carried from `trig-all`; 21 API failures retried and all recovered). Held before the replay pending the accept-after-retry decision.
