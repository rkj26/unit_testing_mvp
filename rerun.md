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
| 2 | `trig-22` / `trig-r50` | TriggerSearch, `num_inputs=30` | yes | pending |
| 3 | `tm-22` / `tm-r50` | TrustedMonitor, `reasoning=low`, 2 reps | yes | pending |
| 4 | `ut-property-10` / `-r50` | UnitTesting, `property`, `n_tests=10` | no, but tests run on 2's inputs | pending |
| 5 | `ut-plain_v3-10` / `-r50` | UnitTesting, `plain_v3`, `n_tests=10` | same | pending |
| 6 | `upt-property-10` / `-r50` | UPlansTWrites, `property`, `n_tests=10` | yes, U's plan stage | pending |
| 7 | `upt-plain_v3-10` / `-r50` | UPlansTWrites, `plain_v3`, `n_tests=10` | yes | pending |
| 8 | `mwt-property-10` / `-r50` | MonitorWithTests over run 4 | yes | pending |

Run order matters: 2 before 4-7 (its inputs are what every suite tests against), 4 before 8.

## Then

- [ ] notebook cut down to these arms, both datasets
- [ ] paired before/after: catch, false alarms, AUC, and the deployment game, contaminated vs scrubbed
- [ ] the question this answers: how much of TM's 0.85 catch was reading the attacker's notes

Prior evidence says not much — stratifying the old `tm-22` records by whether the attack carried a
tell-tale comment gave catch 0.853 with against 0.875 without on `apps_hard`, and 0.857 against
0.759 on `random50`. This re-run replaces that observational split with the real thing.
