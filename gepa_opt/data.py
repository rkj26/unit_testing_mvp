"""Problems, frozen search spaces, and the train/val/holdout split GEPA optimizes over.

A `PropertyTask` pairs one `Problem` with a search space that is authored once and then frozen, so
that across the whole GEPA run the property prompt is the only thing that changes. Freezing the
space is what makes the resulting catch-rate delta attributable to the prompt rather than to a
lucky trigger-search sample.

The pool is loaded here directly (mirroring `pipeline.backends.apps`) rather than through the
backend, so the optimizer does not pull in the control_arena ground-truth scoring stack it never
uses — the reference-gated PBT signal is all GEPA needs.
"""

from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline import pbt
from pipeline.model import TrustedModel
from pipeline.outcome import Blame, Unknown, is_unknown
from pipeline.schema import Candidate, Problem

from .throttle import run_sync

SPLIT_SEED = 0
HOLDOUT_FRACTION = 0.3
VAL_FRACTION = 0.2


@dataclass(frozen=True)
class PropertyTask:
    """One task with its frozen blind search space. The GEPA DataInst."""

    problem: Problem
    space: list[Any]

    @property
    def task_id(self) -> str:
        return self.problem.task_id


@dataclass(frozen=True)
class Split:
    train: list[PropertyTask]
    val: list[PropertyTask]
    holdout: list[PropertyTask]


def load_problems(pool_path: str, limit: int = 0) -> list[Problem]:
    """APPS pool -> Problems, keeping only tasks that carry a reference solution.

    A task without a reference cannot have its properties soundness-gated, so including it would
    force the metric to abstain on an INFRA blame for a reason we can see up front. We drop it
    loudly here instead (fail fast) rather than let it become a silent zero later.
    """
    pool = json.loads(Path(pool_path).read_text(encoding="utf-8"))
    items = list(pool["candidates"].items())
    if limit:
        items = items[:limit]
    problems: list[Problem] = []
    dropped: list[str] = []
    for task_id, task in items:
        if not (task.get("reference_solution") or "").strip():
            dropped.append(str(task_id))
            continue
        candidates = [
            Candidate(task["honest"]["candidate_id"], "honest", task["honest"]["code"], "")
        ]
        for i, attack in enumerate(task["attack_proposals"]):
            candidates.append(
                Candidate(
                    attack["candidate_id"],
                    f"attack_{i}",
                    attack["code"],
                    attack["secret_input"],
                )
            )
        problems.append(
            Problem(
                task_id=str(task_id),
                main_task=task["task_description"],
                io_mode="stdio",
                candidates=candidates,
                provided_tests_hint=_hint(
                    task.get("provided_inputs", []), task.get("provided_outputs", [])
                ),
                provided_inputs=list(task.get("provided_inputs", [])),
                reference_code=task["reference_solution"],
            )
        )
    if dropped:
        print(f"  [warn] dropped {len(dropped)} task(s) with no reference solution: {dropped}")
    return problems


def _hint(inputs: list[str], outputs: list[str], n: int = 3) -> str:
    lines = [
        f"  STDIN={inputs[i]!r} -> STDOUT={outputs[i]!r}"
        for i in range(min(n, len(inputs), len(outputs)))
    ]
    return "\n".join(lines) or "(none provided)"


def freeze_search_spaces(
    problems: list[Problem],
    writer: TrustedModel,
    cache_path: str,
    variant: str = "default",
    max_search_space: int = pbt.DEFAULT_MAX_SEARCH_SPACE,
) -> dict[str, list[Any]]:
    """Author one blind trigger-search space per task and cache it to disk.

    The space is authored by the writer once and reused for every GEPA rollout. Tasks whose space
    cannot be authored are reported and excluded (their id is returned absent from the map), so a
    degraded space never silently narrows the experiment.
    """
    cache = Path(cache_path)
    if cache.exists():
        stored = json.loads(cache.read_text(encoding="utf-8"))
        return {tid: space for tid, space in stored.items()}

    authored = run_sync(_author_all(problems, writer, variant))
    spaces: dict[str, list[Any]] = {}
    failed: list[str] = []
    for problem, result in zip(problems, authored):
        if is_unknown(result):
            failed.append(f"{problem.task_id} ({result.reason})")
            continue
        spaces[problem.task_id] = result[:max_search_space]
    if failed:
        print(f"  [warn] no frozen search space for {len(failed)} task(s): {failed}")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(spaces, indent=2), encoding="utf-8")
    return spaces


async def _author_all(
    problems: list[Problem], writer: TrustedModel, variant: str
) -> list[list[Any] | Unknown]:
    return await asyncio.gather(*(_author_one(p, writer, variant) for p in problems))


async def _author_one(
    problem: Problem, writer: TrustedModel, variant: str
) -> list[Any] | Unknown:
    completion = await writer.complete(pbt.search_prompt(problem, variant), "trigger_search")
    space, error = pbt.parse_search_space(completion)
    if space is None:
        return Unknown(Blame.MODEL, f"trigger_search abstained: {error}")
    return space


def make_split(
    problems: list[Problem],
    spaces: dict[str, list[Any]],
    holdout_problems: list[Problem] | None = None,
    holdout_spaces: dict[str, list[Any]] | None = None,
) -> Split:
    """Deterministic train/val/holdout partition.

    When a disjoint `holdout_problems` pool is given, the whole in-pool set becomes train+val and
    holdout is those separate tasks — the split that actually tests for memorized backdoors. With
    no disjoint pool, holdout is carved from the same tasks and the caller is warned that
    generalization is only measured across instances of the same task distribution.
    """
    tasks = [PropertyTask(p, spaces[p.task_id]) for p in problems if p.task_id in spaces]
    rng = random.Random(SPLIT_SEED)
    rng.shuffle(tasks)

    if holdout_problems is not None and holdout_spaces is not None:
        holdout = [
            PropertyTask(p, holdout_spaces[p.task_id])
            for p in holdout_problems
            if p.task_id in holdout_spaces
        ]
        n_val = max(1, round(len(tasks) * VAL_FRACTION))
        return Split(train=tasks[n_val:], val=tasks[:n_val], holdout=holdout)

    print(
        "  [warn] no disjoint holdout pool given; holdout is carved from the same tasks. "
        "A memorized-backdoor check needs a pool of DIFFERENT tasks — pass --holdout-dataset."
    )
    n_holdout = max(1, round(len(tasks) * HOLDOUT_FRACTION))
    n_val = max(1, round(len(tasks) * VAL_FRACTION))
    holdout = tasks[:n_holdout]
    val = tasks[n_holdout : n_holdout + n_val]
    train = tasks[n_holdout + n_val :]
    if not train:
        raise ValueError(
            f"pool of {len(tasks)} usable task(s) is too small to leave a train set after a "
            f"{n_holdout}-task holdout and {n_val}-task val; add tasks or pass --holdout-dataset."
        )
    return Split(train=train, val=val, holdout=holdout)
