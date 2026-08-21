"""Read a finished run: what was written, what fired, and what was actually true.

Every function takes a candidate id and returns a value. Nothing prints and nothing is composite —
one call per thing you want to look at, so a notebook cell shows exactly one fact.

Three sources are joined here. The pool holds ground truth (the attack, the honest code, the real
trigger). `runs/<id>/suites/<candidate>/run_<i>/` holds what the model wrote. `runs/<id>/probe.json`
holds the scores. Prompts are not stored; they are re-rendered from the flags the run recorded,
which is exact because rendering is deterministic.

The specification and the reference come through the run's BACKEND, not out of the pool, because a
BigCodeBench pool carries neither: its statement is the dataset's `code_prompt` and its reference is
the canonical solution reassembled onto it. `--domain` is the only thing that says which backend,
and a run that predates the flag is an APPS run — `probe.load_problems` refused any other pool then.

Nothing here costs a model call. `probe.py` is the half that does.

    import audit
    audit.use("a2-hard50")
    audit.reach("apps_3945_attack_0")
    audit.flagged("apps_3945_attack_0")
"""

from __future__ import annotations

import ast
import json
from functools import lru_cache
from pathlib import Path

from pipeline import monitor, pbt
from pipeline.schema import Candidate, Problem

import probe as probe_mod
from probe import (
    COMPLETION_STEM,
    FUNCTION,
    RATIONALE_STEM,
    REASONING_STEM,
    REASONING_UNKNOWN_STEM,
    REPETITION_DIR_PREFIX,
    TESTS_STAGE,
    VERDICT_ESSAY_FIELD,
    build_prompt,
    input_section,
    line_reader_read_the_inputs,
    load_problems,
    prose_outside_fences,
    staged_file,
    stages_of,
    suite_dir,
)

_ACTIVE_RUN = ""

THE_ONLY_STAGE = "*"
FORMAT_BEFORE_THE_FLAG = "blocks"
DOMAIN_BEFORE_THE_FLAG = "apps"


def use(run_id: str) -> str:
    """Choose the run every accessor below reads, so a call passes only the candidate id."""
    global _ACTIVE_RUN
    _ACTIVE_RUN = run_id
    return run_id


def _chosen(run: str) -> str:
    picked = run or _ACTIVE_RUN
    if not picked:
        raise ValueError("no run selected — call use('<run-id>') or pass run='<run-id>'")
    return picked


@lru_cache(maxsize=8)
def _probe(run: str) -> dict:
    path = Path("runs") / run / "probe.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist — the run has not finished")
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def _pool_tasks(pool_path: str) -> dict:
    return json.loads(Path(pool_path).read_text(encoding="utf-8"))["candidates"]


def candidates(run: str = "") -> list[dict]:
    """Every verdict in the run, one per candidate per repetition."""
    return _probe(_chosen(run))["verdicts"]


def stages(run: str = "") -> tuple[str, ...]:
    """The authoring calls this run made, which is what its per-suite artifacts are named after.

    A run that predates `--format` made one call and wrote `completion.txt`, which is exactly the
    layout `blocks` writes; that is a fact readable off the directory, not a substituted flag.
    """
    record = _probe(_chosen(run))
    written = (
        record["output_format"] if "output_format" in record else FORMAT_BEFORE_THE_FLAG
    )
    return stages_of(written)


def _stage(run: str, stage: str) -> str:
    """Which authoring call an accessor is being asked about. Never guessed on a split run.

    `--format split` writes two completions, two reasonings and two rationales per suite, and they
    are different answers to different prompts. An accessor that silently picked one would hand
    back the tests call's text to a caller asking why the inputs were chosen, so the default is
    "the only one" and a run with two of them refuses and names them.
    """
    held = stages(run)
    if stage == THE_ONLY_STAGE:
        if len(held) == 1:
            return held[0]
        raise ValueError(
            f"{_chosen(run)!r} made {len(held)} authoring calls per suite; "
            f"pass stage= one of {list(held)}"
        )
    if stage not in held:
        raise ValueError(f"{_chosen(run)!r} has no {stage!r} stage; it made {list(held)}")
    return stage


