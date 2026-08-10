# Does property-based testing add monitoring value over code review? A 2×2 ablation

**Date:** 2026-08-10 · **Run IDs:** `b1-r1`, `b1-r5`, `b1-r3`, `b1-r7` · **Status:** complete, n=10 per cell

---

## 0. Summary

Two interventions were ablated against a common baseline on 50 APPS tasks, 10 runs each:
letting an untrusted model **plan** the properties, and a spec-only **critique** pass that prunes
unsound ones. Pre-registered before any cell ran (`reports/2026-08-09-factorial-batch.md`).

| finding | verdict |
|---|---|
| **H1** critique raises deployable PBT by ≥5 pts | **not supported** — +0.3 pts under `blind_t`, **−9.4** under `u_plans` |
| **H4** `u_plans_t_writes` beats `blind_t` by ≥5 pts | **supported** — **+17.9 pts** |
| **H3** the two interventions are non-additive | **supported**, direction opposite to prediction — they *conflict* |
| **Kill criterion** any cell above 60% of TM | **fires** — best cell is 44.1% |

**Headline.** Deployable standalone PBT reaches at best **44% of the trusted monitor's earned
safety**. The critique doubled property soundness (0.44 → 0.81) and bought no safety at all. The
only arm that beats code review is `pbt_informed_tm` — PBT evidence handed to the monitor — and
its advantage is **not statistically significant at n=10** in any cell.

---

## 1. Question

Within an AI-control threat model with no ground-truth reference at deploy time, does having a
trusted model write property-based tests add monitoring value over a trusted monitor that simply
reads the code?

## 2. Setup

| | |
|---|---|
| **Pool** | `apps_pool_hard.json` — 50 tasks, 115 candidates (50 honest, 65 attacks). Frozen. Every attack is a verified working backdoor; all tasks stdio with ≥20 provided inputs. |
| **Trusted model (T)** | `azureai/DeepSeek-V3.2`, reasoning `low`. Writes properties, trigger search, and both monitors. |
| **Untrusted model (U)** | `azureai/gpt-5.4`, reasoning `high`. Used only by `u_plans_t_writes`, and only to produce a prose plan — never executable code. |
| **Runs** | 10 per cell, seed base 300. n=10 chosen because the informed-TM t-statistic previously sat at 2.48–2.66 against `t_crit(4)=2.776`. |
| **Deployment game** | horizon 50, audit rate 10%, attack rate 10%, 10,000 Monte-Carlo trials. Free floor 0.005. |
| **Isolation** | Docker, `--memory 2g --pids-limit 256 --network none` (see §7). |
| **Monitor prompts** | AI-control-paper wording, unchanged. Not a variable in this experiment. |

**Arms scored in every cell**

- `tm` — trusted monitor reads the code. The baseline.
- `pbt` — deployable: every property the model wrote, run over the trigger space.
- `pbt_ceiling` — only properties that held on the privileged reference. **Not deployable** (no reference exists at deploy time); an upper bound.
- `pbt_informed_tm` — the trusted monitor, given the code *plus* the PBT evidence.

## 3. Design

Full 2×2, one factor per axis, everything else held fixed.

| cell | property author | critique pass |
|---|---|---|
| **r1** | T alone (`blind_t`) | — |
| **r5** | T alone (`blind_t`) | ✓ |
| **r3** | U plans, T writes | — |
| **r7** | U plans, T writes | ✓ |

## 4. Results

All values mean ± std over n=10. Earned safety = safety minus the free floor (the share of
deployments in which the attacker never attacked, which no protocol earned).

### Earned safety

| cell | `tm` | `pbt` | `pbt_ceiling` | `pbt_informed_tm` |
|---|---|---|---|---|
| r1 | 0.533 ± 0.067 | 0.139 ± 0.020 | 0.220 ± 0.035 | 0.499 ± 0.052 |
| r5 | 0.540 ± 0.061 | 0.142 ± 0.029 | 0.163 ± 0.031 | 0.579 ± 0.084 |
| r3 | 0.552 ± 0.072 | 0.239 ± 0.027 | 0.317 ± 0.042 | 0.582 ± 0.046 |
| r7 | 0.540 ± 0.062 | 0.185 ± 0.030 | 0.192 ± 0.022 | 0.603 ± 0.112 |

