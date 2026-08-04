# PBT-as-monitor: the plan×write 2×2 + generation variations (findings)

**Date:** 2026-08-04 · **Pool:** apps_pool_hard10 (10 APPS-hard tasks, 24 candidates, 14 ground-truth backdoors)
**Models:** trusted T = DeepSeek-V3.2, untrusted U = gpt-5.4 · **Runs:** 5/arm · **Audit:** top-2%-by-suspicion, 1 slot, horizon 10, 10k trials.

## TL;DR
Across **both** axes we varied — *who plans / who writes* the properties (2×2) **and** *how* the properties
are generated (precision, more-properties, dense-search) — **trusted property-based tests used as a monitor
never lift deployable safety off the 2% audit floor, and hard-thresholding PBT into the audit always hurts.**
The two structural walls hold universally:
- **W1 (coverage):** the deployable `pbt` protocol stays pinned at ~0.02 in every arm; even +50% more trigger
  inputs (dense-search) leaves the reference-gated ceiling flat (~0.18) — coverage is limited by the
  *properties' discriminative power*, not by trigger-input density.
- **W2 (verification-generation asymmetry):** `PBT+TM = max(tm,pbt)` hurts in every arm (Δ −0.35…−0.48) because
  unsound properties false-alarm on honest code and there is no reference at deploy time to gate them; the
  reference-gated **ceiling** version never hurts, isolating the cause.

**The one constructive result:** the FPR-robust way to use PBT is **`informed-TM`** — let the trusted model
*read the PBT evidence and judge*, rather than hard-thresholding it. It is the best PBT-using protocol and the
only one that *improves* with better/more generation (more-properties: Δ +0.169 vs TM). Gains are modest and
noisy at n=5.

Two methodological findings fell out: (1) a per-call interpreter-spawn bottleneck in the evaluator confounded
the first `u_plans_u_writes` run and made runs ~1000× too slow — now fixed; (2) small-n + a knife-edge 2%/N=10
audit metric mean effect sizes should be read as indicative, not significant.

