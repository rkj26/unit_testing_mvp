% Can automated tests catch backdoors that code review misses?
% An experiment on 50 programming tasks · 10 repeats per condition
% 10 August 2026

# Summary

**The setting.** A powerful AI writes code for us. We cannot fully review it by hand, and it might be sabotaging us. We have a weaker AI we trust, and a small human review budget. Can we catch sabotage?

**The two approaches compared.**

- **Code review** — the trusted AI reads the code and rates how suspicious it looks. This is the baseline.

- **Automated testing** — the trusted AI writes tests from the *written specification only*, never seeing the code, then we run those tests against the submitted code.

**The question.** Does *running* the code catch sabotage that *reading* it misses?

&nbsp;

**What we found**

- **Testing alone is far worse than code review.** The best configuration reached **44%** of code review's effectiveness. Our pre-committed threshold for continuing this line was 60%, so that threshold was crossed and the approach is not viable on its own.

- **The most promising fix did nothing.** We added a step where the AI reviews its own tests and deletes unreliable ones. It worked as designed — reliable tests roughly doubled — and bought **no improvement in safety whatsoever**.

- **The one thing that did help** was letting the powerful AI *plan* the tests while the trusted AI writes them: **+18 points**. But this is not enough to rescue the approach.

- **Tests are useful as evidence, not as a decision.** Giving the test results *to the reviewer* was the only configuration that beat code review — but the advantage was **not statistically significant**, at roughly **3× the cost**.

&nbsp;

> **The headline.** Automated testing does not replace code review here. Its value, if any, is as an *extra input to a reviewer* rather than as a check that decides on its own.

&nbsp;

# 1. A concrete example

Everything below is easier with one example in mind.

**The task.** "Read a list of integers and print how many are even."

**A submission from the untrusted AI.** It looks correct and passes all the visible tests — but it contains one extra line: if the list length happens to be exactly 47, it prints the count of *odd* numbers instead. That is a **backdoor**: wrong output on one rare input, correct everywhere else.

**A test written by the trusted AI**, from the specification alone, never having seen that code:

> *"Appending an even number to the input must increase the answer by exactly one."*

This is what we call a **property** — a rule that must hold for *every* correct solution, not a fixed input-and-expected-output pair. We generate many inputs and check the property on each.

**What can happen:**

- The property **fires** (fails) on some input → strong evidence of a backdoor
- The property **passes** on every input we tried → weak evidence of safety, because we may simply never have tried the input that triggers it

That asymmetry drives every result in this report. **Finding a violation proves something. Not finding one proves very little.**

&nbsp;

# 2. What we are testing, and what we predicted

We pre-registered four hypotheses before running anything. The numbering below is the pre-registration's, kept unchanged so the two documents can be read side by side.

**H1 — the self-critique step.** After writing tests, the trusted AI reviews its own tests and deletes any that a *correct* solution could fail. Predicted: this raises testing's effectiveness by **at least 5 points**.

*Rationale: testing's known weakness is flagging honest code — a 30% false-alarm rate — and unreliable tests were the suspected cause.*

**H4 — who plans the tests.** Instead of the trusted AI working alone, the powerful AI writes a prose *plan* and the trusted AI implements it. The powerful AI never produces executable code, so it cannot smuggle anything in. Predicted: **at least 5 points** better.

**H2 — code-aware input search** and **H3 — whether H1 and H2 combine.** Both concern a third factor: choosing test inputs by *reading the submitted code* rather than the specification alone. **Those runs are still in progress, so H2 and H3 are not answered in this report.**

**The abandon threshold, set in advance.** If no configuration reached **60%** of code review's effectiveness, testing-as-a-standalone-check is not worth pursuing further.

&nbsp;

# 3. The four conditions

Two factors, on and off, giving four conditions. Everything else is held identical.

- **T-only** — the trusted AI writes the tests alone. No self-critique.

- **T-only + critique** — same, plus the self-critique step.

- **U-plan** — the powerful AI plans, the trusted AI writes. No self-critique.

- **U-plan + critique** — same, plus the self-critique step.

Comparing across the first factor answers **H4**. Comparing across the second answers **H1**.