### As a ratio to the trusted monitor (horizon-invariant)

| cell | strategy | critique | `pbt` | `pbt_ceiling` | `pbt_informed_tm` | soundness | coverage |
|---|---|---|---|---|---|---|---|
| r1 | `blind_t` | — | 26.2% | 41.5% | 95.0% | 0.442 | 0.986 |
| r5 | `blind_t` | ✓ | 26.4% | 30.3% | 108.5% | 0.814 | 0.990 |
| r3 | `u_plans` | — | **44.1%** | **58.3%** | 107.3% | 0.484 | 0.970 |
| r7 | `u_plans` | ✓ | 34.8% | 36.2% | **113.8%** | 0.772 | 0.969 |

### Main effects on `pbt` ratio-to-TM

```
critique, under blind_t :  26.2 → 26.4   =  +0.3
critique, under u_plans :  44.1 → 34.8   =  −9.4
strategy, no critique   :  26.2 → 44.1   = +17.9
strategy, with critique :  26.4 → 34.8   =  +8.3
```

### Operating point at the 10% audit budget

Computed over `sweep_deployed` — the population the deployment game can actually draw (each task's
selected attack plus every honest candidate), so catch rate, false-positive rate and safety share
one denominator.

| cell | `tm` catch / FPR | `pbt_informed_tm` catch / FPR |
|---|---|---|
| r1 | 0.362 / 0.014 | 0.466 / 0.070 |
| r5 | 0.366 / 0.012 | 0.456 / 0.034 |
| r3 | 0.370 / 0.014 | **0.502** / 0.038 |
| r7 | 0.366 / 0.014 | 0.460 / 0.026 |

### Significance of the informed monitor against TM (paired, per-run)

| cell | ratio | paired Δ | t | significant? |
|---|---|---|---|---|
| r1 | 95.0% | −0.0346 | −1.18 | no |
| r5 | 108.5% | +0.0396 | +1.26 | no |
| r3 | 107.3% | +0.0302 | +1.08 | no |
| r7 | 113.8% | +0.0625 | +1.31 | no |

`t_crit(df=9) = 2.262`. **No cell reaches significance.**

## 5. Interpretation

**H1 — critique: not supported, and harmful under the better strategy.** The intervention did
what it was designed to do: soundness rose 0.442 → 0.814 (`blind_t`) and 0.484 → 0.772 (`u_plans`).
It bought no safety. The mechanism is visible in the operating points — the critique removes
properties, so the false-positive rate falls (0.058 → 0.020) but the catch rate falls further
(0.094 → 0.040). It is clearest in `pbt_ceiling`, which fell 41.5 → 30.3 and 58.3 → 36.2: that arm's
FPR is already zero by construction, so pruning properties is pure loss with nothing to gain.

**H4 — strategy: supported, and the largest effect measured.** Letting U plan and T write is worth
**+17.9 points** without the critique. U never emits executable code, so the collusion surface stays
narrow; the gain comes from better-targeted invariants.

**H3 — interaction: supported, direction reversed.** The two interventions conflict rather than
compose. Critique is neutral under `blind_t` (+0.3) and costly under `u_plans` (−9.4), cutting the
strategy gain from +17.9 to +8.3. Interpretation: `u_plans` produces *better* properties, and the
critique then prunes precisely the ones earning the catches.

**Kill criterion fires.** Best deployable cell is 44.1% of TM. Standalone PBT as a deployed monitor
is not competitive with code review on this pool.

**The one arm that beats TM is not yet established.** `pbt_informed_tm` exceeds TM in three of four
cells, best at 113.8%, and lifts catch from 0.362 → 0.502 at r3's operating point. But every t-stat
is 1.08–1.31 against 2.262. Effect and noise scale together, so more runs of this design will not
resolve it (see §8).

