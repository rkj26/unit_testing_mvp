# The shared spine

`pipeline/protocols/base.py` answers one question for every protocol at once: *how does a class
statement in a notebook become a directory full of records that outlives the notebook?* `Run` owns
serialisation, tmux, the eight worker threads, the resume and the failure triple; a subclass owns
`prepare` and `score` and nothing else. The four protocol pages that follow this one describe only
what happens inside their `score()` — everything around it is on this page.

## At a glance

| | |
|---|---|
| **reads** | `runs/<run_name>/config.json` (in the subprocess), `runs/<run_name>/records.jsonl` (to resume), and the dataset file the config names |
| **model calls** | none. `Run` never calls a model — `prepare` and `score` on the subclass do, and `model.complete_sync` (`model.py:244`) is the only bridge they may use |
| **writes** | `runs/<run_name>/config.json`, `runs/<run_name>/records.jsonl` (one line per candidate, flushed on arrival), `runs/<run_name>/console.log` (teed by `launch.py:89`) |
| **unit scored** | one `(task, candidate)` pair from `Dataset.candidates()` (`data.py:375`) — honest before attack, train before test |
| **prompt templates** | none |
| **parser** | none; `json.loads`/`json.dumps` for the two artifacts, and `data.load_records` (`data.py:385`) to read the second one back |
| **sandbox** | no. `base.py` imports `launch` and `data` and nothing else from `pipeline` |

`Echo` (`base.py:527`) is the spine's own protocol: no model, no sandbox, one constant per candidate,
`seconds_per_candidate` wide enough to kill a run in and watch the next one resume. Nothing in
`tests/test_end_to_end.py` covers it; the resume path is checked by hand.

## The call flow

### The process-level lifecycle

Two processes that share nothing but a directory. The left column is your kernel; the right column
is a fresh interpreter that has never seen the object you constructed.

```{mermaid}
flowchart TB
  subgraph caller["your process: notebook cell, shell, agent"]
    ctor["Run.__init__<br/>base.py:157"]
    dspath["_dataset_and_path<br/>refuses an in-memory Dataset<br/>base.py:91"]
    rcache["_resolved_cache<br/>runs&gt;1 forces False; runs&gt;1 with cache=True raises<br/>base.py:74"]
    serial["_serialisable<br/>json.dumps or TypeError<br/>base.py:104"]
    seeds["self.seeds = seed+0 .. seed+runs-1<br/>base.py:185"]
    dorun["run(wait=True)<br/>base.py:301"]
    wcfg["write_config<br/>refuses a used name holding a DIFFERENT document<br/>base.py:225"]
    pend1["pending()<br/>base.py:310"]
    q1{"nothing pending?"}
    noop["print N/N already scored, return<br/>base.py:312"]
    lch["launch.launch(run_name, argv, cwd)<br/>launch.py:65"]
    q2{"LaunchFailed raised?"}
    pend2["pending() re-read from disk<br/>base.py:328"]
    q3{"still pending?"}
    reraise["re-raise LaunchFailed<br/>base.py:329"]
    forgiven["print scored inside the launch grace, return<br/>base.py:330"]
    follow["_follow()<br/>base.py:340"]
    stat["status(): launch.alive FIRST, then load_records<br/>base.py:283"]
    q4{"scored &gt;= total?"}
    q5{"session alive?"}
    runfailed["raise RunFailed with _console_tail(2000 chars)<br/>base.py:351"]
    detach["KeyboardInterrupt: print the detach hint and return<br/>base.py:356"]
    finished["return"]
  end

  subgraph shared["runs/&lt;run_name&gt;/ — the only thing the two processes share"]
    cfgfile["config.json"]
    recfile["records.jsonl"]
    logfile["console.log"]
  end

  subgraph child["tmux session named &lt;run_name&gt;"]
    q0{"launch.alive(run_name) already?"}
    refuse["LaunchFailed: attach or kill it<br/>launch.py:81"]
    newsess["tmux new-session -d -s run_name -c cwd<br/>launch.py:92"]
    q6{"tmux exit code?"}
    refused["LaunchFailed: tmux refused to start, carrying its stderr<br/>launch.py:97"]
    grace["sleep 3.0s then launch.alive again<br/>launch.py:98"]
    died["LaunchFailed with _failure_excerpt(console.log)<br/>launch.py:100"]
    proc["env PYTHONPATH=REPO_ROOT python -m pipeline.protocols.base config.json<br/>stdout and stderr teed to console.log<br/>base.py:315"]
    dunder["base.py executed as __main__<br/>base.py:579"]
    twocopies["this copy has its OWN Run class and its OWN REGISTRY,<br/>holding echo alone"]
    entry["_entry_point_in_the_imported_module(sys.argv)<br/>base.py:568"]
    mainf["main(argv[1]) imported from pipeline.protocols.base<br/>base.py:545"]
    denv["load_dotenv(REPO_ROOT/.env)<br/>tmux inherits the server env, not your shell's<br/>base.py:558"]
    imp["importlib.import_module(pipeline.protocols)<br/>every module it imports registers via __init_subclass__<br/>base.py:559"]
    fromcfg["Run.from_config(document)<br/>KeyError if REGISTRY has no such protocol<br/>base.py:247"]
    exec1["execute() — see the second diagram<br/>base.py:369"]
    zero["print wrote N record(s), return 0<br/>base.py:564"]
  end

  ctor --> dspath --> rcache --> serial --> seeds
  seeds --> dorun --> wcfg --> pend1 --> q1
  wcfg -->|writes| cfgfile
  recfile -.->|read| pend1
  q1 -->|yes| noop
  q1 -->|no| lch
  lch --> q0
  q0 -->|yes| refuse
  q0 -->|no| newsess --> q6
  q6 -->|"non-zero"| refused
  q6 -->|"zero"| proc
  proc -->|tee| logfile
  q6 -->|"zero"| grace
  grace -->|"session gone"| died
  refuse --> q2
  refused --> q2
  died --> q2
  grace -->|"alive"| follow
  q2 -->|yes| pend2 --> q3
  q3 -->|yes| reraise
  q3 -->|no| forgiven
  follow --> stat --> q4
  recfile -.->|read| stat
  q4 -->|yes| finished
  q4 -->|no| q5
  q5 -->|yes| follow
  q5 -->|no| runfailed
  follow -.->|"Ctrl-C"| detach

  proc --> dunder --> entry --> mainf
  dunder -.-> twocopies
  mainf --> denv --> imp --> fromcfg --> exec1 --> zero
  cfgfile -.->|read| fromcfg
  exec1 -->|"append + flush per line"| recfile
```

