# `pipeline/` — the shared library

Seven modules, and one entry point. `pipeline.protocols.base.main` is it:

```
.venv/bin/python -m pipeline.protocols.base runs/<run_name>/config.json
```

One `config.json` in, one run directory out. The subprocess looks the config's `protocol` field up
in `REGISTRY` and rebuilds the class, so a run is re-derivable from its own directory and nothing
outside it has to remember what an arm meant. Nothing else here has a `__main__`.

| module | what it is for |
|---|---|
| `data.py` | `Dataset`, `Task`, `Candidate`, `task.blind()`, `Blame`, `load_records` |
| `model.py` | the inspect client, the reasoning and timeout ladders, and `complete_sync` — **read that one first** |
| `sandbox.py` | **the only place candidate code runs** |
| `launch.py` | start a run detached in tmux and prove it started |
| `prompts.py` | every prompt template, and the one renderer that fills them |
| `parse.py` | one completion into the two things a protocol can run: test source, trigger inputs |
| `protocols/` | `Run`, the four protocols, `main`. Its own `AGENTS.md` is the rulebook for adding one |

---

## `model.py` — `complete_sync` is the only bridge to the loop

`Run.execute` scores candidates in a `ThreadPoolExecutor`; `TrustedModel.completion` is a coroutine.
`complete_sync(model, prompt, kind, schema=None)` is the **one** place those two meet, and `tm.py`,
`trigger_search.py` and `unit_testing.py` all call it rather than bridging themselves.

```python
loop    = shared_loop()                       # one asyncio loop per process, on a daemon thread
pending = asyncio.run_coroutine_threadsafe(_survivable(call), loop)
return pending.result(timeout=model.runtime.http_timeout + BRIDGE_MARGIN_SECONDS)
```

Three separate bridges existed once and one of them called `asyncio.run` per call. That cannot work:
`get_model` memoises one inspect `Model` per (name, config), and both the provider's httpx pool and
inspect's own semaphores bind to the loop that first awaited them, so the second call runs against
state the first loop closed. `shared_loop` is process-wide, not per-run, because the memoised model
is process-wide too.

The two guards are the part that is easy to drop in a rewrite:

- **`_survivable` converts a `BaseException` into `ModelCallFailed`.** A `KeyboardInterrupt` or
  `SystemExit` raised inside a coroutine is re-raised by `Task.__step` instead of being stored on the
  future, so it propagates into `run_forever` and ends the loop thread. Every later
  `run_coroutine_threadsafe` then schedules onto a loop nobody is running — eight worker threads all
  parked in `.result()`, which is how this deadlocked the whole suite for five minutes at 1% CPU.
- **`.result()` is bounded.** Even with the loop protected, a future that never completes must fail
  rather than park a worker forever. The bound is the runtime's own http budget plus a margin, so it
  can only fire after every retry the call was entitled to.

There is deliberately no `except` around the result. A call that never returned is infra, and
`Run._record_for` states that blame where it catches the exception; a second policy here is the copy
that drifts from it.

## The timeout ladder is derived, never passed in

Every bound follows from the per-call attempt for that reasoning effort, so a run cannot end up with
a retry budget shorter than the call it is retrying — which is what the old pipeline had, passing one
measured call budget as both the attempt and the HTTP bound. A protocol that wants a different budget
raises the reasoning effort; it does not hand `ModelRuntime` a timeout of its own.

Two rungs exist for reasons that are not obvious. The **per-call** bound is what catches a dead
socket: chat completions here are non-streaming REST, so a hung connection sends no bytes at all
while the model is generating and looks identical to a slow answer. The **unit** bound stops one
pathological task taking the whole run down with it.

## `sandbox.py` — the only place candidate code runs

```python
run_raw(task, code, props_src, space, timeout_s=..., isolation=Isolation.SUBPROCESS, docker_image=...)
```

Runs every property over every input against one implementation and returns `records`, one
`{prop, i, outcome}` per pair. It is a port, not a rewrite, because its corrections are invisible on
the page and both were bugs once:

- **The Docker path kills a process GROUP.** On the hard-kill path `run_raw` calls `_docker_kill` and
  then `kill_group`, which is `os.killpg(os.getpgid(proc.pid), SIGKILL)` against the session
  `start_new_session=True` opened. Signalling the child alone leaves orphans running candidate code.
- **`complete` is counted by the parent**, as `len({(r["prop"], r["i"]) for r in records})` against
  `len(props) * len(space)` — distinct pairs, never a flag the candidate could have written into the
  result file. A missing pair can only lose a catch, never invent one, so an incomplete run
  under-reports and must not be read as a clean negative.

