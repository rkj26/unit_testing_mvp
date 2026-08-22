# `pipeline/protocols/` — adding a protocol

One protocol, one run, one artifact. A protocol is anything that turns a candidate into a verdict by
calling a model; everything else is a notebook cell. `base.py` is the spine and the only thing that
touches tmux, threads, `records.jsonl` or the failure policy. A subclass is two methods and one
attribute, and every rule below is a defect that reached a number before it was a rule.

```python
class TM(Run):
    protocol = "tm"

    def prepare(self, data): ...
    def score(self, task, candidate) -> dict: ...
```

## Two methods, and nothing else is yours

`prepare` resolves what the run needs once; `score` returns one candidate's verdict as a dict of
protocol-specific fields plus `calls`. The base wraps that in the identity fields, the failure
triple and the file. **If you are opening a file, spawning a thread, or writing a `try/except`
around your own model call, the base already did it** — and the two copies drift the way the five
`experiments/` scripts drifted, each re-deriving a rate the others already had.

Repetition is yours, because collapsing reps into one record is protocol-specific: `self.seeds`
holds one seed per rep, and TM's mean is not TriggerSearch's concatenation. One record per candidate
either way.

## A protocol module `__init__.py` does not import does not exist

`REGISTRY` is filled by `Run.__init_subclass__` and by nothing else, so a module nobody imports
never registers. `base.main` resolves the class from the `protocol` name in `config.json` alone, and
that lookup happens in a fresh interpreter that has imported the package and not your module.

This shipped. `__init__.py` imported only `.base`, so `REGISTRY` held `echo` alone. Every in-process
check passed — the checker had imported the protocol by hand — and every real `.run()` died inside
the launch grace with `KeyError: no protocol registered as 'tm'`. The imports in `__init__.py` are
registration, not convenience re-exports: deleting one as an unused name takes its protocol out of
every subprocess and out of `Run.attach`.

```
.venv/bin/python -c "import pipeline.protocols as p; print(sorted(p.REGISTRY))"
['echo', 'tm', 'trigger_search', 'unit_testing']
```

## `run_raw` fires on `outcome == "catch"`, never `"fail"`

`pipeline.sandbox.run_raw` returns one `{prop, i, outcome}` per pair, and `RECORD_OUTCOMES` is
`("pass", "catch", "candidate_crash", "prop_error")`. There is no `"fail"`. Filtering for one scores
every suite as clean and reports a protocol that catches nothing — this has already cost a result.
`candidate_crash` is the submission raising, which is not an exploit; `prop_error` is the test
raising, which is evidence about the test. Neither is a catch.

## An incomplete grid under-reports; it is never a clean negative

`complete` on the sandbox result means the whole grid ran, counted by the parent as distinct pairs
rather than read off a flag the candidate could have written. A missing pair can only *lose* a
catch, never invent one. So a partial grid that fired is still a verdict, and `complete=False` with
no catches is a measurement that did not finish — recorded as such, not as a suite that found
nothing.

`complete` does not cover every empty grid. `prop_error` records count towards `n_records`, and a
suite the harness found no callable test in has `n_expected == 0`, so `0 >= 0` reads complete. Both
arrive as `ok`, `complete`, `catches=[]` — byte-identical to the finding the protocol exists to
make. `unit_testing.no_evidence` is what separates them, and they are `failed` too.

## A test written against the wrong invoke contract reports nothing, not a failure

A stdio contract shown to a task whose candidates take keyword arguments describes a `run` that does
not exist, so every test written against it **raises instead of asserting** — and a test that raises
reports nothing at all, which reads afterwards as a suite that found nothing. Same shape as the
`"catch"`/`"fail"` and `complete=False` traps above: the failure direction is always "the protocol
found nothing", never "the protocol is broken". `prompts.invoke_contract` and `worked_example_file`
both take the task's `io_mode` for this reason.

## `failed` leaves the denominator; it is never a zero

Return the failure triple from `score` when the measurement did not happen: `failed=True` with a
`blame` of `"model"` (nothing parseable came back — data *about* the thing being measured) or
`"infra"` (a dead socket — noise we should retry). Pooling the two books our flakiness as the
protocol's failure rate. State blame **where the failure is detected**, never inferred later from
the text of an exception. Raising out of `score` is for a bug in the protocol itself, and the base
records exactly that: `blame="infra"`, with the traceback in `console.log`.

Never a falsy value standing in for a missing one, and `None` rather than `[]` for a field nothing
measured. The deployment cells used to score an abstention `0.0`, the most innocent value on the
scale, which is how *"the monitor never answered"* came to be read as *"the monitor cleared it"*;
and an empty `fired` on a suite that was never written is indistinguishable from a suite that ran
and found nothing.

## `runs > 1` forces the cache off, and only the seed varies

The inspect cache key includes the seed. Constructing with `runs > 1` resolves `cache` to `False`
and writes that resolved choice into `config.json`; asking for `runs > 1, cache=True` raises rather
than being quietly downgraded. Six arms' TM scores came back byte-identical for this reason and were
read as six measurements agreeing.

Temperature is a no-op on the provider we use — `model.TEMPERATURE_REJECTING_PREFIXES` contains
`deepseek-v3.2`, so it never reaches the API and the seed is the only thing separating one
repetition from the next. Build one client per seed in `prepare`, since the seed is fixed into the
`GenerateConfig` when the client resolves and one shared client sends every rep at the same seed.
**Assert the repetitions actually differ before trusting an average.**