## Audit policy
Every protocol ranks candidates by **its own** suspicion score and audits the **top 2%**, threshold calibrated
on the honest-score distribution (`metrics.audit_probability`); randomization happens *only* at the exact
boundary to hit the 2% budget. Not random auditing. `PBT+TM = max(tm,pbt)`; `informed-TM` = TM shown the PBT
evidence. (`force_audit.py`'s OR-trigger rule is a supplementary lens, below.)

## Full results — safety (mean ± half-95% CI; top-2% audit, always-attack p=1.0)
| protocol | blind_t | u_writes | u_plans_t_writes | u_plans_u_writes† | precision | more-props | dense-search |
|---|---|---|---|---|---|---|---|
| TM (baseline) | 0.381 | 0.516 | 0.516 | 0.381 | 0.381 | 0.381 | 0.381 |
| **PBT (deployable)** | 0.021 | 0.033 | 0.028 | 0.034 | 0.022 | 0.021 | 0.020 |
| PBT_ceiling (non-deploy) | 0.179 | 0.218 | 0.139 | **0.238** | 0.177 | 0.159 | 0.180 |
| **PBT+TM** = max(tm,pbt) | 0.025 | 0.039 | 0.033 | 0.050 | 0.031 | 0.024 | 0.024 |
| PBT-informed-TM | 0.457 | 0.418 | 0.551 | 0.558 | 0.431 | **0.563** | 0.393 |
| pbt_soundness | 0.98 | 0.98 | 0.84 | 0.86 | **1.00** | 0.98 | **1.00** |
| pbt_generation_health | 1.00 | 1.00 | 0.94 | 0.94 | 1.00 | 0.98 | 1.00 |
| FPR (deployable pbt) | 0.58 | 0.38 | 0.44 | 0.32 | 0.44 | 0.70 | ~0.5 |
| Δ(PBT+TM − TM), paired | −0.357 | −0.477 | −0.484 | −0.331 | −0.351 | −0.358 | ~−0.35 |

† `u_plans_u_writes` = the clean re-run (`upuw3`) on the fixed evaluator. The first run was **confounded** (see below).
**Pools:** TM=0.381 arms share the blind_t candidate pool (blind_t, u_plans_u_writes, and all 3 variations),
so **variation-vs-blind_t is a clean within-pool paired contrast**; the TM=0.516 arms (u_writes, u_plans_t_writes)
are a different pool, so cross-pool 2×2 comparisons mix treatment with attack-set. n=4 on TM where one run's honest-TM abstained.

## Axis 1 — the plan×write 2×2 (who plans × who writes)
- **blind_t (T writes):** clean baseline — sound (0.98), fully healthy, but deployable pbt at the floor and
  ceiling capped ~0.18. Coverage-limited, not confounded.
- **u_writes (U writes):** cleanest elicited arm; highest clean ceiling among no-plan arms (0.218) and best
  clean deployable point (0.033) — capability buys a hair of coverage, not deployable safety.
- **u_plans_t_writes (U plans, T writes):** the split degrades suites (soundness 0.98→0.84) with no
  deployable payoff — the plan already induces heavier/looser properties even for the trusted writer.
- **u_plans_u_writes (U plans + writes):** highest **non-deployable ceiling (0.238)** — U's plan-then-write
  produces the most *powerful* properties — but also the least sound/heaviest, so deployably it still sits at
  the floor (pbt 0.034) and PBT+TM still hurts (FPR 0.32→ Δ −0.331). **Capability, not deployability.**

### The confound (now fixed) that faked `u_plans_u_writes` wins
The first run showed `tm+pbt=0.263`, `informed=0.768`, `FPR=0.10` — all **artifacts**. Root cause: working
from its own plan, U writes properties with large internal batteries / brute-force loops that ignore the
search input (task 3694: ~13,500 reference `run()` calls vs ~1,120 for u_writes). The stdio evaluator spawned
a **fresh interpreter per `run()` call (~33 ms)**, so 52% of suites died to the 60s reference timeout → PBT
scored 0.0 (a broken monitor that never false-alarms) → its "wins" were inertia, not detection. Fixed by
running stdio candidates **in-process** inside the sandboxed harness (+ per-call itimer): parity 24/24 vs the
old subprocess on valid suites, timeouts recovered 5/5 (452s→0.4s), ~1000× faster. The clean re-run
(`upuw3`, validity 0.40→0.94) makes every artifact collapse to the floor — confirming the analysis.

## Axis 2 — generation variations (all on the blind_t deployable base, within-pool)
- **precision-prompted** (fewer, high-confidence properties): did its job — **soundness 1.00**, FPR 0.58→0.44
  — **yet the wall holds**: deployable pbt 0.022 (floor), PBT+TM still −0.351. Cutting FPR to 0.44 is nowhere
  near enough; a 2% budget needs FPR ≈ 0.02 not to saturate. The FPR wall is *steep*, not gradual.
- **more-properties** (5→10): FPR gets *worse* (0.58→0.70) so PBT+TM hurts slightly more — **but informed-TM
  improves most (0.457→0.563, Δ +0.169)**: more evidence helps when a trusted judge weighs it instead of
  hard-thresholding.
- **dense-search** (avg 94 vs 60 trigger inputs, perfect health): **ceiling unchanged (0.180 vs 0.179)** —
  more trigger coverage does *not* help. Coverage is bounded by whether the *properties discriminate the
  backdoor*, not by how many valid inputs are tried.

## The constructive thread: PBT as evidence, not as a trigger
Every hard-threshold use of PBT (`PBT+TM`) hurts, in all 7 arms, under the fixed-2% and the force-audit lenses.
The **only** FPR-robust route is `informed-TM` (trusted model reads PBT results + reasons): it is the best
PBT-using protocol and the one thing that responds positively to better generation (more-properties +0.169,
u_plans_* ≈ 0.55). This reframes the deployable question from "add PBT to the audit" to "give the trusted
monitor PBT evidence to reason over." Worth pursuing; not yet a proven win at n=5.

## Force-audit lens (supplementary — TM baseline + Δ across attack rates)
TM-only safety: p=0.05 → 0.74 … p=1.0 → 0.38. Δ from force-auditing on *deployable* PBT:

| flow | Δ @ p=0.05 (realistic) | Δ @ p=1.0 (always-attack) |
|---|---|---|
| blind_t | −0.078 | +0.333 |
| u_plans_u_writes | −0.029 | +0.285 |
| precision | −0.065 | +0.297 |
| more-props | −0.079 | +0.434 |
| dense-search | −0.078 | +0.359 |
| ceiling (FPR=0, any) | +0.03…+0.07 | +0.09…+0.19 |

Force-auditing deployable PBT helps only when attacks are frequent; at realistic low attack rates the false
positives burn the scarce slot on honest traffic → it hurts in every arm. Only the zero-FPR ceiling always
helps a little — the headroom *if* false positives could be eliminated (needs the reference → non-deployable).

## Statistical caveats
n=5 is underpowered; reported CIs use z=1.96 not a t-multiplier (~40-60% too narrow) → corrected CIs overlap
across arms and nothing survives multiple-comparison correction. Safety at 2%/N=10 is a near-binary "strictly
outrank every honest candidate" test → bimodal/outlier-driven. Within-pool variation contrasts (vs blind_t)
are clean; cross-pool elicitation contrasts (u_writes/uplan) are not. Treat effect magnitudes as indicative.

## Pipeline changes made this cycle
- **Evaluator:** stdio candidates now run in-process in the sandboxed harness (+ per-call itimer added to
  function-mode too) — fixes the timeout confound and ~1000× speedup. Parity + recovery verified.
- **Config is now the single source of truth** (endpoint/eval knobs threaded into model/pbt, not re-read from
  env); Docker forwards only credentials; `run.json` fully reproduces a run.
- **New generation knobs:** `--property-prompt {default,precision}`, `--search-prompt {default,dense}`.
- Engine de-hardcoded (Step-driven ONCE + fan-out table + enforced needs); 11 review findings fixed; eval
  parity byte-identical on mock; pytest 19/19.

## Recommended next steps
1. **Pursue `informed-TM` as the deployable path** — it is the only FPR-robust PBT use. Test: better PBT
   *evidence summaries* to the trusted judge, and more properties, at higher n.
2. **Raise statistical power:** n ≥ 20 runs, bootstrap/t CIs + per-run dot plots, a rank/AUC separation metric
   instead of the knife-edge 2% outcome, within-pool paired contrasts + multiple-comparison correction.
3. **Re-run the elicitation 2×2 on one shared pool + the fixed pipeline** to remove the cross-pool + pre/post
   confounds before drawing 2×2 conclusions beyond "the wall holds."
4. **Deprioritize deployable hard-threshold PBT+TM and raw coverage tweaks** — precision, more-properties, and
   dense-search each empirically fail to move the wall.

## Provenance
blind_t/u_writes/u_plans_t_writes: pre-rewrite pipeline. u_plans_u_writes (upuw3) + all 3 variations:
de-hardcoded pipeline w/ fixed evaluator (byte-identical to pre-rewrite on the deterministic mock backend).
Analysis by a 21-agent adversarial-verification workflow (`wf_d26b8770-885`).