`ok` is the weaker claim: a usable header and at least one well-formed record. `_validated`
re-derives props and records from the result file and raises on anything off-contract, because the
file is attacker-reachable — the candidate runs in that process and knows the path.

`Isolation.SUBPROCESS` is the default because the mock path runs under it, and it is a timeout and
process-group boundary only. `UnitTesting` runs `Isolation.DOCKER`.

## `prompts.py` — `render` fills in one pass or raises

`render(name, **kw)` reads `prompts/<name>`, and raises on a placeholder with no value and on a
value that is empty. Two real defects made that necessary. A template that kept a literal `{code}`
returned a completion indistinguishable from any other, so *a prompt we never asked was recorded as
an answer we did*; and substituting key by key let an early value's own `{code}` be expanded by a
later key, splicing the candidate's source into the specification. The placeholder pattern is a
lowercase identifier, so the literal `{0,1,2,3}` brace sets in the trigger-search prompts survive.

Everything above `build_prompt` is tables, not branches: which template a stage and a code visibility
select, which fragment a framing names, which invoke contract an `io_mode` gets. Changing one of them
changes the experiment, not the code.

## `parse.py` — which block gets read, and `dropped` is a count

`parse_search_space` reads the **longest** fenced block. A model that also wrote tests it was not
asked for would otherwise have them read as the search space, so a caller must cut the python block
out first — `prompts.input_section` is that cut, and dropping it silently swaps tests in for inputs.

A fence's language tag is matched as **one word terminated by a line break**, never as "everything up
to the first newline". A model that opens a fence and starts code on the same line would otherwise
lose that line silently; a multi-word info string is left in the block instead, where it fails loudly
as a `SyntaxError`.

### `dropped` is a count, not a flag

`parse_search_space(completion) -> (space, error, dropped)`, with three cases in the third slot:

| | |
|---|---|
| `0` | everything the model wrote was read |
| `n` | `n` inputs were lost, one per line, and the suite searched a smaller space than it was asked for |
| `None` | inputs were lost and **how many is not recoverable** — a truncated JSON array is salvaged to its leading complete elements, and nothing in the fragment says how many were intended |

A shortened space is not an error, since it still runs, but it is the ceiling on everything
downstream, so the magnitude travels with the space. `read_input_lines` is the single place a line
becomes a value, and the dropped-input diagnostic reads the same list the parse did, so an
explanation cannot disagree with the parse it is explaining. `parse_properties` rejects async
properties: the harness calls each property synchronously, so a coroutine function returns an
unawaited coroutine, raises nothing, and records a pass without running its body.

## Show a model its input in the notation you are asking it to write

`json.dumps`, never `repr`. A prompt that demands a double-quoted JSON string per line while
illustrating it with a single-quoted Python repr is how a model writes something that looks right and
parses to nothing — and under `function` io_mode a repr of a kwargs dict is not even valid JSON.

## `data.py` — `blind()`, and a record that is never silently dropped

`task.blind()` returns exactly `main_task`, `provided_tests`, `io_mode`, `entry_point`. Never
`reference_solution`, never a `secret_input`, never the full provided set. A protocol builds every
prompt from `**task.blind()`, so widening what a blind step sees is one edit here and one line in
review.

`Blame` is a `str, Enum` with `MODEL` and `INFRA`, and a record carries the plain string. The two are
not interchangeable: `model` is data about the thing being measured, `infra` is noise we should
retry, and pooling them books our own flakiness as the protocol's failure rate.

`load_records(run_name)` tolerates a truncated final line — that is what a process killed mid-write
leaves — and recognises it by the missing final newline rather than by the parse failing. A
malformed line anywhere else raises, because skipping one drops a candidate from a denominator
without saying so. A directory holding no `config.json` raises rather than returning `[]`, which
would read as a finished run that scored nothing.

## `launch.py`

```
launch(run_id, argv)   # detached tmux session named after the run id
alive(run_id) · pane(run_id) · kill(run_id) · console_log(run_id) · sessions()
```

A launch that failed must never read as a launch that succeeded. `launch` waits
`SESSION_LIVENESS_GRACE_SECONDS` for the session to prove it is alive and raises `LaunchFailed` with
the tail of `runs/<run_id>/console.log`, so a mistyped flag surfaces at launch rather than as an
empty `runs/` in the morning. That log exists to explain a failed launch; it is never where a result
is read from.

It also refuses a `run_id` whose session already exists. Two processes writing one run directory
corrupt it, and the subprocess resumes from `records.jsonl` anyway, so the fix is to attach to the
running session rather than start a second one beside it.

A launch whose tmux session is already gone is forgiven **only when every candidate has a record**: a
resumed run with two candidates left legitimately finishes inside the liveness grace, and the artifact
is what says so. Any other vanished session is a `LaunchFailed`.