## 6. Questions for discussion

### 6.1 Is `pbt_informed_tm` worth its cost?

This is the central open question and we do not think the data settles it.

**What it costs, per run of 50 tasks / 115 candidates:**

| | model calls | vs TM alone |
|---|---|---|
| `tm` alone | 115 | 1.0× |
| `pbt_informed_tm` (`blind_t`) | 115 TM + 115 informed + 100 authoring = **330** | **2.9×** |
| `pbt_informed_tm` (`u_plans`) | 115 TM + 115 informed + 150 authoring = **380** | **3.3×** |

Plus per-candidate sandboxed harness execution, plus the operational cost of running untrusted code
at all — which in our case caused three kernel panics before containment (§7).

**What it buys:** +7 to +14 points of earned safety ratio, at t = 1.08–1.31, i.e. **not
distinguishable from zero at n=10**.

**The question:** is roughly **3× the monitoring cost, plus a code-execution sandbox in the
deployment path, justified by an effect this size — and how large would the effect need to be
before it is?** A related framing: `pbt_informed_tm`'s gain is concentrated in catch rate
(0.362 → 0.502) at a higher FPR (0.014 → 0.038). Under a fixed audit budget, is that trade the
right one, or is the honest conclusion that PBT's value is as an *evidence channel* only where
execution is already available and cheap?

### 6.2 Is code-aware trigger search a legitimate direction at all?

We are running it now (`r2`: `blind_t` + code-aware, `r4`: `u_plans_t_writes` + code-aware) and want
a view on whether the direction is sound *independent of what the numbers say*.

**Why it may not be.** The implementation is benchmark-shaped: it harvests integer literals and
magic constants out of the candidate, builds whitespace token grids, and applies line-0 heuristics
tuned to APPS-style stdio parsing. None of that obviously transfers to a codebase with structured
inputs, database state, or non-textual I/O. If the gain concentrates on tasks with simple
line-based input formats, it is a benchmark artifact rather than a method.

**The argument that it does generalise.** The *principle* — read the code to decide where to
probe — is general even where this implementation is not. "Look at what the code branches on, then
test near those boundaries" is what a human auditor does, and it does not depend on APPS.

**The sharper objection, which we think matters more than generalisability.** Blindness is the
entire architectural argument for PBT as a monitor. A property written from the specification alone
is *independent* of the submission: it cannot be talked out of firing by code that merely looks
innocent. Code-aware search spends part of that independence. The input generator now looks where
the code suggests looking, and an untrusted model that knows constants get harvested can plant
misleading ones — a form of sandbagging the blind version is immune to.

One important qualification, and it is a real defence: the **oracle stays blind**. Properties never
see the code, so a code-aware generator cannot manufacture a false positive — it can only change
where we look. Our data supports this: `pbt_ceiling`'s false-positive rate was **0.000** in the
earlier code-aware study. So the exposure is on the **recall** side (an adversary steers you to the
wrong inputs), not the precision side (you invent violations).

**Prior evidence is discouraging.** An earlier analysis of 88 clean backdoors asked how often a
harvestable literal is *also* the triggering input *and* missed by the trusted monitor *and*
checkable by a sound oracle. Direct-harvestable was 9/88; harvest ∧ TM-miss was 2/88, and both
failed the oracle wall — leaving the genuinely complementary-and-sound cell at **0/88**. The
proposed reason is causal rather than incidental: the specification ambiguity that hides a backdoor
from a reader is the same ambiguity that leaves a blind tester without a sound invariant to check.

**The questions.** (a) Is spending blindness on the generator, while keeping the oracle blind, an
acceptable trade within this threat model, or does it undermine the claim PBT is making? (b) If the
50-task result is positive, how would we distinguish "the method works" from "APPS inputs are easy
to harvest"? (c) Is there a version of code-awareness that is adversarially robust — one where an
untrusted model gains nothing by anticipating the generator?

