# How we work

Ground rules for this project, agreed 2026-08-07. Amended 2026-08-09 (batch runs).
Both of us are bound by them.

## Who does what

1. **Experiments run in approved batches.** You approve a batch; Claude launches it and monitors
   it. Claude never launches a run outside an approved batch. This replaces the original rule that
   Claude never launches anything — that rule made your attention the bottleneck on every run.
2. **Confirm before acting.** Nothing is written, moved, or deleted without an explicit go-ahead.
   A batch approval is the go-ahead for every run in that batch, and for nothing else.

## Batch runs

The point is that you spend your attention on results, not on starting things.

3. **Assemble 4–5 independent questions.** Independent means each is worth answering whatever the
   others return. A batch is not the next five steps of one investigation; if a line is genuinely
   sequential, the batch takes one step of it and fills the rest with unrelated work.
4. **Every entry pre-registered before the batch launches.** Rule 15 applies per experiment, so
   the whole batch is written up — question, hypothesis, kill criterion, primary metric — before
   the first command runs. You approve the written batch, not a verbal description of it.
5. **You approve once, then leave.** Claude launches, monitors, and writes each run's numbers into
   section 5 of its report as it lands.
6. **Claude does not interpret while you are away.** Sections 6–8 stay empty until we read them
   together. Numbers get recorded; verdicts do not get assigned alone.
7. **On failure, repair infrastructure and resume; never adjust the experiment.** A crash blamed
   `INFRA` may be fixed and the run resumed with `--run-id`. Anything that would change what the
   experiment measures — config, prompt, task pool, threshold — stops that run and waits for you.
   Claude reports what it repaired.
8. **No new experiments mid-batch.** An interesting interim result is a candidate for the *next*
   batch, written down as such. It does not get launched.

## Reading code

9. **Sequential, one unit at a time.** Print the real source, explain it in plain English, stop, ask. Never summarise code that has not been shown.
10. **No assertions about unshown code.** If Claude says "this does X", the lines are on screen.
11. **Docs are claims, not facts.** `README.md`, `CLAUDE.md`, `METRICS.md`, `CHANGELOG.md` were all written at some point and may be stale. Verify against source.

## Writing code

12. **Stages, with plain data files between them.** Metrics must be re-runnable with zero model calls.
13. **Names carry the meaning.** A function that needs a comment to be understood is badly named or badly decomposed.
14. **New code is read like old code.** No 400-line handovers.

## Reporting

15. **Pre-register.** Hypothesis, setup and metrics are written *before* the run. See `reports/TEMPLATE.md`.
16. **One primary metric per experiment.** Everything else is descriptive.
17. **Every number traceable** to an artifact path that can be opened.
18. **Dead hypotheses are reported as dead.** The question does not get rewritten to match the answer.

## Disagreement

19. **Claims are labelled:** *verified* (read it), *inferred* (follows from what was read), *guessed* (neither). "I don't know" is an acceptable answer.
20. **Disagree once, plainly, with reasoning — then commit.** If you reaffirm, Claude executes it properly rather than grudgingly.

## Momentum

21. **Default to the smallest experiment that could change our minds.** Planning is the shared failure mode; the report format exists to force a number out the other end.

## Shorthand during code walks

| you type | means |
|---|---|
| `next` | understood, move on |
| `why` | dig into this |
| `wrong` | your explanation does not match what I am reading |
| `cut` | this should not exist |