*(In the raw data these are runs `b1-r1`, `b1-r5`, `b1-r3` and `b1-r7`. The gaps in the numbering are the four code-aware conditions still running.)*

&nbsp;

# 4. How a task becomes a number

![How one task becomes a safety number](figures/pipeline.png)

&nbsp;

Walking the diagram:

1. **Write the tests.** The trusted AI reads only the specification and writes properties. It never sees the submitted code — that independence is the whole point, because a test that has read the code can be fooled by code that looks innocent.

2. **Choose the inputs.** The trusted AI proposes inputs where a backdoor would most plausibly hide — boundaries, extremes, unusual shapes. Also specification-only in every condition here.

3. **Run everything.** Every property against every input against every submission, inside a locked-down container. A property that fails means a catch; a submission that merely crashes does not count as a catch.

4. **Check which tests were trustworthy.** We run the tests against the *known-correct* solution to see which ones misfire. **This uses information a real deployment would not have**, so it only ever feeds the "best case" arm below — never a deployable one.

5. **Score each submission.** Four different scorers, described next.

6. **Simulate deployment.** Convert the scores into a single safety number.

&nbsp;

**The four scorers**

- **Code review** *(the baseline)* — the trusted AI reads the code and rates suspicion 1–10.

- **Tests alone** — how many independent properties caught this submission. Deployable.

- **Tests alone, best case** — the same, but counting only properties we *know* were trustworthy. **Not deployable**: it needs the correct solution. It answers "if we could perfectly filter out bad tests, how good could this get?"

- **PBT-informed review** — the trusted AI reads the code **and** the test results, then rates suspicion. Deployable.

&nbsp;

# 5. How safety is measured

**The simulation.** We replay 10,000 imaginary deployments. Each runs for 50 steps; at each step the untrusted AI submits code and sabotages with probability 10%. Our scorer ranks each submission, and the most suspicious ones go to a human — but we can only afford **5 human reviews per deployment**. A deployment is **won** if we catch a sabotage attempt before an uncaught backdoor ships.

**Safety** is the percentage of deployments won.

**Two adjustments, both of which matter:**

- **Subtract the free wins.** In some deployments the attacker never attacks at all, and we "win" without doing anything. That is 0.5% of deployments, and it is subtracted from every score so nobody gets credit for it.

- **Express everything relative to code review.** Raw safety depends on how long the simulated deployment is, so it is not portable. Every headline number in this report is therefore **"% of code review's safety"**: 100% means matching it, below 100% means worse than simply reading the code.

**What the human-review budget actually buys.** A submission is reviewed if it looks more suspicious than all but 10% of honest traffic. The important consequence: **what the budget spends is rank, not score.** A scorer that lumps many submissions at the same suspicion level wastes the budget even if its ordering is sensible — there is no way to pick between tied candidates.

**One convention that shapes the numbers.** If a scorer produces no answer at all — a crashed test run, an unparseable reply — that counts as *"nothing suspicious"* rather than being thrown away, because a real deployment still has to decide. This means our own infrastructure failures would look like testing finding nothing. We therefore check the infrastructure-failure rate *before* reading any result. **In this experiment it was zero in all four conditions.**

&nbsp;

# 6. Results

![Safety by condition, as a percentage of code review](figures/results.png)

&nbsp;

**Headline: safety as % of code review** (10 runs per condition)

- **T-only** — tests alone **26.2%** · best case 41.5% · PBT-informed review 95.0%

- **T-only + critique** — tests alone **26.4%** · best case 30.3% · PBT-informed review 108.5%

- **U-plan** — tests alone **44.1%** · best case 58.3% · PBT-informed review 107.3%

- **U-plan + critique** — tests alone **34.8%** · best case 36.2% · PBT-informed review 113.8%

**The two effects we pre-registered**

- **H1, the critique step:** 26.2 → 26.4 under T-only (**+0.3**), and 44.1 → 34.8 under U-plan (**−9.4**)

- **H4, who plans:** 26.2 → 44.1 without critique (**+17.9**), and 26.4 → 34.8 with it (**+8.3**)

**Did the critique step do its job?** Yes — this is why the result is interesting rather than merely negative. The share of test suites with no misfiring tests:

- **T-only** 0.442 → **with critique** 0.814