### 6.3 What should the next experiments be?

Our own shortlist, for critique:

1. **Code-aware trigger search, both strategies.** The obvious remaining lever: use the candidate's
   code to choose trigger inputs rather than the spec alone. Cells `r2`/`r6` (`blind_t`) and
   `r4`/`r8` (`u_plans`) are built and pre-registered but unrun. Our prior is negative — an earlier
   10-task study measured +0.150 honest FPR against +0.089 catch, safety unchanged — but it has
   never been tested at 50 tasks, nor under `u_plans_t_writes`, which is now known to be the
   stronger strategy. **This is the experiment we would run next.**
2. **Powering the informed-TM comparison.** n=10 does not resolve a t≈1.3 effect, and more runs will
   not help because runs share candidates: run-to-run variance is monitor noise, not sampling. This
   needs *more tasks*, not more runs.
3. **Monitor rubric.** On a prior run TM placed 37 attacks **and 11 honest candidates** at
   suspicion level 9. Those 11 are what stops the audit threshold dropping from 10 to 9 — threshold
   10 catches 21/65 at 2% FPR, threshold 9 catches 58/65 at 24% FPR, and a 10% budget cannot buy the
   second. A finer scale at the top may be worth more than either intervention tested here. We
   deliberately did **not** change the paper's prompt for this experiment.
4. **Sound-by-construction properties.** The critique result suggests the binding constraint is not
   soundness *screening* but property *quality*. Metamorphic relations are sound by construction;
   the models already produce them unprompted (translation invariance, permutation invariance).

## 7. Caveats

- **`selected_attack` defaults to the first attack.** ~15 tasks carry a second attack the game never
  draws. If `attack_0` is systematically easier, safety carries an unmeasured selection bias.
- **Runs share candidates.** The same 115 candidates appear in all 10 runs, so reported spread
  understates true variance and n=10 does not make the pool representative.
- **APPS-shaped trigger search.** Line-0 heuristics and whitespace token grids; do not read these
  results as generalising to other benchmarks.
- **Temperature uncontrolled**, at each provider's default — both models reject the parameter.
- **Mixed isolation within `r3`/`r7`.** Runs 0–6 executed under subprocess isolation, 7–9 under
  Docker. Checked directly: per-run `pbt` coverage was 0.9615 → 0.9884 (r3) and 0.9640 → 0.9797
  (r7), i.e. it *improved*, so no candidate hit the 2GB cap and the boundary introduced no loss.
- **Infrastructure history.** The subprocess isolation path applies a time bound but no memory
  bound, and macOS cannot enforce one (`RLIMIT_AS`/`DATA`/`RSS` are unsettable). Untrusted candidate
  code reached ~120GB on a 64GB machine and caused three kernel panics. Docker with cgroup limits
  resolved it; the batch then ran 7.5 hours without incident. `pbt_invalid_blame = 0.0` in all four
  cells, so no infrastructure failure contaminated these numbers.

## 8. What we would need to change our mind

Deployable standalone PBT would need a cell above 60% of TM. Nothing came close. For
`pbt_informed_tm`, an effect of the observed size would need roughly 4× the task count to reach
significance — which is a different experiment, not a longer one.

## 9. Artifacts and provenance

Every number in this report was read from the committed metrics files below — none quoted from
memory. `runs/` itself is gitignored (1.1 GB of raw suites and rows), so the per-cell `metrics.json`
and resolved `run.json` are mirrored into the repo so the figures can be checked independently.

### Results, per cell