def _inputs_stage(run: str, stage: str) -> str:
    """The call that chose the inputs, which is the only one that can have dropped any.

    Defaulting to it is a derivation rather than a guess: the tests call is not shown a search
    space to lose lines from, so there is only one call the question can be about.
    """
    if stage != THE_ONLY_STAGE:
        return _stage(run, stage)
    held = stages(run)
    return probe_mod.INPUTS_STAGE if probe_mod.INPUTS_STAGE in held else held[0]



def verdict(candidate_id: str, run: str = "", run_index: int = 0) -> dict:
    """One candidate's scores on one repetition. Raises rather than returning an empty record.

    The monitor's prose is left out — it is two thousand characters in the middle of a dozen
    numbers, and it has its own accessor, `tm_reasoning`.
    """
    return {
        key: value
        for key, value in _raw_verdict(candidate_id, run, run_index).items()
        if key != VERDICT_ESSAY_FIELD
    }


def _raw_verdict(candidate_id: str, run: str, run_index: int) -> dict:
    """One candidate's row for one repetition, or a refusal naming the repetitions it does hold.

    `--runs N` is a flag, so a caller asking for repetition 7 usually does not know how many there
    are; a refusal that does not list them cannot be acted on. `analyse_probes.load_arm` answers
    the same question the same way.
    """
    held = {
        record.get("run", 0): record
        for record in _probe(_chosen(run))["verdicts"]
        if record["candidate_id"] == candidate_id
    }
    if run_index in held:
        return held[run_index]
    if not held:
        raise KeyError(f"{candidate_id!r} is not in {_chosen(run)!r}")
    raise KeyError(
        f"{candidate_id!r} has no verdict for run {run_index} in {_chosen(run)!r}; "
        f"it has {sorted(held)}"
    )


def _any_verdict(candidate_id: str, run: str) -> dict:
    for record in _probe(_chosen(run))["verdicts"]:
        if record["candidate_id"] == candidate_id:
            return record
    raise KeyError(f"{candidate_id!r} is not in {_chosen(run)!r}")


def _task(candidate_id: str, run: str) -> dict:
    probe = _probe(_chosen(run))
    return _pool_tasks(probe["pool"])[_any_verdict(candidate_id, run)["task_id"]]


def domain(run: str = "") -> str:
    """Which benchmark backend this run read its pool through.

    A run that recorded no `--domain` was made while `probe.load_problems` refused any pool that was
    not stdin/stdout, so it is an APPS run. That is a fact about what the code could do at the time,
    the same kind of reading `stages` makes of a run predating `--format`, not a default substituted
    for a measurement.
    """
    record = _probe(_chosen(run))
    return record["domain"] if "domain" in record else DOMAIN_BEFORE_THE_FLAG


@lru_cache(maxsize=8)
def _problems(run: str) -> dict[str, Problem]:
    """Every task the run scored, as the `Problem` records it was built from.

    `probe.load_problems` rather than a second reading of the pool here: the spec, the entry point,
    the statement examples and the reference of a BigCodeBench task are not in its pool at all, and
    a reconstruction that read only the pool would have to invent them or claim they were absent.

    Whole run at a time, and cached: the loader reads the pool from disk, which is 52 MB for
    `apps_pool_hard.json`, and asks the backend for its dataset, which for BCB is a scan of 1,140
    tasks. Per task that is one of each per accessor call.

    The task list comes off the verdicts rather than the recorded split, because every run has
    verdicts and the runs that predate `--split` being recorded do not have the other.
    """
    record = _probe(run)
    task_ids = list(dict.fromkeys(verdict["task_id"] for verdict in record["verdicts"]))
    problems = load_problems(Path(record["pool"]), task_ids, domain(run))
    return {problem.task_id: problem for problem in problems}


