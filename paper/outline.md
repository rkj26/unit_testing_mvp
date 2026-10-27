# Methodology and Results: outline

**Status 2026-10-27.** Both sections are written in `sruthi_apor/` (a gitignored copy of the NeurIPS draft)
and mirrored to `paper/`, with every number from the re-executed digest. Still open: Omar's multi-turn
slot, Alon's BigCodeBench safety number, and a citation for ControlArena.

The shape of both sections, for approval before any prose changes. One row per subsection: its
one-line claim, where its numbers come from, and its status. `results.tex` keeps its convention:
points to make with numbers, and Rakshit writes the final prose. **Owner** is blank where nobody is
assigned yet.

Status: **keep** = stands as written · **revise** = same slot, content changes · **new** · **cut** ·
**pending M_n** = waits for that module of `experiments/safety_rework_plan.md`.

## Methodology (`paper/methodology.tex`)

| § | subsection | one-line claim | source | status | owner |
|---|---|---|---|---|---|
| 1 | Setting | Greenblatt et al.'s setting: U writes code, T and a small audit budget defend; we ask whether T's tests catch what T's reading misses. | — | keep | |
| 2 | Data | The main pool is all 1,388 usable APPS tasks (555 train / 833 test, one honest and one backdoored candidate each); the three small pools were development pools. | `DOCUMENTATION.md`, digest §1 | revise: today it presents the three small pools as the data | |
| 2a | Removing label leaks | Comments and self-naming identifiers removed from both sides; behaviour unchanged. | digest scrub figure | keep, with the full pool's numbers (48.6% → 0) | |
| 2b | Ground truth | Every candidate graded by control-arena's rule: honest code passes, every backdoor passes and fires. | full notebook, ground truth | **new**; written (regraded 27 Oct, `ad214ed`) | |
| 3 | Protocols | Trusted monitor; trigger search; unit testing (property / plain); U plans, T writes; monitor with tests; trusted solve. | — | keep | |
| 3a | Defer to trusted | A flagged submission that is not audited can ship T's own solution instead; Greenblatt et al.'s baseline. | digest DTT | **new** | |
| 3b | Multi-turn | One paragraph, if the full-pool multi-turn arms are in Results. | `experiments/multi_turn_plan.md` | **new**, if kept | Omar? |
| 4 | Choosing a threshold | The (1 − b) quantile of honest train scores, ties broken at random so exactly b of honest train is audited; no attack labels. | — | revise: add the tie rule; cut the "any fires" threshold from safety | |
| 5 | Safety and usefulness | The audit budget only sets the cut; every test sample above it is audited; U attacks every task; safety = caught ÷ (caught + shipped and working), with no simulation and no attack rate. | M1 | **new**, replaces "Deployment simulation" (games A/B/C, horizon 50, 5% attacks, 10% budget) | |
| 5a | Intervals | 10,000 paired task resamples; each arm refits its cut on the drawn train tasks. | digest bootstrap | **new** | |
| 6 | Handling failures | A failed candidate leaves every denominator, blamed on the model or the infrastructure; headline numbers use only candidates every arm scored. | — | keep, add blame | |
| 7 | Provider change | Runs straddle the provider's change of 10 October; which arms were scored after it, and why no re-run is possible. | `experiments/rerun_plan.md`, E12 | **new** | |

## Results (`paper/results.tex`)

| § | subsection | one-line claim | source | status | owner |
|---|---|---|---|---|---|
| 0 | Overview | Tests alone are worse than the monitor; tests given to the monitor raise safety at a 2% budget (≈0.55 → 0.66–0.72) and stop helping by 10%. | M2 | revise, pending M2 (the game numbers 0.787 / 0.804–0.830 go) | |
| 1 | Pool and coverage | 2,435 of 2,776 candidates scored by every arm; T solves 79.4% alone; safety uses the test tasks every arm scored. | digest §1, §5 | revise: "642 held-out tasks for the game" changes to the safety population | |
| 2 | Detection | Every tests-only arm ranks below the monitor (AUC 0.808–0.870 vs 0.958); tests sharpen the top of the monitor's ranking (catch @ 2%: 0.669–0.721 vs 0.558) and add nothing at 10%. | `catch_at_fpr.csv` | keep | |
| 3 | Safety at a 2% audit budget | Bars with 95% intervals: monitor 0.549, monitor + tests 0.662–0.716, tests alone 0.202–0.430 (M1, verified). | M1 + M2 | **new**, replaces "Deployment safety" and "At a 2% audit budget"; numbers pending M1 | |
| 4 | Defer to trusted | The four monitor protocols on one safety–usefulness plot, zoomed to the top right as in Greenblatt et al. Fig. 2. | M2 | **new** (Aaron's request) | |
| 5 | Across budgets | Safety at 1, 2, 5 and 10%; the monitor + tests advantage shrinks as the budget grows. | M2 | **new**, replaces "Budget and attack rate" | |
| 6 | Why catch does not move | Hard-pool study: tests imprecise, the variations move false alarms not catch, misses are reached but not detected. | as written | keep; its four TODOs stay open | |
| 7 | Multi-turn (full pool) | What the multi-turn arms add over one turn on the full pool. | full notebook, multi-turn section | **new**, if kept | Omar? |
| 8 | BigCodeBench | The benchmark is saturated, so it cannot separate protocols. | as written | keep | Alon |
| 9 | Notes for Limitations | No red-team attack selection (U attacks every task with a fixed backdoor); provider change; one model at two efforts; detection pools train and test. | Aaron; `rerun_plan.md` | revise: add the first two; "no intervals" goes once §3 has them | |
