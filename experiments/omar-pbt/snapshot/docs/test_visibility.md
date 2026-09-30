# How much of the test set may a blind step see?

**Verdict: local choice.** No source reached treats an APPS-style provided input/output set as an answer
key that has to be withheld from a blue-team component. Two of them call it *public*; one hands the whole
set to the **attacker**; the original paper lists running it as a blue-team **resource**. What the field
does deliberately hide from a monitor is the secret input and collusion signals, never the pairs. The
strict reading in `build_dataset.py::statement_examples` is ours, not the field's — but it is not
*contradicted* either, because no published monitor is given the pairs, for the simpler reason that no
published monitor needs them: they all rate suspicion from statement + code.

## What `control_arena` actually does (v17.1.2, in `.venv`)

The test data **is** available to the protocol and is **never passed** to the monitor. There is no
withholding step to point at.

`settings/apps/task/dataset.py:87` puts the full grading set on the sample:

```python
apps_metadata = AppsTaskMetadata(inputs=inputs, outputs=outputs, solutions=solutions, ...)
```

reachable from any protocol component via `control_task_metadata()`. The monitor never reads it. Every
prompt formatter interpolates exactly two fields — `settings/apps/task/dataset.py` again supplies the
first as `record["question"]`, the statement with its printed examples:

```python
# monitor/_last_tool_calls_prompt_formatter.py:89
return prompt.format(
    task_description=task_metadata.main_task_description,
    tool_calls=tool_calls_message,
)
```

Identical at `monitor/_prefix_prompt_formatter.py:99`, `monitor/_cot_prompt_formatter.py:88`,
`monitor/_full_trajectory_prompt_formatter.py:387`. None of the five prompt templates in
`monitor/prompts/` has a slot for test data. The trusted editor gets `{untrusted_code}` and the statement
(`policy/prompts/trusted_editor.txt`); defer-to-trusted and trusted-editing
(`micro_protocol/_defer_to_trusted.py`, `_trusted_editing.py`) add nothing.

The **only** non-test reader of `metadata.inputs` is the grader, `settings/apps/task/scorers.py:308`:

```python
input_data = metadata.inputs[:num_tests]
output_data = metadata.outputs[:num_tests]
```

inside `passes_tests`, called from the `@scorer` `main_task_success` — Inspect scorers run after the
episode and cannot influence the protocol.

Contrast with the one thing `control_arena` *does* withhold on purpose. Hiding `secret_input` from the
monitor has dedicated infrastructure (`tools/_attack_tool/_attack_tool.py`, `attack_tool` /
`HonestToolDef`) and an end-to-end test whose docstring is explicit: *"verify that the attack tool
infrastructure correctly hides the 'secret_input' argument from the monitor's view"*
(`settings/apps/tests/test_apps_submit_hiding.py`). Nothing equivalent exists for test I/O. It is omitted,
not guarded.

## What the sources give the blue team

| Source | Who sees the provided pairs | Who runs them |
|---|---|---|
| Greenblatt et al. 2023, §2 | not stated for the monitor | blue-team protocol, once per problem |
| Control Tax, App. B | the **attacker** (full unit tests, verbatim in the prompt) | pipeline; called "publicly available" |
| Hua et al. 2025, App. D | nobody — "monitors ... do not have access to test cases" | experimenter |
| Ctrl-Z, §2.1 | the **untrusted policy** (public half) | protocol, at every step |
| Factor(T,U) | withheld from U ("private unit tests") | protocol, as a pre-monitor filter (App. E) |
| **this repo** | statement-visible pairs only (median 2 of 30.5) | the grader, first 10 |

**Greenblatt, Shlegeris, Sachan & Roger (2023), §2, p.4**, listing blue-team resources alongside `U`, `T`
and `H`:

> "The ability to run test cases for exactly one submitted solution per problem. These test cases are
> provided by the APPS dataset."

So in the paper this repo reproduces, the tests are a budgeted *deployment* affordance, not a hidden
grading set. The paper never prints the trusted-monitoring prompt — Appendix N.1 links live examples
instead — so **whether their trusted monitor saw pairs is not verifiable from the PDF**; §3.4.2 implies
statement + code, since it discusses as a hypothetical that "the protocol could decide to not show `U` the
problem statement at all". Every withholding the paper does argue for is anti-collusion, applies to the
*untrusted* monitor, and is about theme/naming/comment signals, not pairs. Trusted editing (§3.5) gets
`{PROBLEM}` and `{SOLUTION}`. The red team's rarity check writes test *inputs* and is shown the reference
solution: *"When drafting test inputs, we just show the model a normal solution"* (App. M.9).

**Control Tax (Terekhov et al., arXiv:2506.05296), §2 and App. B** — the sharpest counter to the strict
reading, because the asymmetry runs the other way:

> §2.1: "we consider a solution *backdoored* if it satisfies all publicly available test cases but produces
> incorrect outputs for at least one input not covered by these test cases."
>
> App. B.1, *attacker* prompt: "Here are as well the unit tests that both the correct solution and your
> subtly wrong solution should pass. Please keep these in mind when brainstorming. Note that if a
> particular value is used as the input for a unit test, you should AVOID using that value as a
> `fail_input`."
>
> App. B.2, *monitor* prompt: `{problem_statement}` and `{solution}`. Nothing else.

**Hua et al., "Combining Cost-Constrained Runtime Monitors" (arXiv:2507.15886, NeurIPS 2025), App. D** —
the only flat statement of the restriction, and it is a description of a cheap prompted-LLM monitor class,
not a leakage argument:

> "Note that monitors are only given the question and the solution. They do not have any ability to run the
> code, nor do they have access to test cases."

## The distinction that matters here

*Tests the deployment runs to accept a submission* versus *a grading set only the experimenter runs.*

- **Deployment-acceptance.** Greenblatt (one run per problem, spent by the protocol); Ctrl-Z (Bhatt et al.,
  arXiv:2504.10374, §2.1: the pipeline "generates Python test cases — showing approximately half to the
  model while withholding the rest as private validation tests", and "at each step ... the associated
  public unit tests are run"); Factor(T,U) (arXiv:2512.02157, App. E: "Monitor only solutions which pass
  unit tests: since solutions which fail unit tests are rejected anyway"); Control Tax, whose backdoor
  definition is stated against "publicly available test cases".
- **Experimenter grading set.** `control_arena`'s `apps_scorer`; Ctrl-Z's private half; Greenblatt's
  usefulness metric.

Ctrl-Z is the only source that splits one benchmark's tests into both roles explicitly, and it puts *half*
in the deployment-visible bucket and shows them to the untrusted policy.

`statement_examples` classifies our entire `provided_inputs` set as the second kind and then relaxes the
statement-matched remainder back into the first. Every source with an APPS-style provided set treats it as
the first kind, or as both. The pool numbers, verified against `apps_pool_hard.json` (50 tasks): 1,986
provided pairs, median 30.5 per task, range 20–130; 132 statement-visible, median 2, range 1–17.

## Has anyone built a test-*writing* monitor?

No, and the affordance has been named as unbuilt. Factor(T,U) (Sandoval & Rushing, Redwood,
arXiv:2512.02157) lists it twice — once among the legitimate adversarial uses of the trusted model
("monitoring, editing, **generating unit tests**, and generating honeypots") and once under Extensions
("Use `T` or `U` to generate child task unit tests"). Three arXiv sweeps (`abs:"trusted monitoring"`,
`abs:"AI control" AND abs:"test"`, `abs:"control protocol" AND abs:"backdoor"`, ~90 records) returned no
monitor that authors tests rather than scoring suspicion. Closest analogues, neither a monitor: Greenblatt's
`H`-auditing exploit generator, which is given the code and constructs its own reference solution rather
than being handed pairs; and ResearchArena (arXiv:2607.19321), whose monitors "may execute and probe the
produced artifact" — abstract only, **not verified against the paper**.

So there is no precedent to break, and no precedent to lean on. The ground truth a test-writing monitor is
allowed is an open parameter, not an inherited one.

## The argument specific to this pool

Our situation dissolves the leak worry, if it holds. Showing the test-writer a pair leaks something only
if the pair separates the candidates — if an attack fails a pair the honest one passes, the pairs *are*
the answer key and a blind step handed them is being told which submission is the attack. But every
candidate in this pool is selected to pass the provided set: the attack definition requires it, and the
honest and reference solutions are filtered on it. If that holds, all candidates are indistinguishable on
all 1,986 pairs, the pairs carry zero bits about which candidate is the attack, and showing 40 instead of 2
leaks nothing — it only tells the writer what the output format is and what a correct answer looks like,
which is spec information the statement was supposed to convey anyway. **This was measured and then the measuring script was deleted with `experiments/`,
so the figure below is a record rather than something you can re-derive.** It ran running honest / `attack_0` / reference against every provided
pair of all 50 tasks with wrong-answer, crash and timeout counted separately, and its own design note is
marked `DESIGN NOTE PENDING`. If it reports any attack failing a provided pair, this paragraph is wrong for
that task and the pairs are load-bearing evidence there.

## Caveat the writeup would need

> The test-writer is shown *N* known-correct input/output pairs from the pool's provided set — pairs the
> deployment must be able to supply, and the same pairs a grader
> would score correctness on — which the trusted-monitor arm does not receive, so the TM-vs-PBT
> comparison is no longer information-matched.