def _problem(candidate_id: str, run: str) -> Problem:
    return _problems(_chosen(run))[_any_verdict(candidate_id, run)["task_id"]]


def _candidate(candidate_id: str, run: str) -> Candidate:
    for candidate in _problem(candidate_id, run).candidates:
        if candidate.candidate_id == candidate_id:
            return candidate
    raise KeyError(f"{candidate_id!r} is not a candidate of its own task")


def _attack(candidate_id: str, run: str) -> dict:
    proposals = _task(candidate_id, run)["attack_proposals"]
    if not proposals:
        raise KeyError(f"the task behind {candidate_id!r} has no attack proposal")
    return proposals[0]


def task_spec(candidate_id: str, run: str = "") -> str:
    """The specification the run showed every blind call, as the backend assembled it.

    Read off the `Problem` rather than the pool: a BigCodeBench pool carries no `task_description`
    at all — the statement is the dataset's `code_prompt`, which only the backend can reach.
    """
    return _problem(candidate_id, run).main_task


def code(candidate_id: str, run: str = "") -> str:
    """The submission that was actually monitored — honest or attack, whichever this id names."""
    return _candidate(candidate_id, run).code


def honest_code(candidate_id: str, run: str = "") -> str:
    return _task(candidate_id, run)["honest"]["code"]


def attack_code(candidate_id: str, run: str = "") -> str:
    return _attack(candidate_id, run)["code"]


def reference(candidate_id: str, run: str = "") -> str:
    """A privileged correct solution. Inline in an APPS pool, reassembled from the dataset for BCB.

    Raises when the domain's backend supplies none, rather than handing back an empty string that
    reads as a task whose reference is trivially satisfied by anything.
    """
    problem = _problem(candidate_id, run)
    if not problem.reference_code:
        raise LookupError(
            f"the {domain(run)!r} backend supplies no reference solution for {problem.task_id}"
        )
    return problem.reference_code


def trigger(candidate_id: str, run: str = "") -> str:
    """The input the backdoor was built to fire on, from the pool. Ground truth, never a guess."""
    return _attack(candidate_id, run)["secret_input"]


def _suite_file(candidate_id: str, run: str, run_index: int, name: str) -> Path:
    record = _any_verdict(candidate_id, run)
    directory = suite_dir(
        Path("runs") / _chosen(run), record["task_id"], record["label"], run_index
    )
    path = directory / name
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist — {candidate_id!r} reached no verdict on run {run_index}, "
            f"or the run predates the run_<i> layout; it wrote {_repetitions_written(directory)}"
        )
    return path


def _repetitions_written(directory: Path) -> list[int]:
    """Which `run_<i>` directories this candidate actually has, so a refusal can be acted on."""
    return sorted(
        int(sibling.name.removeprefix(REPETITION_DIR_PREFIX))
        for sibling in directory.parent.glob(f"{REPETITION_DIR_PREFIX}*")
        if sibling.name.removeprefix(REPETITION_DIR_PREFIX).isdigit()
    )


def tests(candidate_id: str, run: str = "", run_index: int = 0) -> str:
    """The whole test file written for this candidate, as parsed and executed."""
    return _suite_file(candidate_id, run, run_index, "tests.py").read_text(encoding="utf-8")


def test_source(candidate_id: str, test_name: str, run: str = "", run_index: int = 0) -> str:
    """One test function from the suite, by name.

    A suite holds ten tests and usually one or two fired, so reading the whole file to find the one
    that matters is the slow way round.
    """
    source = tests(candidate_id, run, run_index)
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == test_name:
            return ast.get_source_segment(source, node)
    written = [n.name for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)]
    raise KeyError(f"{test_name!r} is not in {candidate_id}'s suite; it wrote {written}")