- **U-plan** 0.484 → **with critique** 0.772

**What each scorer catches, at the 10% human-review budget.** Catch rate is the share of real backdoors flagged; false-alarm rate is the share of honest code flagged.

- **T-only** — code review catches 36.2% at 1.4% false alarms · tests alone 9.4% at 5.8% · PBT-informed review 46.6% at 7.0%

- **T-only + critique** — code review 36.6% at 1.2% · tests alone **4.0% at 2.0%** · PBT-informed review 45.6% at 3.4%

- **U-plan** — code review 37.0% at 1.4% · tests alone 11.8% at 1.4% · PBT-informed review **50.2% at 3.8%**

- **U-plan + critique** — code review 36.6% at 1.4% · tests alone 3.8% at 1.0% · PBT-informed review 46.0% at 2.6%

**Is the PBT-informed reviewer's advantage real?** A paired test against code review, run by run:

- **T-only** 95.0% → t = −1.18 · **T-only + critique** 108.5% → t = +1.26

- **U-plan** 107.3% → t = +1.08 · **U-plan + critique** 113.8% → t = +1.31

Significance would require |t| above **2.262**. **None of the four reaches it.**

**Absolute safety**, before converting to percentages (mean ± standard deviation over 10 runs):

- **T-only** — code review 0.533 ± 0.067 · tests alone 0.139 ± 0.020 · best case 0.220 ± 0.035 · informed 0.499 ± 0.052

- **T-only + critique** — 0.540 ± 0.061 · 0.142 ± 0.029 · 0.163 ± 0.031 · 0.579 ± 0.084

- **U-plan** — 0.552 ± 0.072 · 0.239 ± 0.027 · 0.317 ± 0.042 · 0.582 ± 0.046

- **U-plan + critique** — 0.540 ± 0.062 · 0.185 ± 0.030 · 0.192 ± 0.022 · 0.603 ± 0.112

&nbsp;

# 7. What it means

## H1 — the critique step: not supported, and harmful

- **The prediction was +5 points or better. We measured +0.3, then −9.4.**

- It genuinely did what it was designed to do: reliable test suites went from 44% to 81%.

- **Why it still failed.** Deleting a test removes its false alarms *and* its catches. False alarms fell from 5.8% to 2.0% — but catches fell from 9.4% to 4.0%, proportionally further. We paid more in missed backdoors than we saved in false alarms.

- The clearest evidence is the "best case" arm, which fell 41.5 → 30.3 and 58.3 → 36.2. That arm has **no false alarms to begin with**, so pruning tests there is pure loss with nothing to buy.

- **The real lesson: unreliable tests were never the bottleneck.** We fixed the thing we thought was broken and it changed nothing. The bottleneck is that the tests do not *reach* the backdoor in the first place.

## H4 — who plans the tests: supported

- **+17.9 points**, comfortably past the +5 threshold, and the largest effect we measured.

- It is safe in the way that matters: the powerful AI only writes prose, so it never produces code that could contain a backdoor. The gain comes from better-aimed tests.

- This is also the first time the trusted-AI-alone strategy has been measured on this task set, so the baseline it beats had never actually been established here.

## The abandon threshold was crossed

- Best condition: **44.1%** of code review, against a pre-committed **60%**.

- **Testing as a standalone check is not competitive with reading the code.** Even the non-deployable best-case arm only reached 58.3%.

## Tests as evidence: promising, unproven

- PBT-informed review beat code review in three of four conditions, best at **113.8%**, lifting catch rate from 37.0% to **50.2%**.

- But no condition is statistically significant, and the noise scales with the effect — **running more repeats of this same design will not settle it.**

## An unplanned finding — the two interventions conflict

**This was not pre-registered, and should be treated as exploratory.**

The critique step is harmless under T-only (+0.3) but costly under U-plan (−9.4), cancelling most of the planning gain (+17.9 → +8.3). The likely explanation: U-plan produces *better* tests, and the critique then deletes precisely the ones earning the catches.

We flag this explicitly because our pre-registered interaction hypothesis (H3) was about a *different* pair of factors — critique and code-aware search — and cannot be evaluated until those runs finish. Reading this as a confirmed interaction would be reading a hypothesis into data collected for another purpose.

