# `prompts/`

Every template is loaded by bare filename through `pipeline.pbt.render(name, **kw)`.

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

Reached from `probe.py` or `audit.py`:

| template | reached by |
|---|---|
| `audit_tests.txt` | `probe.build_prompt`, `--code visible` (the default) |
| `audit_tests_speconly.txt` | `probe.build_prompt`, `--code hidden` |
| `trusted_monitor.txt` | `monitor.tm_prompt`, from both `probe.py` and `audit.py` |

Everything else is a remnant of the deleted orchestrator. Its renderer still exists and still passes
its tests, so editing one of these changes nothing that any run reads:

| template | renderer | callers |
|---|---|---|
| `property_gen.txt`, `property_gen_precision.txt`, `property_gen_code.txt` | `pbt.property_prompt` | `tests/test_parsers.py` only |
| `trigger_search.txt`, `trigger_search_dense.txt`, `trigger_search_code.txt` | `pbt.search_prompt` | `tests/test_parsers.py` only |
| `informed_monitor.txt` | `monitor.informed_prompt` | `tests/test_parsers.py` only |
| `property_critique.txt` | `pbt.critique_prompt` | none |
| `property_plan.txt` | `pbt.plan_prompt` | none |
| `property_from_plan.txt` | `pbt.write_from_plan_prompt` | none |

`Settings.property_prompt` and `Settings.search_prompt` still validate their variant names against
`pbt.PROPERTY_VARIANTS` and `pbt.SEARCH_VARIANTS`, so the flags parse. Nothing live consumes them.

## Changing a live template changes the arm

A prompt edit is a change to the experiment, not a fix. It gets an entry in `reports/EXPERIMENTS.md`
with the old and new run ids, the same as any other one-variable change.
