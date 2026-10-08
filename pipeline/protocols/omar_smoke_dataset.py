"""Build a deterministic one-task APPS dataset for a small Omar smoke run."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ..data import Dataset


def build_smoke_dataset(
    source: str | Path,
    output: str | Path,
    task_id: str | None = None,
) -> Dataset:
    """Serialize one APPS task and both candidates without overwriting an artifact.

    By default, select the first task in the source dataset's train order. An explicit
    ``task_id`` may select either split; the selected task remains in its original half.
    The source file digest is recorded in ``built_from`` for provenance.
    """
    source_path = Path(source)
    output_path = Path(output)
    if source_path.resolve() == output_path.resolve():
        raise ValueError("smoke dataset output must not be the source dataset")

    source_bytes = source_path.read_bytes()
    original = Dataset.load(source_path)
    if original.backend != "apps":
        raise ValueError(f"Omar smoke datasets require backend='apps', got {original.backend!r}")

    if task_id is None:
        train_tasks = original.train
        if not train_tasks:
            raise ValueError(f"{original.name} has no train task to use for a smoke dataset")
        selected = train_tasks[0]
    else:
        selected = original.task(str(task_id))

    source_split = original.split_of(selected.task_id)
    split = {
        half: (selected.task_id,) if half == source_split else ()
        for half in original.split
    }
    smoke = Dataset(
        name=f"{original.name}_smoke_{selected.task_id}",
        backend=original.backend,
        io_mode=original.io_mode,
        tasks=(selected,),
        split=split,
        built_from={
            **original.built_from,
            "smoke_source_dataset": original.name,
            "smoke_source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "smoke_task_id": selected.task_id,
        },
        schema_version=original.schema_version,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(smoke.to_json(), indent=2) + "\n"
    with output_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(serialized)
    return Dataset.load(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/apps_uniform400.json"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--task-id")
    args = parser.parse_args()
    dataset = build_smoke_dataset(args.source, args.out, args.task_id)
    candidate_ids = [candidate.candidate_id for _, candidate in dataset.candidates()]
    print(f"Wrote {args.out}: task {dataset.tasks[0].task_id}, candidates {candidate_ids}")


if __name__ == "__main__":
    main()
