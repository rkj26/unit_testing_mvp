"""Deterministic, provenance-carrying Omar smoke dataset construction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pipeline.data import Candidate, Dataset, Task
from pipeline.protocols.omar_smoke_dataset import build_smoke_dataset


def _dataset(path: Path, backend: str = "apps") -> Dataset:
    tasks = tuple(
        Task(
            task_id=task_id,
            specification=f"Solve {task_id}.",
            io_mode="stdio",
            candidates=(
                Candidate(f"{task_id}_honest", "honest", "print(1)"),
                Candidate(f"{task_id}_attack_0", "attack_0", "print(2)", "secret"),
            ),
            provided_inputs=("1",),
            provided_outputs=("1",),
            statement_visible=(0,),
            reference_solution="print(1)",
        )
        for task_id in ("train-first", "train-second", "test-first")
    )
    dataset = Dataset(
        name="apps_uniform400",
        backend=backend,
        io_mode="stdio",
        tasks=tasks,
        split={"train": ("train-first", "train-second"), "test": ("test-first",)},
        built_from={"pool": "fixture"},
    )
    path.write_text(json.dumps(dataset.to_json()), encoding="utf-8")
    return dataset


def test_default_smoke_selects_first_train_task_and_records_source_digest(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    original = _dataset(source)
    output = tmp_path / "nested" / "smoke.json"

    smoke = build_smoke_dataset(source, output)

    assert [task.task_id for task in smoke.tasks] == ["train-first"]
    assert smoke.split == {"train": ("train-first",), "test": ()}
    assert [candidate.candidate_id for _, candidate in smoke.candidates()] == [
        "train-first_honest", "train-first_attack_0",
    ]
    assert smoke.built_from["smoke_source_dataset"] == original.name
    assert smoke.built_from["smoke_source_sha256"] == hashlib.sha256(
        source.read_bytes()
    ).hexdigest()
    assert smoke.built_from["smoke_task_id"] == "train-first"


def test_explicit_task_keeps_its_original_split(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    _dataset(source)

    smoke = build_smoke_dataset(source, tmp_path / "test-smoke.json", "test-first")

    assert [task.task_id for task in smoke.tasks] == ["test-first"]
    assert smoke.split == {"train": (), "test": ("test-first",)}


def test_existing_output_is_never_overwritten(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    _dataset(source)
    output = tmp_path / "smoke.json"
    output.write_text("keep me", encoding="utf-8")

    with pytest.raises(FileExistsError):
        build_smoke_dataset(source, output)

    assert output.read_text(encoding="utf-8") == "keep me"


def test_only_apps_datasets_are_accepted(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    _dataset(source, backend="bcb")
    output = tmp_path / "smoke.json"

    with pytest.raises(ValueError, match="backend='apps'"):
        build_smoke_dataset(source, output)

    assert not output.exists()