### `execute()` for one candidate

Everything below `pool.submit` runs on one of eight worker threads. Everything above it runs on the
thread that called `execute`, which is the subprocess's main thread.

```{mermaid}
flowchart TB
  e0["execute()<br/>base.py:369"]
  e1["_repair_truncated_tail(records_path)<br/>drop a final line with no newline<br/>base.py:116"]
  e2["self.prepare(self.data)<br/>subclass: credentials, upstream runs, one client per seed<br/>base.py:376"]
  e3["remaining = pending()<br/>base.py:377"]
  e4["open records.jsonl in append mode<br/>base.py:387"]
  e5["ThreadPoolExecutor(max_workers=WORKERS=8)<br/>base.py:388"]
  e6["pool.submit(_record_for, task, candidate) for every remaining pair<br/>base.py:389"]
  e7["as_completed(scoring)<br/>base.py:394"]

  subgraph worker["one worker thread, one candidate"]
    w0["_record_for(task, candidate)<br/>base.py:412"]
    w1["try: self.score(task, candidate)<br/>subclass; contract at base.py:515"]
    w2["model.complete_sync(model, prompt, kind, schema)<br/>model.py:244"]
    w3["shared_loop(): one asyncio loop per PROCESS on a daemon thread<br/>model.py:212"]
    w4{"loop.is_running()?"}
    w5["raise ModelCallFailed: restart the process<br/>model.py:255"]
    w6["run_coroutine_threadsafe(_survivable(call), loop)<br/>BaseException becomes ModelCallFailed<br/>model.py:230, 261"]
    w7["future.result(timeout = http_timeout + 60s)<br/>model.py:262"]
    w8["Completion returns to score()"]
    w9{"did score() raise an Exception?"}
    w10["traceback.print_exc() to console.log, then<br/>verdict = empty calls, failed=True, blame=infra,<br/>reason=ExceptionType: message<br/>base.py:417"]
    w11["_record(task, candidate, verdict)<br/>base.py:430"]
    v1{"any of the 7 IDENTITY_FIELDS present?"}
    v2{"calls missing?"}
    v3{"blame or reason declared without failed?"}
    v4{"failed with blame outside Blame?"}
    v5{"failed with an empty reason?"}
    v6{"not failed but blame or reason set?"}
    verr["ValueError on the worker thread<br/>base.py:437-470"]
    w12["record = identity + failure triple + the rest of score()<br/>base.py:472"]
  end

  e8["finished.result() re-raises whatever the worker raised<br/>base.py:395"]
  e9["json.dumps, then write + flush inside the one Lock<br/>base.py:397"]
  e10["print the progress line, with FAILED blame: reason when failed<br/>base.py:401"]
  e11{"more futures?"}
  e12["return written<br/>base.py:410"]
  e13["BaseException: cancel every UNSTARTED future, then re-raise<br/>base.py:406"]

  e0 --> e1 --> e2 --> e3 --> e4 --> e5 --> e6 --> e7
  e6 --> w0
  w0 --> w1
  w1 -->|"if the protocol calls a model"| w2
  w1 -->|"Echo: none"| w9
  w2 --> w3 --> w4
  w4 -->|no| w5
  w4 -->|yes| w6 --> w7 --> w8
  w8 --> w9
  w5 --> w9
  w9 -->|yes| w10 --> w11
  w9 -->|no| w11
  w11 --> v1
  v1 -->|yes| verr
  v1 -->|no| v2
  v2 -->|yes| verr
  v2 -->|no| v3
  v3 -->|yes| verr
  v3 -->|no| v4
  v4 -->|yes| verr
  v4 -->|no| v5
  v5 -->|yes| verr
  v5 -->|no| v6
  v6 -->|yes| verr
  v6 -->|no| w12
  w12 --> e8
  verr --> e8
  e7 --> e8
  e8 -->|"returned a dict"| e9 --> e10 --> e11
  e8 -->|"raised"| e13
  e11 -->|yes| e7
  e11 -->|no| e12
```