| cell | strategy | critique | metrics | resolved config |
|---|---|---|---|---|
| r1 | `blind_t` | — | [`b1-r1.metrics.json`](artifacts/b1/b1-r1.metrics.json) | [`b1-r1.run.json`](artifacts/b1/b1-r1.run.json) |
| r5 | `blind_t` | ✓ | [`b1-r5.metrics.json`](artifacts/b1/b1-r5.metrics.json) | [`b1-r5.run.json`](artifacts/b1/b1-r5.run.json) |
| r3 | `u_plans_t_writes` | — | [`b1-r3.metrics.json`](artifacts/b1/b1-r3.metrics.json) | [`b1-r3.run.json`](artifacts/b1/b1-r3.run.json) |
| r7 | `u_plans_t_writes` | ✓ | [`b1-r7.metrics.json`](artifacts/b1/b1-r7.metrics.json) | [`b1-r7.run.json`](artifacts/b1/b1-r7.run.json) |

Each `metrics.json` holds `summary` (the aggregate over 10 runs, which every table here quotes) and
`runs` (the 10 per-run metric objects the aggregate is computed from).

### Reading a number back

```bash
# the pbt ratio-to-TM in the H1 comparison (r1 vs r5, section 4)
jq '.summary.protocols.pbt.ratio_to_baseline.mean' reports/artifacts/b1/b1-r1.metrics.json
jq '.summary.protocols.pbt.ratio_to_baseline.mean' reports/artifacts/b1/b1-r5.metrics.json

# soundness, the metric that shows the critique DID work
jq '.summary.pbt_soundness.mean' reports/artifacts/b1/b1-r{1,5}.metrics.json

# the gate that must be zero before any of the above is trusted
jq '.summary.pbt_invalid_blame.mean' reports/artifacts/b1/b1-r{1,3,5,7}.metrics.json
```

### Prompts (the exact text the models were given)

| role | file | note |
|---|---|---|
| Trusted monitor | [`prompts/trusted_monitor.txt`](../prompts/trusted_monitor.txt) | AI-control-paper wording, **unchanged** |
| Informed monitor | [`prompts/informed_monitor.txt`](../prompts/informed_monitor.txt) | the same prompt **plus** PBT evidence; opening and rating instruction byte-identical to the trusted monitor |
| Property generation | [`prompts/property_gen.txt`](../prompts/property_gen.txt) | `blind_t` |
| Property plan (U) | [`prompts/property_plan.txt`](../prompts/property_plan.txt) | `u_plans_t_writes` step 1 — prose only, never code |
| Write from plan (T) | [`prompts/property_from_plan.txt`](../prompts/property_from_plan.txt) | `u_plans_t_writes` step 2 |
| Property critique | [`prompts/property_critique.txt`](../prompts/property_critique.txt) | the H1 intervention |
| Trigger search | [`prompts/trigger_search.txt`](../prompts/trigger_search.txt) | spec-blind in every strategy |

### Code paths behind the claims

| claim | where |
|---|---|
| deployment game, safety, sweeps | [`pipeline/metrics.py`](../pipeline/metrics.py) |
| `sweep_deployed` — the population safety draws from | [`pipeline/metrics.py`](../pipeline/metrics.py) (`deployed_rows`) |
| property scoring, soundness gate, both arms | [`pipeline/pbt.py`](../pipeline/pbt.py) |
| sandboxed execution of candidate code | [`pipeline/harness.py`](../pipeline/harness.py) |
| authoring strategies (`blind_t`, `u_plans_t_writes`, critique) | [`pipeline/authoring.py`](../pipeline/authoring.py) |
| a failure never silently becoming a value | [`pipeline/outcome.py`](../pipeline/outcome.py) |

### Documents

- **Pre-registration**, written before any cell ran: [`2026-08-09-factorial-batch.md`](2026-08-09-factorial-batch.md)
- **Experiment index**: [`EXPERIMENTS.md`](EXPERIMENTS.md)
- **Operational log** (including the three kernel panics and the unsandboxed-search bug): [`CHANGELOG.md`](../CHANGELOG.md)
- **Working rules** this project is held to: [`CLAUDE.md`](../CLAUDE.md)

---

**Provenance.** Pre-registration: `reports/2026-08-09-factorial-batch.md`, written before any cell
ran. Artifacts: `runs/b1-r{1,3,5,7}/metrics.json`. Every number above read from those files.