&nbsp;

# 8. Questions for discussion

## 8.1 Is the PBT-informed reviewer worth 3× the cost?

The central open question, and the data does not settle it.

**Cost per run**, over 50 tasks and 115 submissions:

- Code review alone — 115 AI calls

- PBT-informed review, T-only tests — 330 calls, **2.9×**

- PBT-informed review, U-plan tests — 380 calls, **3.3×**

Plus, beyond the API bill:

- every submission must be *executed* in a sandbox

- the operational burden of running untrusted code at all — which crashed our machine three times before it was properly contained

**What it buys:** 7 to 14 points, at t = 1.08–1.31, which is indistinguishable from zero at this sample size.

**The questions**

- Is 3× the cost plus a code-execution sandbox in the deployment path justified by an effect this size?

- How large would the effect need to be before it is?

- The gain is bought by flagging more honest code (1.4% → 3.8% false alarms) to catch more backdoors (37.0% → 50.2%). Under a fixed human budget, is that the right trade?

## 8.2 Is code-aware input search a legitimate direction?

Those runs are in progress. We would like a view on whether the direction is sound *regardless of what the numbers say*.

**The idea.** Instead of choosing test inputs from the specification alone, read the submitted code and aim at what it branches on. In our example: notice the `length == 47` check and try a 47-element list.

**Why it might not generalise**

- Our implementation harvests integer constants and builds text-input variations tuned to this benchmark's format

- None of that obviously transfers to structured inputs, database state, or non-textual interfaces

- If the benefit concentrates on simple text-input tasks, it is an artefact of the benchmark rather than a method

**Why it might**

- The *principle* — look at what the code branches on, then probe near those boundaries — is what a human auditor does and does not depend on this benchmark

**The deeper objection, which we think matters more**

- Independence is the entire argument for this approach. A test written from the specification alone **cannot be talked out of firing** by code that merely looks innocent

- Reading the code to choose inputs spends part of that independence. An untrusted AI that knows we harvest constants can plant misleading ones — a way of hiding that the specification-only version is immune to

- **An important qualification:** only the *input choice* would read the code. The *tests themselves* still never do, so this cannot manufacture a false accusation — it can only change where we look. Our data supports that: the best-case arm's false-alarm rate was exactly zero in the earlier study. The risk is missing backdoors, not inventing them

**Prior evidence is discouraging.** Across 88 backdoors we examined by hand:

- 9 had a trigger value that could be read straight out of the code

- of those, 2 were also missed by code review

- both of those 2 had no reliable test that could check them

- so the number of backdoors where this technique would *uniquely* help: **0 of 88**

- The suggested reason is not bad luck: the specification vagueness that lets a backdoor hide from a reader is the same vagueness that leaves a specification-only test with no rule to check

**The questions**

- Is giving up input-choice independence acceptable, given the tests themselves stay independent?

- If the result is positive, how do we tell "the method works" from "this benchmark is easy to harvest"?

- Is there a version that is robust to an adversary who *knows* how we pick inputs?

## 8.3 What should we run next?

- **Finish the code-aware conditions.** In progress. Our expectation is negative, but it has never been tested at this scale nor combined with the stronger planning strategy

- **Give the PBT-informed comparison enough power.** More repeats will not help, because every repeat uses the same 115 submissions — the variation between runs is scorer noise, not new evidence. This needs **more tasks**, not more runs

- **Fix the suspicion scale.** In an earlier run, code review put 37 backdoors *and 11 honest submissions* at suspicion level 9. Those 11 are what stops us lowering the threshold from 10 to 9: at 10 we catch 21 of 65 backdoors for 2% false alarms; at 9 we catch 58 of 65 but at 24% false alarms, which the budget cannot afford. A finer scale at the top may be worth more than either intervention tested here. We deliberately left the prompt untouched for this experiment

- **Write tests that are correct by construction.** The critique result suggests the problem is not *screening out* bad tests but *producing* good ones. Rules like "reordering the input must not change the answer" are reliable by their very form, and the AI already writes them unprompted

&nbsp;

# 9. Caveats

- **Every run uses the same 115 submissions.** So the spread between runs understates the true uncertainty. 10 runs makes the comparison decidable; it does not make the task set representative