## Step by step

### A class statement is the registration

`Run.__init_subclass__` (`base.py:138`) runs the moment the `class` body finishes, and it refuses
three things. A subclass with no `protocol` **of its own** — `cls.__dict__.get("protocol", "")`, not
`cls.protocol`, so an inherited name does not count — raises, because two protocols filing records
under one name cannot be told apart afterwards. A name another class already holds raises, because
every run directory written under the old class would `attach` as the new one and `records.jsonl`
records only the name. Everything else lands in `REGISTRY` (`base.py:67`), a plain module-level dict.

That dict is filled by `__init_subclass__` and by nothing else, so **a protocol module that
`pipeline/protocols/__init__.py` does not import does not exist.** This shipped: `__init__.py`
imported only `.base`, `REGISTRY` held `echo` alone, every in-process check passed because the
checker had imported the protocol by hand, and every real `.run()` died inside the three-second
launch grace with `KeyError: no protocol registered as 'tm'`. The imports in `__init__.py` are
registration, not convenience re-exports.

```
.venv/bin/python -c "import pipeline.protocols as p; print(sorted(p.REGISTRY))"
['echo', 'tm', 'trigger_search', 'trusted_solve', 'unit_testing']
```

### `__init__` resolves what the config has to carry

`Run.__init__` (`base.py:157`) does four things worth naming.

`_dataset_and_path` (`base.py:91`) returns `(Dataset, str)` and refuses a `Dataset` that was not
loaded from a file: `config.json` would have no path to record and the subprocess would have nothing
to load. A string or `Path` is loaded here, in your process, so a broken dataset fails at
construction rather than in tmux.

`_resolved_cache` (`base.py:74`) is the one knob stored **resolved** rather than as asked for.
`runs == 1` keeps the caller's choice, defaulting to `True`. `runs > 1` forces `False`, and
`runs > 1, cache=True` raises rather than being quietly downgraded — the inspect cache key includes
the seed, temperature is a no-op on the provider we use
(`model.TEMPERATURE_REJECTING_PREFIXES` contains `deepseek-v3.2`), and the seed is therefore the only
thing separating one repetition from the next. Six arms' TM scores came back byte-identical for this
reason and were read as six measurements agreeing. A subclass may override the *default* only:
`TrustedSolve` passes `cache=False` when the caller passed `None`, because its prompt carries no
candidate and both candidates of a task hash to one cache key.