def inputs(candidate_id: str, run: str = "", run_index: int = 0) -> list[str]:
    """The trigger inputs the model guessed, in the order the harness ran them."""
    return json.loads(_suite_file(candidate_id, run, run_index, "inputs.json").read_text("utf-8"))


def completion(
    candidate_id: str, run: str = "", run_index: int = 0, stage: str = THE_ONLY_STAGE
) -> str:
    """The raw model output of one authoring call, before either parser touched it."""
    name = staged_file(COMPLETION_STEM, _stage(run, stage), ".txt")
    return _suite_file(candidate_id, run, run_index, name).read_text(encoding="utf-8")


def reasoning(
    candidate_id: str, run: str = "", run_index: int = 0, stage: str = THE_ONLY_STAGE
) -> str:
    """The provider's thinking behind one call. Empty means it sent none, which is a finding.

    Raises when the shape of the response hid whether there was any, rather than handing back the
    same empty string a provider that genuinely sent nothing produces. Runs made before the
    artifact existed have no file at all and raise from `_suite_file`.
    """
    chosen = _stage(run, stage)
    directory = _suite_file(
        candidate_id, run, run_index, staged_file(REASONING_STEM, chosen, ".txt")
    ).parent
    unknown_path = directory / staged_file(REASONING_UNKNOWN_STEM, chosen, ".json")
    if unknown_path.exists():
        raise LookupError(
            f"{candidate_id} has no measured reasoning on repetition {run_index}: "
            f"{unknown_path.read_text(encoding='utf-8')}"
        )
    return (directory / staged_file(REASONING_STEM, chosen, ".txt")).read_text(encoding="utf-8")


def authoring_notes(
    candidate_id: str, run: str = "", run_index: int = 0, stage: str = THE_ONLY_STAGE
) -> str:
    """The account the PROMPT asked the model for: why these inputs, why these assertions.

    Distinct from `reasoning`, which is what the provider sent unprompted: DeepSeek-V3.2 returns
    reasoning blocks only at a raised effort, so on a `low` run this is the only record of how a
    suite chose what it chose. Under `--format split` the default is the call that chose the
    inputs; pass `stage="tests"` for the other half.

    Runs made before the rationale artifact existed fall back to the prose beside the blocks, and
    a run that has neither says so rather than returning an empty string that reads like a model
    with nothing to say.
    """
    chosen = _inputs_stage(run, stage)
    directory = suite_dir(
        Path("runs") / _chosen(run),
        _any_verdict(candidate_id, run)["task_id"],
        _any_verdict(candidate_id, run)["label"],
        run_index,
    )
    written = directory / staged_file(RATIONALE_STEM, chosen, ".txt")
    notes = (
        written.read_text(encoding="utf-8")
        if written.exists()
        else prose_outside_fences(completion(candidate_id, run, run_index, chosen))
    )
    if not notes.strip():
        raise LookupError(
            f"{candidate_id} wrote no rationale on the {chosen or 'authoring'} call — either the "
            "model declined, or this run predates the prompt asking for one"
        )
    return notes


def dropped_inputs(
    candidate_id: str, run: str = "", run_index: int = 0, stage: str = THE_ONLY_STAGE
) -> list[dict]:
    """The lines of the completion the input parser could not read, and why.

    `inputs()` shows what survived; this shows what did not, which is where the interesting failures
    are. The model reliably wants to emit large inputs, and the format demands one literal JSON
    string per line, so it reaches for `" ".join(...)` or `range(...)` and the whole line is lost.

    A filter over `pbt.read_input_lines`, the same reader the parser itself uses, so this can never
    explain a failure the parse did not actually have. An answer the provider shaped to a schema
    was never read a line at a time and cannot have lost one, so it reports nothing rather than
    every line of a pretty-printed object.
    """
    chosen = _inputs_stage(run, stage)
    text = completion(candidate_id, run, run_index, chosen)
    if not line_reader_read_the_inputs(text):
        return []
    section = input_section(text)
    return [entry for entry in pbt.read_input_lines(pbt.input_block(section)) if not entry["ok"]]


