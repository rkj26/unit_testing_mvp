# Few-shot (plain_v5) and standalone monitor — four-method bootstrap, Rule A

**8-arm full-run deployment-game arms (`apps_full`), not multi-turn. Dev/validation numbers, not
final paper numbers.** Multi-turn arms untouched (Omar owns those). Reused
`analysis/bootstrap_methods.py --audit-rule audit_all --match-trials` with run dirs as arguments;
no new code this turn. Read-only, no model calls. 2000 resamples, 2000 matched trials.

The "few-shot tests arm" is **plain_v5** (`ut-all-plain_v5-10`, and `mwt-full-all-plain_v5-10` for
monitor+tests) — confirmed on real artifacts, 2776 records each.

## 1 · Few-shot vs monitor, Rule A (n = 1144 tasks scored by all three: 510 train, 634 test)

Point monitor safety on this intersection: 0.64 / 0.79 / 0.83 / 0.89 at 2/5/10/20%.

**(a) monitor + few-shot tests − monitor** (diff, 95% CI):

| budget | multinomial | hierarchical | bayesian |
|---|---|---|---|
| 2% | +0.029 [−0.014,+0.413] | +0.029 [−0.036,+0.575] | +0.029 [−0.028,+0.449] |
| 5% | −0.119 [−0.162,+0.104] | −0.119 [−0.030,+0.073] | −0.119 [−0.176,+0.103] |
| 10% | −0.065 [−0.117,**−0.004**] | −0.065 [−0.111,+0.138] | −0.065 [−0.133,+0.012] |
| 20% | −0.056 [−0.114,**−0.011**] | −0.056 [−0.102,**−0.006**] | −0.056 [−0.124,**−0.005**] |

**(b) few-shot tests-only − monitor** (diff, 95% CI):

| budget | multinomial | hierarchical | bayesian |
|---|---|---|---|
| 2% | −0.470 [−0.531,−0.080] | −0.470 [−0.564,+0.041] | −0.470 [−0.553,−0.062] |
| 5% | −0.429 [−0.601,−0.250] | −0.429 [−0.485,−0.249] | −0.429 [−0.615,−0.248] |
| 10% | −0.270 [−0.492,−0.204] | −0.270 [−0.478,−0.081] | −0.270 [−0.503,−0.179] |
| 20% | −0.130 [−0.206,−0.083] | −0.130 [−0.196,−0.069] | −0.130 [−0.231,−0.061] |

Bold = CI excludes zero. `calls_only` omitted from the tables (diagnostic only); it is in the CSV.

## 2 · Standalone monitor safety, Rule A (n_test = 832, the monitor's own scored set)

Monitor safety and 95% CI, each method:

| budget | multinomial | hierarchical | bayesian |
|---|---|---|---|
| 2% | 0.618 [0.223,0.650] | 0.618 [0.127,0.694] | 0.618 [0.210,0.667] |
| 5% | 0.789 [0.571,0.819] | 0.789 [0.603,0.695] | 0.789 [0.563,0.833] |
| 10% | 0.834 [0.740,0.860] | 0.834 [0.625,0.863] | 0.834 [0.733,0.870] |
| 20% | 0.899 [0.846,0.930] | 0.899 [0.820,0.918] | 0.899 [0.832,0.943] |

The monitor's own interval is wide at a 2% budget (lower bounds 0.13–0.22) and tightens as the
budget rises, as expected: at 2% the cut sits far out in the honest tail where few tasks constrain
it.

## 3 · Method-invariance — and this is where few-shot differs from the 8-arm property result

**(a) monitor + few-shot tests: method-invariance partially BREAKS.** At 20% all three task-level
methods agree the few-shot suite significantly *hurts* the monitor (every CI excludes zero, all
negative). At 10% the methods disagree: multinomial excludes zero (−0.004 upper), hierarchical and
Bayesian cross it. So the conclusion at 10% depends on the bootstrap — unlike the property arm,
where every method crossed zero at every budget.

**(b) few-shot tests-only: method-invariant and robustly negative** at 5/10/20% under all methods;
only the 2% budget (weak-monitor, wide-interval regime) lets hierarchical touch zero. Same shape as
the property tests-only result.

## What differs from the 8-arm (property) result