`_serialisable` (`base.py:104`) tries `json.dumps(params)` and re-raises a `TypeError` naming
`sorted(params)` — every parameter key, not the offending one — with the original message appended,
so a knob that could not be rebuilt from `config.json` is refused at construction rather than in the
subprocess after the session is already up.

`self.seeds` (`base.py:185`) is `tuple(seed + rep for rep in range(runs))` — one seed per repetition,
and the only thing that varies between them. Collapsing reps into one record is the subclass's job;
the base only hands it the seeds.

### The serialisation round trip

`config()` (`base.py:207`) is the document: `protocol`, `run_name`, `data`, `model`, `runs`, `seed`,
the **resolved** `cache`, and `params`. Nothing that varies between two runs of one experiment may go
in it — no timestamp, no hostname — because `write_config` tells a resume from a reused name by
comparing documents.

`write_config` (`base.py:225`) creates the directory and writes that document, but first, if
`config.json` already exists, it compares. Identical means resume and the write is a no-op. Different
raises, printing both documents, because a second experiment wearing a used name would append its
records to the first's and pool two populations into every rate computed off the file.

`from_config` (`base.py:247`) looks `document["protocol"]` up in `REGISTRY`, raises a `KeyError`
listing what *is* registered when it misses, and then — when called as `TM.from_config` rather than
`Run.from_config` — refuses a document whose protocol resolves to some other class, so
`TM.attach("some-trigger-run")` cannot read another protocol's records under TM's field names. It
reconstructs with the six named arguments plus `**document["params"]`, which is why every constructor
argument has to survive `json.dumps`.

`attach` (`base.py:273`) is `from_config` over `runs/<run_name>/config.json`, raising
`FileNotFoundError` naming `runs/` when the directory holds no config. It is the whole of what a run
registry used to be: the run is its own label.

One gap here is worth knowing about. `_serialisable` checks that `params` *dumps*, not that it
*round-trips*, and it stores `dict(params)` rather than `json.loads(json.dumps(params))`. A tuple
param, or a dict with integer keys, constructs and writes fine and then makes every later resume
raise `already describes a different run`, because the in-memory tuple compares unequal to the list
that came back off disk. No shipped protocol passes one — every knob in `tm`, `solve`,
`trigger_search` and `unit_testing` is a `str`, `int`, `float` or `bool` — so this is latent, not
live.

### `run()`: config, pending, launch, poll

`run(wait=True)` (`base.py:301`) writes the config, then calls `pending()`. If nothing is pending it
prints `N/N already scored, nothing to run` and returns without touching tmux — which is what makes
re-running an arm under the same `run_name` free.

Otherwise it builds `argv`:

```
env PYTHONPATH=<REPO_ROOT> <sys.executable> -m pipeline.protocols.base runs/<run_name>/config.json
```

and hands it to `launch_mod.launch` with `cwd=Path.cwd()`. `RUNS_DIR` is `Path("runs")`, relative and
resolved against the CWD every time, so the subprocess is given the same CWD the caller had and both
processes agree on where the run directory is. Launching from anywhere but the repo root therefore
writes `runs/` there; `PYTHONPATH` is what keeps the import working regardless.

`LaunchFailed` (`launch.py:27`) means *a run that never started*, and it arrives from three places in
`launch` (`launch.py:65`): the session name is already taken (`launch.py:81`), `tmux new-session`
itself exited non-zero and the message carries its stderr (`launch.py:97`), or the session was gone
when `launch` re-checked `alive` after `SESSION_LIVENESS_GRACE_SECONDS = 3.0`, in which case the
message carries the last 2000 characters of `console.log` (`launch.py:100`, `_failure_excerpt` at
`launch.py:108`). `run()` forgives it in exactly one case (`base.py:327`): it re-reads `pending()`
from disk, and if every candidate now has a record it prints `scored inside the launch grace` and
returns. A resumed run with two candidates left legitimately finishes inside three seconds, and the
artifact is what says so. Any other vanished session re-raises.

### `launch.py`: tmux, the tee, and proof-of-start

`launch` runs one shell string in a detached session:

```
mkdir -p runs/<run_id> && <command> 2>&1 | tee runs/<run_id>/console.log
```

Both streams are merged and teed, so the traceback from a `score()` that raised, `prepare`'s
credential error and the per-candidate progress lines all land in one file. That log exists to
explain a failed launch; it is never where a result is read from, because nothing writes a heartbeat
and artifact counts are the only ground truth.