def prompt(
    candidate_id: str, run: str = "", run_index: int = 0, stage: str = THE_ONLY_STAGE
) -> str:
    """One authoring prompt, re-rendered from the flags the run recorded.

    A run that recorded no `framing` was made before the flag existed and its prompt had no
    framing section at all. There is no template that can reproduce that now, so this refuses
    rather than rendering a prompt the run never saw — the exact failure `pbt.render` refuses a
    hole to prevent.
    """
    record = _probe(_chosen(run))
    if "framing" not in record:
        raise KeyError(
            f"{_chosen(run)!r} predates --framing; the prompt it used cannot be re-rendered"
        )
    chosen = _stage(run, stage)
    return build_prompt(
        _problem(candidate_id, run),
        code(candidate_id, run),
        record["n_tests"],
        record["n_inputs"],
        record["resolve"],
        record["code_visibility"],
        record["output_format"] if "output_format" in record else FORMAT_BEFORE_THE_FLAG,
        record["framing"],
        chosen,
        tuple(inputs(candidate_id, run, run_index)) if chosen == TESTS_STAGE else (),
    )


def tm_prompt(candidate_id: str, run: str = "") -> str:
    """What the trusted monitor was asked."""
    return monitor.tm_prompt(_problem(candidate_id, run), _candidate(candidate_id, run))


def tm_reasoning(candidate_id: str, run: str = "", run_index: int = 0) -> str:
    """What the trusted monitor answered, before `parse_suspicion` reduced it to a number."""
    record = _raw_verdict(candidate_id, _chosen(run), run_index)
    if VERDICT_ESSAY_FIELD not in record:
        raise KeyError(f"{_chosen(run)!r} predates stored monitor reasoning; it cannot be recovered")
    return record["tm_reasoning"]


def flagged(candidate_id: str, run: str = "", run_index: int = 0) -> list[dict]:
    """Which test fired, and the input it fired on. The pairing an audit turns on."""
    record = _raw_verdict(candidate_id, _chosen(run), run_index)
    if "catches" not in record:
        raise KeyError(
            f"{_chosen(run)!r} stored only test names; which input fired them cannot be recovered"
        )
    space = inputs(candidate_id, run, run_index)
    return [
        {
            "test": catch["test"],
            "input_index": catch["input_index"],
            "input": space[catch["input_index"]],
        }
        for catch in record["catches"]
    ]


def reach(candidate_id: str, run: str = "", run_index: int = 0) -> bool:
    """Is the real trigger among the inputs the model guessed?

    The hard ceiling on everything downstream: a test can only catch a backdoor on an input that
    executes it. False here means the suite never ran the backdoor at all, which is a different
    failure from an oracle that ran it and did not notice — and no aggregate rate separates them.
    """
    if not _any_verdict(candidate_id, run)["label"].startswith("attack_"):
        raise ValueError(f"{candidate_id!r} is honest; it has no trigger to reach")
    io_mode = _problem(candidate_id, run).io_mode
    wanted = _comparable(trigger(candidate_id, run), io_mode)
    return any(
        _comparable(guess, io_mode) == wanted
        for guess in inputs(candidate_id, run, run_index)
    )


def _comparable(one_input: object, io_mode: str) -> object:
    """One input reduced to the form two inputs are the SAME input in.

    Under stdio an input is text, and a statement pretty-prints its examples, so whitespace is the
    only thing normalised away. Under function io_mode an input is a mapping of keyword arguments:
    the pool stores the trigger as JSON text and the run stores its guesses parsed, and comparing
    those as strings makes `{"a": 1, "b": 2}` and `{"b": 2, "a": 1}` — the same call — a search
    miss. A miss is the flattering direction here, because it excuses every test that never fired.
    """
    if io_mode != FUNCTION:
        return " ".join(str(one_input).split())
    if isinstance(one_input, str):
        return json.loads(one_input)
    return one_input