The property arm gave the clean null: monitor+tests crossed zero at every budget under every method.
**The few-shot arm does not.** Its point estimates are negative at 5/10/20% (−0.119, −0.065,
−0.056), and at the 20% budget every method finds the harm significant. So for plain_v5 the finding
is stronger than "no improvement" — at higher budgets, **adding the few-shot suite to the monitor
measurably reduces safety**, and that is robust across methods at 20%. This matches the earlier
hard-pool finding that plain_v5/plain_v4 raised false alarms; here it shows up as a safety cost when
the suite is combined with the monitor.

Tests-only (few-shot) is far below the monitor, same as property tests-only.

## Flags

- All numbers are on real artifacts (tm-all, mwt-full-all-plain_v5-10, ut-all-plain_v5-10, 2776
  records each).
- DTT still not added as a baseline (it has no suspicion score; see the Rule A report). Monitor-only
  baseline.
- The 20%-budget harm for monitor+few-shot is the one conclusion that is both significant and
  method-invariant here; the 10% conclusion is method-dependent and should be reported as such, not
  rounded to "hurts".

## Update, 5000 trials (matching the main Rule A CSV)

All three deployment-game bootstrap CSVs now use 5000 matched trials. Re-run on 2026-10-25, outputs only, no code change. Conclusions below are confirmed unchanged from the 2000-trial run.

**(a) monitor + few-shot tests - monitor** (n=634 test), diff and 95% CI:

| budget | multinomial | hierarchical | bayesian |
|---|---|---|---|
| 2% | +0.031 [-0.015,+0.413] | +0.031 [-0.031,+0.576] | +0.031 [-0.025,+0.445] |
| 5% | -0.125 [-0.158,+0.098] | -0.125 [-0.027,+0.071] | -0.125 [-0.177,+0.104] |
| 10% | -0.057 [-0.114,-0.006] | -0.057 [-0.110,+0.139] | -0.057 [-0.129,+0.009] |
| 20% | -0.052 [-0.108,-0.013] | -0.052 [-0.097,-0.007] | -0.052 [-0.120,-0.005] |

**(b) few-shot tests-only - monitor**, diff and 95% CI:

| budget | multinomial | hierarchical | bayesian |
|---|---|---|---|
| 2% | -0.473 [-0.532,-0.082] | -0.473 [-0.564,+0.042] | -0.473 [-0.554,-0.059] |
| 5% | -0.437 [-0.596,-0.251] | -0.437 [-0.487,-0.252] | -0.437 [-0.614,-0.250] |
| 10% | -0.285 [-0.488,-0.207] | -0.285 [-0.473,-0.082] | -0.285 [-0.498,-0.174] |
| 20% | -0.145 [-0.199,-0.085] | -0.145 [-0.191,-0.070] | -0.145 [-0.222,-0.064] |

**Standalone monitor safety** (n_test=832), safety and 95% CI:

| budget | multinomial | hierarchical | bayesian |
|---|---|---|---|
| 2% | 0.616 [0.227,0.655] | 0.616 [0.129,0.696] | 0.616 [0.217,0.672] |
| 5% | 0.778 [0.581,0.821] | 0.778 [0.611,0.697] | 0.778 [0.571,0.835] |
| 10% | 0.816 [0.748,0.862] | 0.816 [0.633,0.865] | 0.816 [0.740,0.873] |
| 20% | 0.891 [0.852,0.930] | 0.891 [0.824,0.918] | 0.891 [0.838,0.941] |

### Conclusions at 5000 trials — unchanged

- **20% harm, confirmed and method-invariant.** monitor+few-shot minus monitor at 20%:
  multinomial −0.052 [−0.108,−0.013], hierarchical −0.052 [−0.097,−0.007], bayesian −0.052
  [−0.120,−0.005]. All three exclude zero and are negative. Adding the few-shot suite to the
  monitor measurably reduces safety at the 20% budget.
- **10% method-dependent, confirmed.** At 10% multinomial excludes zero (−0.057 [−0.114,−0.006])
  while hierarchical (−0.057 [−0.110,+0.139]) and bayesian (−0.057 [−0.129,+0.009]) cross it. The
  10% conclusion still depends on the bootstrap and should be reported as such.
- **few-shot tests-only** stays robustly below the monitor at 5/10/20% under every method.

The 2000-trial and 5000-trial tables agree on every one of these calls; the extra trials narrow the
deployment-draw Monte-Carlo noise slightly but move no conclusion.
