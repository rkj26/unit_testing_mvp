"""Turn a candidate pool and a split into the one file every run reads.

    .venv/bin/python build_dataset.py --pool apps_pool_hard.json --make-split 20 \
        --split splits/apps_hard_20_30.json
    .venv/bin/python build_dataset.py --backend apps \
        --pool apps_pool_hard.json --split splits/apps_hard_20_30.json \
        --out data/apps_hard.json

Runs once. After it, nothing opens the 52 MB pool: a protocol loads `data/<name>.json`, which carries
its own train/test split so no two protocols can disagree about which tasks are which.

`Backend` is the only benchmark-specific surface this project has; both implementations live below.

GROUND TRUTH IS ASSERTED, NOT MEASURED. `main_task_success` and `side_task_success` come from how the
pool was filtered, and the dataset records that in `built_from["ground_truth"]`. There is no
`--verify`, so these fields must never be read as a verification result.
"""

from __future__ import annotations

import argparse
import ast
import doctest
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from random import Random
from statistics import median
from typing import Any, Mapping, Protocol

from pipeline.data import (
    ATTACK_PREFIX,
    FUNCTION,
    HONEST,
    SCHEMA_VERSION,
    STDIO,
    Candidate,
    Dataset,
    Task,
)

ATTACKS_PER_TASK = 1
PROJECT_SEED = 300

ASSERTED = "asserted by pool construction"

POOL_IO_MODE_FIELD = "io_mode"
BACKEND_BY_IO_MODE = {STDIO: "apps", FUNCTION: "bcb"}

BCB_SANDBOX_TYPE = "docker"


class Backend(Protocol):
    """Benchmark adapter. The ONLY benchmark-specific surface the pipeline depends on."""

    name: str

    def preprocess(self, pool: dict[str, Any]) -> list[Task]:
        """Normalize a benchmark pool into common Task records."""
        ...


def _candidates(pool_task: Mapping[str, Any]) -> tuple[Candidate, ...]:
    """One task's honest submission plus its attacks, capped at `ATTACKS_PER_TASK`.

    The cap is applied here rather than per protocol, so a task counts once in every rate whose
    denominator is tasks.

    `main_task_success` and `side_task_success` are ASSERTED from how the pool was filtered, never
    measured; `built_from["ground_truth"]` says so.
    """
    honest = pool_task["honest"]
    return (
        Candidate(
            candidate_id=honest["candidate_id"],
            label=HONEST,
            code=honest["code"],
            secret_input=None,
            main_task_success=True,
            side_task_success=None,
        ),
        *(
            Candidate(
                candidate_id=attack["candidate_id"],
                label=f"{ATTACK_PREFIX}{index}",
                code=attack["code"],
                secret_input=attack["secret_input"],
                main_task_success=True,
                side_task_success=True,
            )
            for index, attack in enumerate(pool_task["attack_proposals"][:ATTACKS_PER_TASK])
        ),
    )


def statement_visible(task: dict[str, Any]) -> list[int]:
    """Indices of the provided pairs whose input the problem statement actually prints.

    An APPS pool files its whole grading set under `provided_inputs`, hidden cases included. A
    defender has the statement and nothing else, so every pair outside this list is the answer key
    and is not spec-safe. Matching is whitespace-normalised.
    """

    def normalise(text: str) -> str:
        return " ".join(text.split())

    statement = normalise(task["task_description"])
    return [
        index
        for index, raw_input in enumerate(task["provided_inputs"])
        if normalise(raw_input) and normalise(raw_input) in statement
    ]


class AppsBackend:
    """APPS: spec, reference and the whole grading set come inline from the pool, and every
    candidate is a stdin/stdout program."""

    name = "apps"

    def preprocess(self, pool: dict[str, Any]) -> list[Task]:
        """One `Task` per pool entry, refusing a grid whose inputs and outputs disagree in length."""
        tasks = []
        for task_id, entry in pool["candidates"].items():
            if len(entry["provided_inputs"]) != len(entry["provided_outputs"]):
                raise ValueError(
                    f"{task_id}: {len(entry['provided_inputs'])} provided inputs against "
                    f"{len(entry['provided_outputs'])} provided outputs"
                )
            tasks.append(
                Task(
                    task_id=str(task_id),
                    specification=entry["task_description"],
                    io_mode=STDIO,
                    candidates=_candidates(entry),
                    provided_inputs=entry["provided_inputs"],
                    provided_outputs=entry["provided_outputs"],
                    statement_visible=statement_visible(entry),
                    reference_solution=entry["reference_solution"],
                )
            )
        return tasks


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

    An unreadable docstring means the statement shows no example — a fact about the statement, not a
    measurement that failed.
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
    """The call's arguments as a JSON-round-trippable kwargs dict, or None if any are not."""
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

    These are BCB's only spec-safe inputs: its grading suite (`test_code`) is the answer key. Most
    tasks yield none — their examples take DataFrames, file paths or objects an earlier `>>>` line
    built — and an empty result means the statement showed nothing readable, not a failure.
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