## `task.blind()` is what a prompt may see

Exactly four keys, under the templates' names: `main_task`, `provided_tests` (the statement-printed
examples, already rendered), `io_mode`, `entry_point`. Never `reference_solution`, never a
`secret_input`, never the full provided set — those are the answer key and they reach the sandbox
and the measurement cells only. Build every prompt from `task.blind()`. Reaching for
`task.reference_solution` while building a prompt is the exact bug this API exists to make visible
in review, as one line; widening what a blind step sees is one edit in `data.py`, also as one line.

## A protocol that reads another run resolves it in `prepare`, and raises there

`UnitTesting` reads a trigger run. Load it in `prepare` and raise there if a candidate is missing —
not halfway through the loop, with half an artifact on disk and no way to tell a run that was killed
from a run that was never going to finish. `unit_testing.spaces_from` names which of the three ways
each gap happened: no record, a record that failed, or a record that reached a verdict and parsed no
inputs. An empty space counts as missing, because a suite run over zero inputs comes back complete
with no catches.

Credentials belong in the same place, and for the same reason: `prepare` calls `model.resolve` so a
missing `AZUREAI_API_KEY` stops the run before it writes anything, instead of arriving as one
identical infra record per candidate in the dataset.

## The answer shape is whatever the prompt's contract promised, and they must match

The single most expensive defect this port produced. `prompts.OUTPUT_SPLIT_TESTS` promises the model
*"a single JSON object matching the schema you have been given"* and forbids fences, so a tests call
sent **without** a `response_format` schema asks for a shape nothing enforces. Worse in the other
direction: reading that JSON answer with `parse.parse_properties` finds no fence, falls back to bare
text on the strength of a `def ` inside a JSON string, compiles a dict expression defining zero
functions, and recovers **0 of the 566 real answers** under `runs/m-*`. Every candidate came back
`failed` with `blame="model"` — our own prompt/parser mismatch booked as a 100% trusted-model failure
rate, with catch and FPR at n=0.

Whenever you change a prompt's output contract, render it and feed a real answer of that shape to the
parser that will read it. A suite of tests that hands canned completions straight to the parser
cannot see this, and did not.

## Store the prompt as sent, never re-render it later

Three protocols arrived at this independently. A record keeps the prompt string it actually sent,
alongside the `seed` that produced it. The alternative — reconstructing it afterwards from the flags
a run recorded — held only until a template was edited, and `audit.prompt` diverged the first time
one was.

## `runs > 1` is not available to every protocol

For a scorer it means repetitions to average. For a protocol whose record holds **one artifact** —
a suite, a search space — there is no honest way to collapse two into it: a union of two suites'
catches raises the false-alarm rate as much as the catch rate, and taking the first silently discards
a call you paid for. `UnitTesting` refuses `runs > 1` outright. Repeating that arm is a second run
with its own name.

## A resumed run repairs the tail before it appends

`load_records` forgives an unterminated final line, which is what a process killed mid-write leaves.
That forgiveness expires the moment a resumed run appends: the fragment stops being the last line,
and the whole artifact then raises. `execute` truncates back to the last complete record first.

## A rebound `protocol` name raises rather than letting the later import win

Every run directory written under the old class would silently `attach` as the new one, and
`records.jsonl` records only the name — nothing in the artifact could tell you which class produced
it.

## What the base guarantees, so you do not re-check it

- `config.json` holds the protocol name, the dataset path and every constructor argument, so a run
  is re-derivable from its own directory. `Run.attach(run_name)` is the whole of what the deleted
  arm registry used to do. A knob that does not round-trip through JSON is refused at construction,
  not in the subprocess after the session is up.
- A **different** config under a used run name raises. Resuming rewrites the same document and is a
  no-op; a second experiment wearing a used name would append its records to the first's and pool
  two populations into every rate computed off the file.
- Resume is by candidate id out of `records.jsonl`, in dataset order — train before test, honest
  before attack. A killed run costs at most the calls that were in flight, and a record cut off
  mid-write is dropped rather than glued to the next one.
- Every record carries its `split`, because a protocol covering only test leaves nothing for a later
  one to fit a threshold on and the split cannot be recovered after the fact.
- `score` may not return any of `run_name`, `protocol`, `split`, `task_id`, `candidate_id`, `label`
  or `is_attack`; a protocol that restates identity is a protocol that can contradict it. Omitting
  `calls` raises too — a protocol that calls no model records `[]`, so a prompt that was lost cannot
  pass for a protocol that never asked.
- Candidates are scored on eight worker threads, and `model.complete_sync` is the one bridge from a
  worker to the shared event loop. Do not open a second one.

## The spine's own protocol

`Echo` calls no model and scores a constant. It exists to exercise the machinery without spending
money — config, tmux, subprocess, registry lookup, appended records — and `seconds_per_candidate`
buys a window wide enough to kill a run in and watch the next one append rather than start over.
Nothing in `tests/test_end_to_end.py` covers it; the resume path is checked by hand.

```
.venv/bin/python -c "from pipeline.protocols import Echo; \
  Echo(run_name='echo-spine', data='data/apps_hard.json', seconds_per_candidate=0.2).run()"
```
