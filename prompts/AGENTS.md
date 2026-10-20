# `prompts/`

Every template is loaded by bare filename through `pipeline.prompts.render(name, **kw)`. Eighteen
`.txt` files, and every one of them is reached by a protocol.

## `render` fills a template in one pass

It collects the placeholders first, raises `ValueError` if any has no value supplied or an empty one,
then substitutes them all in a single `re.sub`. Two real defects made that necessary:

- A template that kept a literal `{code}` because nobody passed it returned a completion that looked
  like every other completion, so **a prompt we never asked was recorded as an answer we did.**
- Substituting key by key let a value filled in early have its own `{code}` expanded by a later key,
  **splicing the candidate's source into the specification.**

The placeholder pattern is a lowercase identifier, so the literal `{0,1,2,3}` brace sets the
trigger-search prompts use to name a value range are left alone. Keep new placeholders lowercase and
keep brace sets out of any name that could read as one.

## Which templates are live

Three protocols render a template. Each one is chosen by an argument, never by a file name:

| template | rendered by | selected by |
|---|---|---|
| `trusted_monitor.txt` | `TM`, as `tm.TEMPLATE` | nothing — TM has one prompt |
| `audit_inputs.txt` | `TriggerSearch.prompt` | `code_visible=True`, the default |
| `audit_inputs_speconly.txt` | `TriggerSearch.prompt` | `code_visible=False` |
| `audit_tests.txt` | `UnitTesting`, via `prompts.build_prompt` | `code_visible=True`, the default |
| `audit_tests_speconly.txt` | `UnitTesting`, via `prompts.build_prompt` | `code_visible=False` |

The four `audit_*` names are the values of `PROMPT_BY_STAGE_AND_VISIBILITY`: `TriggerSearch` takes the
`inputs` row and `UnitTesting` the `tests` row. `TriggerSearch.__init__` raises `TypeError` on a
`prompt_file=` argument, because `Run` writes every constructor argument into `config.json` and a
name nothing acts on would be read back later as the template that arm ran under.

The rest are fragments — a file that fills a slot in one of those five:

| fragment | slot | in | selected by |
|---|---|---|---|
| `framing_property.txt`, `framing_plain.txt`, `framing_plain_v2.txt` | `{framing_rule}` | `audit_tests*.txt` | `UnitTesting(test_gen_prompt=…)`, by key or by file name; default `property` |
| `resolve_without.txt`, `resolve_with.txt` | `{resolve_rule}` | `audit_tests*.txt` | `UnitTesting(resolve=…)`; default `without` |
| `example_<template stem>_<io_mode>.txt`, eight of them | `{worked_example}` | all four `audit_*` | `worked_example_file(template, io_mode)` — the dataset's mode, not a knob |

Only `audit_tests.txt` and `audit_tests_speconly.txt` carry `{framing_rule}` and `{resolve_rule}`; the
inputs templates have no such slot, which is why a framing is a `UnitTesting` argument and there is no
`TriggerSearch` equivalent.

`resolve_rule_file` also accepts `forbidden` and `allowed`, the old spellings of `without` and `with`,
so a run recorded under them re-renders exactly. `bounded` was deleted, and a run made under it cannot
be re-rendered at all.

A fragment is loaded through `render` rather than a bare read, so a fragment that grows a placeholder
of its own fails at load instead of shipping a literal `{...}` inside a rendered prompt.

A new template needs a worked example for **both** io_modes, because a stdio example shown to a task
whose candidates take keyword arguments teaches the wrong invoke contract. Ship only one and the first
call raises: `TriggerSearch.prepare` on the missing file, before any candidate; `build_prompt` at
`render`, which supplies `worked_example` only when the file exists and so trips the
no-value-supplied check.

## Changing a live template changes the arm

A prompt edit is a change to the experiment, not a fix. It gets a new `run_name` rather than a rerun
under the old one, and the prediction goes in the markdown cell above the cell that reads it, written
before that cell runs.

Old runs are untouched by the edit: `calls[].prompt` holds the prompt **as sent**, so nothing
re-renders an artifact. That field exists because `audit.prompt` used to re-render from the recorded
flags, which held only until a template was edited — and it had already diverged once.