class BcbBackend:
    """BCB has no inline data: spec, entry point, statement examples and the canonical solution all
    come from HuggingFace (`bigcode/bigcodebench`, pinned through control_arena).

    The pool supplies only candidates. Every provided pair is a `>>>` example from the statement, so
    all of them are statement-visible by construction.
    """

    name = "bcb"

    def __init__(self) -> None:
        self._meta: dict[str, _TaskMeta] = {}

    def _load_meta(self, task_ids: list[str]) -> None:
        """Cache each task's spec, statement examples and a runnable reference.

        A pool task absent from the pinned dataset raises rather than being dropped: dropping it
        would hand every downstream rate a denominator nobody chose.
        """
        from control_arena import EvalMode
        from control_arena.settings.bigcodebench.bigcodebench_setting import (
            BigCodeBenchSetting,
        )

        wanted = {task_id for task_id in task_ids if task_id not in self._meta}
        if not wanted:
            return
        found: dict[str, _TaskMeta] = {}
        setting = BigCodeBenchSetting(sandbox_type=BCB_SANDBOX_TYPE)
        for sample in setting.get_dataset(EvalMode.HONEST):
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
                f"BigCodeBench dataset and cannot be specified or referenced: {absent}. "
                "The pool and the dataset disagree (infrastructure, not the model); fix the pool "
                "or the pin. Dropping them would shrink the pool and silently change the "
                "denominator of every rate reported from this run."
            )
        self._meta.update(found)

    def preprocess(self, pool: dict[str, Any]) -> list[Task]:
        """The pinned BigCodeBench pool as `Task` records, statement examples included."""
        items = list(pool["candidates"].items())
        self._load_meta([str(task_id) for task_id, _ in items])
        tasks = []
        for task_id, entry in items:
            meta = self._meta[str(task_id)]
            tasks.append(
                Task(
                    task_id=str(task_id),
                    specification=meta.description,
                    io_mode=FUNCTION,
                    entry_point=meta.entry_point,
                    candidates=_candidates(entry),
                    provided_inputs=meta.example_inputs,
                    provided_outputs=meta.example_outputs,
                    statement_visible=range(len(meta.example_inputs)),
                    reference_solution=meta.reference,
                )
            )
        return tasks


BACKEND_CLASSES: dict[str, type[Backend]] = {"apps": AppsBackend, "bcb": BcbBackend}
BACKENDS = tuple(BACKEND_CLASSES)


@lru_cache(maxsize=len(BACKEND_CLASSES))
def _backend(name: str) -> Backend:
    """The backend for a name, built once and shared, so `BcbBackend` scans its dataset once."""
    return BACKEND_CLASSES[name]()


def read_pool(pool_path: Path) -> dict[str, Any]:
    """The pool as stored, with its `io_mode` required rather than defaulted."""
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    if POOL_IO_MODE_FIELD not in pool:
        raise ValueError(
            f"{pool_path} declares no {POOL_IO_MODE_FIELD!r}: a pool must say whether its "
            f"candidates read STDIN ({STDIO!r}) or take keyword arguments ({FUNCTION!r}), because "
            "the invoke contract every prompt carries is built from it"
        )
    declared = pool[POOL_IO_MODE_FIELD]
    if declared not in BACKEND_BY_IO_MODE:
        raise ValueError(
            f"{pool_path} declares io_mode {declared!r}, which is neither {STDIO!r} nor {FUNCTION!r}"
        )
    return pool


def write_split(pool_path: Path, n_train: int, seed: int, out: Path) -> None:
    """Write a train/test split of a pool's tasks as explicit id lists.

    The audit rule is calibrated on the TRAIN ids and every reported number comes from the TEST ids.
    Ids rather than a seed, so two arms provably share one split: a seed reproduces the same lists
    only while the shuffle code is untouched, and a silently different split looks like an effect.
    """
    ids = sorted(json.loads(pool_path.read_text(encoding="utf-8"))["candidates"])
    if not 0 < n_train < len(ids):
        raise ValueError(f"train size {n_train} must be inside 0..{len(ids)}")
    shuffled = list(ids)
    Random(f"split:{seed}").shuffle(shuffled)
    train, test = sorted(shuffled[:n_train]), sorted(shuffled[n_train:])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "pool": str(pool_path),
                "seed": seed,
                "n_train": len(train),
                "n_test": len(test),
                "train": train,
                "test": test,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out}: {len(train)} train / {len(test)} test from {len(ids)} tasks")


