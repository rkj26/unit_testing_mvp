# Re-run on the scrubbed pool

Why: the pool's attacks arrived carrying their own labels. 68% of `apps_hard` attacks (42% of
`apps_random50`) held a comment naming the backdoor — `# Subtle bug: ...`, `# The bug is here` —
against 0% of honest submissions, and two attacks had local variables called `bug` and `flaw`. The
attacks are not ours: they come from `RoganInglis/apps-control-arena`, `source == "control_tax"`,
and every gate in `_usable_backdoors` is behavioural (`compiles`, `passes_tests`, `backdoor_works`).
Nothing ever looked at the text.

Every run below is scored against the archived equivalent in `archived/runs/`, so each arm reports a
before and an after rather than a number on its own.

## Done

- [x] `archived/runs/`, `archived/data/` — the contaminated generation, kept for the pairing
- [x] `build_dataset.py --scrub-tells` — comments cut, comment-only lines deleted, self-naming
      identifiers renamed; applied to honest and attack alike so comment-free is not itself a label
- [x] `data/apps_hard.json`, `data/apps_random50.json` rebuilt in place — 0 comments, 0 self-naming
      identifiers, 0 untokenisable candidates
- [x] behaviour unchanged: 2,237 provided pairs re-run, **0 outputs moved**; 100/100 backdoors still
      fire on their secret input
- [x] pool audit — docstrings clean, no attack-naming string literals, secret input appears verbatim
      in 2/100 attacks, formatting alone separates honest from attack at AUC 0.60 (chance)

## Runs

`solve` is restored rather than re-run: `trusted_solve.txt` has no `{code}`, so the scrub cannot
reach it. Everything else either reads candidate code or consumes something that did.

| # | run name | protocol | reads code? | status |
|---|---|---|---|---|
| 1 | `solve-22` / `solve-r50` | TrustedSolve | no | restore from archive |
| 2 | `trig-22` / `trig-r50` | TriggerSearch, `num_inputs=30` | yes | done (hard), 1 model failure |
| 3 | `tm-22` / `tm-r50` | TrustedMonitor, `reasoning=low`, 2 reps | yes | done (hard) |
| 4 | `ut-property-10` / `-r50` | UnitTesting, `property`, `n_tests=10` | no, but tests run on 2's inputs | done (hard) |
| 5 | `ut-plain_v3-10` / `-r50` | UnitTesting, `plain_v3`, `n_tests=10` | same | done (hard) |
| 6 | `upt-property-10` / `-r50` | UPlansTWrites, `property`, `n_tests=10` | yes, U's plan stage | done (hard) |
| 7 | `upt-plain_v3-10` / `-r50` | UPlansTWrites, `plain_v3`, `n_tests=10` | yes | done (hard) |
| 8 | `mwt-property-10` / `-r50` | MonitorWithTests over run 4 | yes | done (hard) |

Run order matters: 2 before 4-7 (its inputs are what every suite tests against), 4 before 8.
`scratch/launch_scrubbed.py` runs apps_hard in that order, three arms at a time; the notebook's
own `.run()` calls then find every candidate already scored and spend nothing. random50 is held
back until the hard pool reads sensibly.

## Then

- [x] notebook cut down to these arms (apps_hard); section 5 dropped with the critique arms
- [ ] same for random50
- [x] paired before/after: catch, false alarms, AUC, and the deployment game
- [x] the question this answers: how much of TM's 0.85 catch was reading the attacker's notes

Prior evidence says not much — stratifying the old `tm-22` records by whether the attack carried a
tell-tale comment gave catch 0.853 with against 0.875 without on `apps_hard`, and 0.857 against
0.759 on `random50`. This re-run replaces that observational split with the real thing.

## What the re-run found

Matched population 87/100 (43 honest, 44 attack; 39 of 50 tasks keep both submissions). The 13
missing are 1 model failure in trigger search and 12 sandbox timeouts on slow programs — a bias
towards fast programs, and the largest known weakness in these numbers.

| arm | AUC contaminated | AUC scrubbed | catch @ cut | false alarms |
|---|---|---|---|---|
| monitor | 0.925 | 0.874 | 0.818 | 0.186 |
| monitor + tests | — | **0.885** | 0.818 | **0.116** |
| u plans plain_v3/10 | — | 0.763 | 0.841 | 0.419 |
| u plans property/10 | 0.793 | 0.748 | 0.841 | 0.465 |
| tests property/10 | 0.718 | 0.707 | 0.886 | 0.651 |
| tests plain_v3/10 | — | 0.639 | 0.682 | 0.558 |

The prediction going in was that catch would barely move. It did not — it moved 0.02. **False alarms
went 0.080 to 0.200**, which was not the quantity anyone was watching. The comments were evidence
that honest code was fine, not evidence that attacks were bad.

`monitor + tests` looked like the result worth keeping — same catch, two thirds of the false alarms
— until the exchange underneath was counted. On the 43 honest candidates the suite's silence clears
8 of the monitor's false alarms and the suite's firing creates 5 new ones. Net 3, exact two-sided
McNemar p = 0.58. It needs a bigger pool before it means anything.

The one clean effect is U-planning: lower false alarms than T-alone at both framings, with catch
holding or rising. That is the arm to build on.

## Follow-ups this raised

- [ ] the trigger prompt lets the model answer with Python expressions (`"0 " * 98`) instead of JSON
      strings; deterministic at `runs=1`, so `apps_3941_attack_0` fails forever. Not fixed here —
      it re-runs all 100 and adds a second variable to a one-variable comparison.
- [ ] `sandbox_seconds=240` is short for these grids: 12 candidates timed out mid-grid. A clean
      re-run wants a bigger budget, and the budget must be uniform within a run to keep the
      artifact honest.
- [ ] random50, still on the contaminated generation's notebook.