Proof-of-start is `time.sleep(grace_seconds)` then `alive(run_id)` — `alive` (`launch.py:43`) is
membership in `tmux list-sessions -F '#{session_name}'`, and `sessions()` (`launch.py:31`) returns
`[]` rather than raising when no tmux server is running at all. A launch that failed must never read
as a launch that succeeded, which is the whole reason the grace exists: a mistyped argument surfaces
at launch rather than as an empty `runs/` in the morning.

Refusing a live session name (`launch.py:80`) is not politeness. Two processes appending to one
`records.jsonl` interleave partial lines and double-count candidates, and the subprocess resumes
anyway, so the fix is `tmux attach -t <run_id>`, not a second session beside it.

`pane(run_id)` (`launch.py:51`) captures the tail of a live screen and raises when the session is
gone; `kill(run_id)` (`launch.py:61`) swallows its own failure, so killing an already-dead run is not
an error.

### `_follow()`: polling, and Ctrl-C

`_follow` (`base.py:340`) loops on `status()` every `POLL_SECONDS = 2.0`, printing a carriage-returned
`scored/total` line. `status()` (`base.py:283`) reads liveness **before** the count, deliberately: a
session that exits between the two reads is then reported with the records it actually finished,
rather than as alive-and-short. `_follow` checks completion before liveness for the same reason — a
process that wrote its last record and exited is a success, not a `RunFailed`.

`RunFailed` (`base.py:70`) carries `_console_tail` (`base.py:363`), the last 2000 characters of
`console.log`, or `(the run produced no console output)` when the file is missing.

`KeyboardInterrupt` is caught (`base.py:356`) and prints the two commands you need —
`Cls.attach(name).status()` and `pipeline.launch.kill(name)`. Ctrl-C **detaches**; the tmux session
and the work continue. Nothing here kills a run for you, and nothing here stops the machine sleeping
either, which is why `caffeinate` runs alongside.

### The subprocess: two module objects, two `REGISTRY` dicts

`python -m pipeline.protocols.base` makes runpy import the parent package `pipeline.protocols` first
— which imports `.base`, `.solve`, `.tm`, `.trigger_search`, `.unit_testing`, filling
`pipeline.protocols.base.REGISTRY` with all five — and *then* executes `base.py` a second time under
the name `__main__`. That second execution builds a second `Run` class and a second `REGISTRY`, and
the only subclass defined in the file is `Echo`, so `__main__.REGISTRY == {"echo": __main__.Echo}`.
Verified:

```
imported REGISTRY: ['echo', 'tm', 'trigger_search', 'trusted_solve', 'unit_testing']
second copy REGISTRY: ['echo']
same Run class? False
```

`_entry_point_in_the_imported_module` (`base.py:568`) exists for exactly that. It does
`from pipeline.protocols.base import main as registered_main` and calls *that* — the copy whose
`REGISTRY` is full — rather than the `main` defined twenty lines above it in the same file. Calling
the local one would raise `KeyError: no protocol registered as 'tm'` on every protocol but `Echo`.

`main` (`base.py:545`) then does four things in order. `load_dotenv(REPO_ROOT / ".env")` first,
because a detached tmux session inherits the environment of the tmux **server**, which was started
before any of these variables were exported; the credentials have to arrive with the process that
makes the call, not with the shell that launched it. `importlib.import_module("pipeline.protocols")`
next, redundant under `-m` but not when `main` is called from anywhere else. Then `from_config` and
`execute()`. It returns `0` whenever the loop completed — records carrying a failure are results, not
a crash, so the exit code says nothing about whether anything was measured.

### `execute()`: repair, prepare, eight threads, one lock

`execute` (`base.py:369`) is the only writer of `records.jsonl`.

`_repair_truncated_tail` (`base.py:116`) runs first. `load_records` forgives a final line with no
trailing newline, which is what a process killed mid-write leaves — but that forgiveness expires the
instant a resumed run appends, because the fragment stops being the last line and the whole artifact
then raises. So the file is truncated back to the last `\n` before anything is opened for append, and
the number of bytes dropped is printed.

`self.prepare(self.data)` (`base.py:376`) runs next, before `pending()` and before any thread exists.
A protocol resolving credentials or reading an upstream run raises **here**, as one message at the top
of `console.log`, instead of arriving as one identical infra record per candidate with half an
artifact on disk.

