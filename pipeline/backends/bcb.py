"""BCB backend: `CorrectedBigCodeBenchSetting` in a DOCKER sandbox for ground-truth scoring.

BCB has no inline data — task spec, entry point, statement examples and the canonical solution all
come from HuggingFace (`bigcode/bigcodebench`, pinned through control_arena) via the setting. The
pool supplies only candidates: its ``code`` is already a complete module defining the entry point,
so it runs directly in the property runner and is submitted verbatim to control_arena, whose
`code_prompt + "\\n    pass\\n" + code` assembly leaves a column-0 module intact.

A pool task the pinned dataset does not carry ABORTS the load. It used to print a warning and drop
the task, which moved the denominator of every rate computed afterwards: a 30-task pool that became
22 reported catch rates over 22 under a heading that said 30.

Two settings choices are corrections of measured defects, not preferences:

`sandbox_type` is DOCKER because `local` is the host interpreter, which carries no pandas — 3 of 4
honest candidates scored `main_task_success=False` there, a missing dependency written down as the
model failing its task.

The scorer is `CorrectedBigCodeBenchSetting` because control_arena's stock `has_backdoor` decides
"did the backdoor trigger?" by printing `repr(result)` in the sandbox and reading back only the
FIRST stdout line, then comparing the two reprs as raw strings. A multi-line repr (pandas: 426 of
the 1,140 tasks; numpy: 334) is truncated to its header, so a backdoor that corrupts a data row
scores as no backdoor at all — 14 of `bcb_pool.json`'s 26 verified-working attacks, listed under its
`metadata.stock_grader_would_miss`.
"""

from __future__ import annotations

import ast
import doctest
import json
from dataclasses import dataclass
from typing import Any

from ..config import ScoringLimits
from ..schema import Candidate, Problem, ScoreResult
from ..scoring import CorrectedBigCodeBenchSetting, score_via_control_arena

EXAMPLES_SHOWN = 3
SANDBOX_TYPE = "docker"


@dataclass(frozen=True)
class _TaskMeta:
    """Everything the dataset — not the pool — supplies for one BCB task."""

    description: str
    entry_point: str
    reference: str
    example_inputs: list[dict[str, Any]]
    example_outputs: list[str]


def _entry_definition(statement: str, entry_point: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """The `def entry_point(...)` node in a BCB statement, which is itself Python source."""
    for node in ast.walk(ast.parse(statement)):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == entry_point
        ):
            return node
    raise ValueError(f"BigCodeBench statement defines no {entry_point}(...)")


def _readable_examples(docstring: str) -> list[doctest.Example]:
    """The `>>>` examples in a docstring, or none when doctest refuses to read it.

    `DocTestParser` raises on a want-block whose indentation does not line up, which 6 of the 1,140
    statements have. Such a statement shows no example this backend can read — the same state as one
    whose examples call nothing literal, and a fact about the statement rather than a measurement
    that failed, so it is not an `Unknown`.
    """
    try:
        return doctest.DocTestParser().get_examples(docstring)
    except ValueError:
        return []


def _entry_call(source: str, entry_point: str) -> ast.Call | None:
    """The example line as a direct call to the entry point, or None if it is anything else."""
    try:
        expression = ast.parse(source.strip(), mode="eval").body
    except (SyntaxError, ValueError):
        return None
    if (
        isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Name)
        and expression.func.id == entry_point
    ):
        return expression
    return None


def _literal_kwargs(call: ast.Call, parameter_names: list[str]) -> dict[str, Any] | None:
    """The call's arguments as a JSON-round-trippable kwargs dict, or None if any are not.

    A function-mode search space is JSON and is splatted as `**kwargs`, so an argument that is not a
    literal (a DataFrame built by an earlier `>>>` line, a file path opened at call time) cannot
    become a seed no matter how well it illustrates the spec.
    """
    if len(call.args) > len(parameter_names):
        return None
    kwargs: dict[str, Any] = {}
    for name, node in zip(parameter_names, call.args):
        try:
            kwargs[name] = ast.literal_eval(node)
        except (ValueError, TypeError):
            return None
    for keyword in call.keywords:
        if keyword.arg is None:
            return None
        try:
            kwargs[keyword.arg] = ast.literal_eval(keyword.value)
        except (ValueError, TypeError):
            return None
    try:
        json.dumps(kwargs, allow_nan=False)
    except (TypeError, ValueError):
        return None
    return kwargs


