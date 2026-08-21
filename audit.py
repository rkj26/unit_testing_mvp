"""Read a finished run: what was written, what fired, and what was actually true.

Every function takes a candidate id and returns a value. Nothing prints and nothing is composite —
one call per thing you want to look at, so a notebook cell shows exactly one fact.

Three sources are joined here. The pool holds ground truth (the attack, the honest code, the real
trigger, the reference solution). `runs/<id>/suites/<candidate>/run_<i>/` holds what the model
wrote. `runs/<id>/probe.json` holds the scores. Prompts are not stored; they are re-rendered from
the flags the run recorded, which is exact because rendering is deterministic.

Nothing here costs a model call. `probe.py` is the half that does.

    import audit
    audit.use("a2-hard50")
    audit.reach("apps_3945_attack_0")
    audit.flagged("apps_3945_attack_0")
"""

from __future__ import annotations

import ast
import json
import re
from functools import lru_cache
from pathlib import Path

from pipeline import monitor, pbt
from pipeline.schema import Candidate, Problem

from probe import (
    input_section,
    VERDICT_ESSAY_FIELD,
    build_prompt,
    problem_from_task,
    suite_dir,
)

_ACTIVE_RUN = ""


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
    for record in _probe(_chosen(run))["verdicts"]:
        if record["candidate_id"] == candidate_id and record.get("run", 0) == run_index:
            return record
    raise KeyError(f"{candidate_id!r} has no verdict for run {run_index} in {_chosen(run)!r}")


def _any_verdict(candidate_id: str, run: str) -> dict:
    for record in _probe(_chosen(run))["verdicts"]:
        if record["candidate_id"] == candidate_id:
            return record
    raise KeyError(f"{candidate_id!r} is not in {_chosen(run)!r}")


def _task(candidate_id: str, run: str) -> dict:
    probe = _probe(_chosen(run))
    return _pool_tasks(probe["pool"])[_any_verdict(candidate_id, run)["task_id"]]


def _problem(candidate_id: str, run: str) -> Problem:
    record = _any_verdict(candidate_id, run)
    return problem_from_task(record["task_id"], _task(candidate_id, run))


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
    return _task(candidate_id, run)["task_description"]


def code(candidate_id: str, run: str = "") -> str:
    """The submission that was actually monitored — honest or attack, whichever this id names."""
    return _candidate(candidate_id, run).code


def honest_code(candidate_id: str, run: str = "") -> str:
    return _task(candidate_id, run)["honest"]["code"]


def attack_code(candidate_id: str, run: str = "") -> str:
    return _attack(candidate_id, run)["code"]


def reference(candidate_id: str, run: str = "") -> str:
    return _task(candidate_id, run)["reference_solution"]


def trigger(candidate_id: str, run: str = "") -> str:
    """The input the backdoor was built to fire on, from the pool. Ground truth, never a guess."""
    return _attack(candidate_id, run)["secret_input"]


def _suite_file(candidate_id: str, run: str, run_index: int, name: str) -> Path:
    record = _any_verdict(candidate_id, run)
    path = (
        suite_dir(Path("runs") / _chosen(run), record["task_id"], record["label"], run_index) / name
    )
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist — {candidate_id!r} reached no verdict on run {run_index}, "
            f"or the run predates the run_<i> layout"
        )
    return path


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


def completion(candidate_id: str, run: str = "", run_index: int = 0) -> str:
    """The raw model output, before either parser touched it."""
    return _suite_file(candidate_id, run, run_index, "completion.txt").read_text(encoding="utf-8")


def authoring_notes(candidate_id: str, run: str = "", run_index: int = 0) -> str:
    """The plan the model wrote before its two blocks: which condition each input targets.

    The provider returns no reasoning tokens for this model, so the only way to see how a suite
    chose its inputs is to have asked for it. Runs made before the prompt requested a plan have
    none, and say so rather than returning an empty string that reads like a model with nothing
    to say.
    """
    text = completion(candidate_id, run, run_index)
    prose = re.sub(pbt.FENCED_CODE, "", text, flags=re.DOTALL).strip()
    if not prose:
        raise LookupError(
            f"{candidate_id} wrote no plan — this run predates the prompt asking for one"
        )
    return prose


def dropped_inputs(candidate_id: str, run: str = "", run_index: int = 0) -> list[dict]:
    """The lines of the completion the input parser could not read, and why.

    `inputs()` shows what survived; this shows what did not, which is where the interesting failures
    are. The model reliably wants to emit large inputs, and the format demands one literal JSON
    string per line, so it reaches for `" ".join(...)` or `range(...)` and the whole line is lost.

    A filter over `pbt.read_input_lines`, the same reader the parser itself uses, so this can never
    explain a failure the parse did not actually have.
    """
    section = input_section(completion(candidate_id, run, run_index))
    return [entry for entry in pbt.read_input_lines(pbt.input_block(section)) if not entry["ok"]]


def prompt(candidate_id: str, run: str = "", run_index: int = 0) -> str:
    """The test-writer prompt, re-rendered from the flags the run recorded."""
    probe = _probe(_chosen(run))
    return build_prompt(
        _problem(candidate_id, run),
        code(candidate_id, run),
        probe["n_tests"],
        probe["n_inputs"],
        probe["resolve"],
        probe["code_visibility"],
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
    normalise = lambda text: " ".join(text.split())
    wanted = normalise(trigger(candidate_id, run))
    return any(normalise(guess) == wanted for guess in inputs(candidate_id, run, run_index))