Then `pending()`, then a single `open(..., "a")`, then
`ThreadPoolExecutor(max_workers=WORKERS)` with `WORKERS = 8` (`base.py:49`). Every remaining pair is
submitted up front, and `as_completed` consumes them in **completion order**, not dataset order — so
`records.jsonl` is not ordered, and a reader that zips two runs positionally instead of joining on
`candidate_id` will misalign them.

The `Lock` (`base.py:386`) guards the `write` + `flush` pair. Only the thread running the
`as_completed` loop currently enters it, so it is uncontended today; it is what keeps that true if a
protocol ever writes from a worker. The flush is not optional: `records.jsonl` is the run's only
heartbeat, and a buffered line is a candidate that looks unscored to `status()` and gets re-paid on
resume.

The `except BaseException` handler (`base.py:406`) cancels every future that has not started and
re-raises. `cancel()` cannot touch a future already running, and the `with ThreadPoolExecutor` exit
then blocks until those finish, so a kill is not instant. It also discards the results of any futures
that completed but had not yet been consumed by `as_completed` — those calls were paid for and are
lost, and their candidates stay pending.

### `_record_for` and `_record`: where a raise becomes `blame="infra"`

`_record_for` (`base.py:412`) is the try/except. It catches `Exception` — not `BaseException`, so a
`KeyboardInterrupt` or `SystemExit` reaches the handler in `execute` instead — prints the traceback to
`console.log`, and returns a verdict of `{calls: [], failed: True, blame: "infra", reason:
f"{type(error).__name__}: {error}"}`. Raising out of `score` is for a bug in the protocol itself, and
this is exactly what the base records for it. `ModelCallFailed` is a `RuntimeError`, so a dead socket
lands here too.

`_record` (`base.py:430`) validates before it builds, and every check is a defect that reached a
number first:

- **Identity clash** (`base.py:435`). `score()` may not return any of `run_name`, `protocol`, `split`,
  `task_id`, `candidate_id`, `label`, `is_attack`. A protocol restating identity is a protocol that
  can contradict it.
- **Missing `calls`** (`base.py:441`). A protocol that calls no model records `[]`, so a prompt that
  was lost cannot pass for a protocol that never asked.
- **A triple without `failed`** (`base.py:449`). The failure fields are `pop`ped out of the verdict,
  and declaring `blame` or `reason` without `failed` raises — every reader filters on that one flag,
  so the blame would be written down beside a record counted as a clean verdict.
- **Blame outside the enum** (`base.py:457`). `Blame` is a `str, Enum` in `data.py:36`, so the plain
  strings `"model"` and `"infra"` compare equal to its members and nothing else passes.
- **A failure with no reason** (`base.py:464`).
- **Blame on a record that did not fail** (`base.py:466`).

All six raise on the worker thread, propagate through `finished.result()` and hit the `BaseException`
handler, which kills the whole run. That is loud but late: the traceback is only in `console.log`, and
the artifact is left partial. `REACHED_A_VERDICT` (`base.py:65`) supplies the default
`{"failed": False, "blame": None, "reason": None}` for a `score()` that declared nothing.

### `pending()` and `status()`: resume and heartbeat

`pending()` (`base.py:292`) builds the set of `candidate_id`s already in `records.jsonl` and returns
every `(task, candidate)` from `Dataset.candidates()` not in it, in dataset order — train before test,
honest before attack. A killed run therefore costs at most the calls that were in flight.

`status()` (`base.py:283`) is `{"scored": len(load_records(...)), "total": self.total, "alive": ...}`,
where `total` (`base.py:203`) counts both halves of the dataset. Both read the file fresh, so both
work mid-run and from any process.

**The known limitation: `pending()` counts a failed record as done.** A candidate that died on a dead
socket already has a record, so it is never attempted again and the run reports complete. That
contradicts why `blame` exists at all — `"model"` is data about the thing under study, `"infra"` is
our noise and should be retried. It is left this way deliberately, because retrying appends a *second*
record for a candidate that already has one and `load_records` keeps both, double-counting it in every
denominator; the honest fix is "a candidate's record is its latest attempt", a change to the artifact
contract rather than a patch.

Until then the recovery is manual, and it works. Back the file up first.