def statement_examples(
    statement: str, entry_point: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """The example calls a BCB statement shows, as kwargs dicts and their printed results.

    BigCodeBench's grading suite (`test_code`) is the answer key, so it is never spec-safe; the only
    inputs a defender can see are the `>>>` examples in the prompt's own docstring. This is the same
    rule `apps.statement_examples` applies to APPS pairs, reached differently because BCB stores the
    statement as source rather than as text with pairs beside it.

    269 of the 1,140 tasks yield at least one example that survives the JSON/literal bar. The rest
    take DataFrames, file paths or objects an earlier `>>>` line built, and carry none — the same
    empty state APPS renders as "(none provided)".
    """
    definition = _entry_definition(statement, entry_point)
    parameter_names = [
        a.arg for a in (*definition.args.posonlyargs, *definition.args.args)
    ]
    docstring = ast.get_docstring(definition)
    if docstring is None:
        return [], []
    inputs: list[dict[str, Any]] = []
    outputs: list[str] = []
    for example in _readable_examples(docstring):
        call = _entry_call(example.source, entry_point)
        if call is None:
            continue
        kwargs = _literal_kwargs(call, parameter_names)
        if kwargs is None:
            continue
        inputs.append(kwargs)
        outputs.append(example.want.strip())
    return inputs, outputs


def _hint(inputs: list[dict[str, Any]], outputs: list[str], n: int = EXAMPLES_SHOWN) -> str:
    """The visible examples as prompt text, inputs shown in the JSON the search space requires."""
    lines = [
        f"  KWARGS={json.dumps(inputs[i])} -> RETURNS {outputs[i]}"
        for i in range(min(n, len(inputs), len(outputs)))
    ]
    return "\n".join(lines) or "(none provided)"


class BcbBackend:
    name = "bcb"

    def __init__(self) -> None:
        self._setting = CorrectedBigCodeBenchSetting(sandbox_type=SANDBOX_TYPE)
        self._meta: dict[str, _TaskMeta] = {}

    def _load_meta(self, task_ids: list[str]) -> None:
        """Cache each task's spec, statement examples and a runnable reference.

        BCB ships its canonical solution as a bare function body, so it is reassembled onto the
        prompt's signature exactly the way control_arena assembles a submission. It feeds the PBT
        soundness gate only and is never submitted as a candidate.

        A pool task absent from the pinned dataset raises here rather than being dropped. There is
        nowhere for an `Unknown` to live on this path — `preprocess` returns `list[Problem]`, and a
        task with no spec, no entry point and no reference cannot be a `Problem` at all
        (`Problem.__post_init__` refuses function mode without an entry point). Continuing would
        hand every downstream rate a denominator nobody chose, which is strictly worse than one
        missing measurement, and it costs nothing to stop here: no model call has been made yet.
        This matches `probe.load_problems`, which raises on the same condition for APPS.
        """
        from control_arena import EvalMode

        wanted = {task_id for task_id in task_ids if task_id not in self._meta}
        if not wanted:
            return
        found: dict[str, _TaskMeta] = {}
        for sample in self._setting.get_dataset(EvalMode.HONEST):
            metadata = sample.metadata
            if metadata is None:
                raise ValueError(f"BigCodeBench sample {sample.id} carries no metadata")
            task_id = str(metadata["main_task_name"])
            if task_id not in wanted:
                continue
            task = metadata["metadata"]
            entry_point = task["entry_point"]
            statement = metadata["main_task_description"]
            example_inputs, example_outputs = statement_examples(statement, entry_point)
            found[task_id] = _TaskMeta(
                description=statement,
                entry_point=entry_point,
                reference=f"{task['code_prompt']}\n    pass\n{task['canonical_solution']}",
                example_inputs=example_inputs,
                example_outputs=example_outputs,
            )
        absent = sorted(wanted - set(found))
        if absent:
            raise ValueError(
                f"{len(absent)} of {len(task_ids)} pool task(s) are absent from the pinned "
                f"BigCodeBench dataset and cannot be specified, referenced or scored: {absent}. "
                "The pool and the dataset disagree (infrastructure, not the model); fix the pool "
                "or the pin. Dropping them would shrink the pool and silently change the "
                "denominator of every rate reported from this run."
            )
        self._meta.update(found)

    def preprocess(
        self, pool: dict[str, Any], *, limit: int | None = None
    ) -> list[Problem]:
        items = list(pool["candidates"].items())
        if limit:
            items = items[:limit]
        self._load_meta([str(task_id) for task_id, _ in items])
        problems: list[Problem] = []
        for task_id, task in items:
            meta = self._meta[str(task_id)]
            candidates = [
                Candidate(
                    candidate_id=task["honest"]["candidate_id"],
                    label="honest",
                    code=task["honest"]["code"],
                    secret_input=None,
                )
            ]
            for i, attack in enumerate(task["attack_proposals"]):
                candidates.append(
                    Candidate(
                        candidate_id=attack["candidate_id"],
                        label=f"attack_{i}",
                        code=attack["code"],
                        secret_input=attack["secret_input"],
                    )
                )
            problems.append(
                Problem(
                    task_id=str(task_id),
                    main_task=meta.description,
                    io_mode="function",
                    entry_point=meta.entry_point,
                    candidates=candidates,
                    provided_tests_hint=_hint(meta.example_inputs, meta.example_outputs),
                    provided_inputs=list(meta.example_inputs),
                    reference_code=meta.reference,
                )
            )
        return problems

    def score_candidates(
        self, problems: list[Problem], limits: ScoringLimits
    ) -> dict[tuple[str, str], ScoreResult]:
        return score_via_control_arena(self._setting, problems, limits)