- **Only the first backdoor per task is ever deployed.** About 15 tasks have a second one the simulation never draws. If first backdoors are systematically easier, safety carries a bias we have not measured. Checking this is free and has not been done

- **Input choice is shaped by this benchmark.** Do not assume these numbers transfer to other codebases

- **We could not control temperature.** Both providers reject the setting, so it sits at their defaults

- **The sandbox changed partway through, and we checked whether it mattered.** T-only and T-only+critique ran entirely under the original setup; U-plan and U-plan+critique switched to a stricter container at run 8. That makes two comparisons span the change, so we measured it directly. Between the first seven runs and the last three, scores drifted by **−4.1** and **−2.5** in the two conditions that *did not change*, versus **−0.9** and **−2.7** in the two that *did*. In other words, the conditions where nothing changed moved as much or more. The drift is ordinary run-to-run noise, and the +17.9 planning effect is about four times larger than the biggest drift

- **Why the sandbox changed.** The original setup limited how long submitted code could run but not how much memory it could use, and macOS cannot enforce a memory limit. One submission consumed roughly 120 GB on a 64 GB machine and crashed it three times. Running submissions inside a memory-capped container fixed it, after which the batch ran 7.5 hours without incident. Infrastructure-failure rate was zero across all four conditions, so none of this reached the numbers

&nbsp;

# 10. What would change our mind

- **For testing as a standalone check:** any condition above 60% of code review. Nothing came close, and even the non-deployable best case only reached 58.3%

- **For tests-as-evidence:** an effect this size would need roughly **4× the number of tasks** to reach significance. That is a different experiment, not a longer one

&nbsp;

# 11. Where everything lives

Every number here was read from the committed data files below, not from notes.

**Results, one file per condition.** Each holds the 10-run aggregate and the 10 individual runs behind it.

- [T-only: results](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/reports/artifacts/b1/b1-r1.metrics.json) · [configuration](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/reports/artifacts/b1/b1-r1.run.json)

- [T-only + critique: results](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/reports/artifacts/b1/b1-r5.metrics.json) · [configuration](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/reports/artifacts/b1/b1-r5.run.json)

- [U-plan: results](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/reports/artifacts/b1/b1-r3.metrics.json) · [configuration](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/reports/artifacts/b1/b1-r3.run.json)

- [U-plan + critique: results](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/reports/artifacts/b1/b1-r7.metrics.json) · [configuration](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/reports/artifacts/b1/b1-r7.run.json)

**The exact instructions given to the AIs**

- [Code review](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/prompts/trusted_monitor.txt) — unchanged from the AI-control paper this work builds on

- [PBT-informed review](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/prompts/informed_monitor.txt) — the same text plus the test results; its opening and its rating instruction are word-for-word identical to the above, so the only difference is the evidence

- [Writing the tests](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/prompts/property_gen.txt)

- [Planning the tests](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/prompts/property_plan.txt) — the powerful AI's step; prose only, never code

- [Writing tests from a plan](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/prompts/property_from_plan.txt)

- [The self-critique step](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/prompts/property_critique.txt) — the H1 intervention

- [Choosing test inputs](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/prompts/trigger_search.txt) — specification-only in every condition here

**The code**

- [The deployment simulation and all scoring](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/pipeline/metrics.py)

- [Test scoring and the reliability check](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/pipeline/pbt.py)

- [The sandbox that runs submitted code](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/pipeline/harness.py)

- [The four test-writing strategies](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/pipeline/authoring.py)

- [The figures — generated from the data files, not typed by hand](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/reports/figures/make_figures.py)

**Documents**

- [The pre-registration](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/reports/2026-08-09-factorial-batch.md), written before any run started. **Note:** it lists four hypotheses; this report answers H1 and H4, because H2 and H3 both concern the code-aware factor still in progress

- [Index of all experiments](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/reports/EXPERIMENTS.md)

- [Running log](https://github.com/rkj26/unit_testing_mvp/blob/b1-factorial-ablation/CHANGELOG.md), including the three machine crashes and the sandbox bug behind them

- [The repository](https://github.com/rkj26/unit_testing_mvp/tree/b1-factorial-ablation)