```
# stop the run, drop the infra failures, resume — it picks them up as pending
python -c "from pipeline import launch; launch.kill('ut-with-plain_v2')"
# rewrite records.jsonl without lines where failed and blame == "infra"
python -c "from pipeline.protocols import UnitTesting; UnitTesting.attach('ut-with-plain_v2').run()"
```

And print `Counter((r['failed'], r['blame']) for r in load_records(name))` after every run — a run
that is 100% infra failures otherwise reads as a completed one.

### `model.complete_sync`: the one bridge, and the deadlock

`Run.execute` scores on threads; `TrustedModel.completion` is a coroutine. `complete_sync`
(`model.py:244`) is the **only** place those two meet, and `tm.py`, `trigger_search.py`,
`unit_testing.py` and `solve.py` all call it rather than bridging themselves.

`shared_loop()` (`model.py:212`) starts one `asyncio` loop on a daemon thread the first time it is
asked, under a lock, and hands the same one out forever after. Process-wide, not per-run:
`get_model` memoises one inspect `Model` per (name, config), and both the provider's httpx pool and
inspect's own semaphores bind to the loop that first awaited them, so a call made on any second loop
fails on state the first one closed. Three separate bridges existed once and one of them called
`asyncio.run` per call.

`_survivable` (`model.py:230`) re-raises an escaping `BaseException` as `ModelCallFailed` and lets
`Exception` through untouched. This is the guard that is easy to drop in a rewrite, and here is the
mechanism it prevents: a `KeyboardInterrupt` or `SystemExit` raised inside a coroutine is re-raised by
`Task.__step` rather than stored on the future, so it propagates into `run_forever` and **ends the
loop thread**. The loop object still exists and still looks fine. Every later
`run_coroutine_threadsafe` then schedules onto a loop nobody is running, returning a future nothing
will ever complete — eight worker threads all parked in `.result()`. That deadlocked the whole test
suite for five minutes at 1% CPU. The five minutes is the bound below, not a coincidence: at
`reasoning="low"` the ladder gives `http_retry_budget = max(240, 2 × 120) = 240`, and 240 + 60 = 300
seconds is exactly when the eight parked workers gave up and the run continued with eight infra
records. `complete_sync` also checks `loop.is_running()` up front (`model.py:254`) and raises with the
instruction to restart the process rather than trusting anything scored after that point.

`.result()` is bounded (`model.py:262`) at `model.runtime.http_timeout + BRIDGE_MARGIN_SECONDS`, where
`http_timeout` is the ladder's `http_retry_budget` (`tm.py:45`, `solve.py:220`, `trigger_search.py:239`;
`UnitTesting` builds the same quantity by hand at `unit_testing.py:480`) and the margin is 60 seconds —
so the bound equals the ladder's `outer_call` rung and can only fire after every retry the call was
entitled to. Two consequences. There is deliberately no `except` around it: a call that never returned
is infra, and `Run._record_for` is the single place that blame is stated. And
`Future.result(timeout=...)` does not cancel: on a bridge timeout the coroutine keeps running on the
shared loop, still holding its slot in `max_connections`, after the worker has already given up on it.

## The record it writes

The first ten fields are what `_record` (`base.py:472`) names explicitly; `calls` and everything after
it come out of `score()`'s own dict, splatted in with `**fields` in the order the protocol built them,
so a page for a protocol documents only its part. Every shipped protocol returns `calls` first, which
is why the order in the file is the order here.

| field | type | meaning | what `None` means |
|---|---|---|---|
| `run_name` | `str` | `self.run_name` — the directory and the tmux session | never `None` |
| `protocol` | `str` | `type(self).protocol`, the `REGISTRY` key | never `None` |
| `split` | `str` | `data.split_of(task_id)`, `"train"` or `"test"`; raises for a task in neither | never `None` |
| `task_id` | `str` | `task.task_id` | never `None` |
| `candidate_id` | `str` | `candidate.candidate_id` — the resume key, unique across the dataset | never `None` |
| `label` | `str` | `candidate.label`: `"honest"` or `"attack_0"` | never `None` |
| `is_attack` | `bool` | `label.startswith("attack_")` | never `None` |
| `failed` | `bool` | the measurement did not happen. The one flag every reader filters on | never `None` |
| `blame` | `str \| None` | `"model"` (nothing parseable came back — data about the thing measured) or `"infra"` (our machinery broke — noise to retry) | `None` **iff** `failed` is `False`; the base raises on any other combination |
| `reason` | `str \| None` | free text stated where the failure was detected; for a raise out of `score`, `f"{type(error).__name__}: {error}"` | `None` **iff** `failed` is `False`; a failure with an empty reason raises |
| `calls` | `list` | the protocol's own record of every model call — required, `[]` for a protocol that calls none | a protocol may put `None` inside a call entry; the key itself is never absent |
| *protocol fields* | — | whatever else `score()` returned, unchanged | per protocol |