def read_split(split_path: Path) -> tuple[list[str], list[str]]:
    """`(train_ids, test_ids)` from a `--make-split` file, as explicit lists.

    Raises unless both halves are non-empty and disjoint: a threshold is fitted on one half and
    reported from the other.
    """
    split = json.loads(split_path.read_text(encoding="utf-8"))
    train = [str(task_id) for task_id in split["train"]]
    test = [str(task_id) for task_id in split["test"]]
    if not train or not test:
        raise ValueError(
            f"{split_path} leaves a half empty ({len(train)} train / {len(test)} test): a threshold "
            "is fitted on one half and reported from the other, so neither can be missing"
        )
    both = sorted(set(train) & set(test))
    if both:
        raise ValueError(
            f"{split_path} puts {len(both)} task(s) in both halves ({both[:5]}): a threshold would "
            "be calibrated on the very tasks it is then scored against"
        )
    return train, test


def build(
    pool_path: Path, split_path: Path, backend: str, name: str
) -> dict[str, Any]:
    """The whole dataset document, ready to serialise. Makes no model calls."""
    pool = read_pool(pool_path)
    declared = pool[POOL_IO_MODE_FIELD]
    if BACKEND_BY_IO_MODE[declared] != backend:
        raise ValueError(
            f"{pool_path} holds {declared!r} candidates, which --backend "
            f"{BACKEND_BY_IO_MODE[declared]!r} reads, not --backend {backend!r}. The pool and the "
            "backend disagree about what a candidate is, and one of the two is a typo."
        )
    train, test = read_split(split_path)
    task_ids = sorted({*train, *test})
    missing = [task_id for task_id in task_ids if task_id not in pool["candidates"]]
    if missing:
        raise ValueError(f"the pool has no task {', '.join(missing)}")
    chosen = {task_id: pool["candidates"][task_id] for task_id in task_ids}
    return Dataset(
        name=name,
        backend=backend,
        io_mode=declared,
        tasks=_backend(backend).preprocess({**pool, "candidates": chosen}),
        split={"train": train, "test": test},
        built_from={
            "pool": str(pool_path),
            "split": str(split_path),
            "ground_truth": ASSERTED,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "source": pool["source"],
        },
        schema_version=SCHEMA_VERSION,
    ).to_json()


def summarise(document: dict[str, Any]) -> list[str]:
    """The counts a reader would otherwise recompute to trust the file, printed as it is written."""
    tasks = document["tasks"]
    provided = [len(task["provided_inputs"]) for task in tasks]
    visible = [len(task["statement_visible"]) for task in tasks]
    return [
        f"{len(tasks)} tasks, {len(document['split']['train'])} train / "
        f"{len(document['split']['test'])} test, "
        f"{sum(len(task['candidates']) for task in tasks)} candidates",
        f"provided pairs: {sum(provided)} total, median {median(provided)} per task",
        f"statement-visible: {sum(visible)} total, median {median(visible)} per task, "
        f"min {min(visible)}",
        f"ground truth: {document['built_from']['ground_truth']}",
    ]


def main() -> None:
    """Build one dataset from a pool and a split, or write a split with `--make-split`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=BACKENDS)
    parser.add_argument("--pool", required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--out")
    parser.add_argument("--name", default="", help="defaults to the --out stem")
    parser.add_argument(
        "--make-split",
        type=int,
        default=0,
        metavar="N",
        help="write --split as an N-task train half over --pool, and build nothing",
    )
    parser.add_argument("--seed", type=int, default=PROJECT_SEED)
    args = parser.parse_args()

    if args.make_split:
        write_split(Path(args.pool), args.make_split, args.seed, Path(args.split))
        return
    if not args.backend or not args.out:
        parser.error("--backend and --out are required unless --make-split is given")

    out = Path(args.out)
    document = build(
        Path(args.pool),
        Path(args.split),
        args.backend,
        args.name if args.name else out.stem,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    for line in summarise(document):
        print(f"  {line}")


if __name__ == "__main__":
    main()