`Echo.score` (`base.py:540`) returns the minimum: `calls` (empty), `echoed` (`str`, the candidate id
echoed back) and `code_chars` (`int`, `len(candidate.code)`). It never fails, so its records always
carry `failed=False, blame=None, reason=None`.

## Where it fails silently

The base's failure modes are all the same shape: a measurement that did not happen, written down as a
believable number. *(Happened)* marks the ones that have already reached a published result.

**A resume never retries an infra failure — and reports complete.** *(Happened.)* `pending()` keys on
`candidate_id` alone, so a candidate whose only record is `failed=True, blame="infra"` is scored as
far as the resume is concerned. `run()` prints `N/N already scored, nothing to run`, `_follow` prints
`50/50`, and `main` exits `0`. A run that is 100% infra failures is indistinguishable from a completed
one at every one of those three surfaces. The only thing that separates them is
`Counter((r['failed'], r['blame']))` over the artifact, and the manual recovery above.

**A protocol module nobody imports is not registered.** *(Happened, and shipped.)* `REGISTRY` held
`echo` alone; every in-process test passed because the checker imported the class by hand; every
detached run died in the subprocess. It arrives at the caller as `LaunchFailed` with the `KeyError` in
the excerpt, which is loud — except on the one forgiven path, where a run that already has every
record swallows it and prints `scored inside the launch grace`.

**`runs > 1` on a warm cache is one measurement reported `runs` times.** *(Happened — six arms.)* The
inspect cache key includes the seed and temperature never reaches this provider, so the seed is the
only thing that differs between reps. `_resolved_cache` forces the cache off and raises on
`cache=True`, but nothing checks afterwards that the repetitions actually differ. Assert that before
trusting an average.

**A blind prompt is one cache key across both candidates.** *(Happened; measured at 2 calls, 1 cache
entry.)* The rule above is about repetitions of one prompt; a protocol whose prompt does not carry the
candidate has the same problem *across* candidates, and its second attempt is the first replayed —
so an agreement metric comes out true by construction. `TrustedSolve` defaults `cache=False` for this;
any later protocol whose prompt omits the candidate inherits the problem and not the fix.

**The prompt's output contract and the parser can disagree, and the run still completes.** *(Happened
— the most expensive defect in this port.)* `prompts.OUTPUT_SPLIT_TESTS` promises a bare JSON object;
`parse.parse_properties` reads a fenced python block. Fed the former it recovered **0 of 566** stored
answers under `runs/m-*`, every candidate came back `failed` with `blame="model"`, and our own
prompt/parser mismatch was booked as a 100% trusted-model failure rate with catch and FPR at n=0. The
base cannot see this: `failed`/`blame="model"` is exactly what a well-behaved protocol reports when a
model answers unusably. Nothing between the rendered prompt and the parser is the base's to check.

**`main` returns 0 whatever the records say**, and the tmux session then exits cleanly. The exit code
is a statement about the loop finishing, not about anything being measured.

**Records land in completion order.** `as_completed` does not preserve submission order, so
`records.jsonl` is unordered even though `pending()` is not. Joining two runs on line position instead
of `candidate_id` silently pairs the wrong candidates.

**A bridge timeout abandons a live call.** `Future.result(timeout=...)` raises without cancelling, so
the coroutine keeps running on the shared loop holding a connection while the worker records infra and
moves on. Enough of them and the pool starves, which reads as more timeouts.

**Paid work is discarded on a kill.** The `BaseException` handler cancels unstarted futures, but any
future that finished and was not yet consumed by `as_completed` has its record thrown away. Those
candidates stay pending and are re-paid on resume.

Two things the base does **not** protect you from, documented on the protocol pages because that is
where the fix lives: `sandbox.run_raw` fires on `outcome == "catch"` and never `"fail"`, and an
incomplete grid (`complete=False`) can only *lose* a catch, so it under-reports and must never be read
as a clean negative.
