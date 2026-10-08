"""Generators run in isolated copies and preserve exact original team-cell payloads."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
POOL = "u400"
NAME = "results_bcbas.ipynb" if POOL == "bcbas" else "results_uniform400.ipynb"
EXPECTED_TEAM_CELLS = 52 if POOL == "bcbas" else 47
MARKERS = ("### Omar A · selected-model initial run", "omar_initial = omar.run()",
           "### Omar B/C continuation", "### Omar B/C/D continuation",
           "omar_arms = omar.continue_run()")


def _omar(cell):
    return any(marker in "".join(cell["source"]) for marker in MARKERS)


def _raw_cells(text):
    position = text.index("[", text.index('"cells"')) + 1
    decoder = json.JSONDecoder()
    raw = []
    while True:
        while text[position].isspace() or text[position] == ",":
            position += 1
        if text[position] == "]":
            return raw
        _value, end = decoder.raw_decode(text, position)
        raw.append(text[position:end])
        position = end


def _copy(tmp_path, *, git=True):
    # Copy only generator assets, not runs, credentials, or the real working tree.
    isolated = tmp_path / "copy"
    notebooks = isolated / "notebooks"
    notebooks.mkdir(parents=True)
    for name in ("build_results.py", "OMAR_ANALYSIS_CELL.md"):
        shutil.copyfile(ROOT / "notebooks" / name, notebooks / name)
    baseline_bytes = subprocess.check_output(
        ["git", "show", f"HEAD:notebooks/{NAME}"], cwd=ROOT)
    (notebooks / NAME).write_bytes(baseline_bytes)
    if git:
        subprocess.run(["git", "init", "-q"], cwd=isolated, check=True, capture_output=True)
        subprocess.run(["git", "add", f"notebooks/{NAME}"], cwd=isolated, check=True, capture_output=True)
        subprocess.run(["git", "-c", "user.name=Notebook Fixture",
                        "-c", "user.email=notebook@example.invalid",
                        "-c", "core.hooksPath=.no-hooks", "commit", "-qm", "baseline"],
                       cwd=isolated, check=True, capture_output=True)
    return isolated, baseline_bytes.decode("utf-8")


def _build(isolated, *args, env=None):
    return subprocess.run([sys.executable, "notebooks/build_results.py", POOL, *args],
                          cwd=isolated, env=env, capture_output=True, text=True)


def test_rebuild_preserves_every_original_team_cell_byte_and_clears_only_omar(tmp_path):
    isolated, baseline_text = _copy(tmp_path)
    before = (ROOT / "notebooks" / NAME).read_bytes()
    baseline = json.loads(baseline_text)
    completed = _build(isolated)
    assert completed.returncode == 0, completed.stderr
    generated_text = (isolated / "notebooks" / NAME).read_bytes().decode("utf-8")
    generated = json.loads(generated_text)
    team = [cell for cell in generated["cells"] if not _omar(cell)]
    baseline_team = [cell for cell in baseline["cells"] if not _omar(cell)]
    assert len(team) == len(baseline_team) == EXPECTED_TEAM_CELLS
    assert team == baseline_team
    raw_team = [raw for cell, raw in zip(generated["cells"], _raw_cells(generated_text)) if not _omar(cell)]
    raw_baseline = [raw for cell, raw in zip(baseline["cells"], _raw_cells(baseline_text)) if not _omar(cell)]
    assert raw_team == raw_baseline
    checked_in = json.loads(before)
    checked_in_raw = before.decode("utf-8")
    assert [raw for cell, raw in zip(checked_in["cells"], _raw_cells(checked_in_raw))
            if not _omar(cell)] == raw_baseline
    assert generated["metadata"] == baseline["metadata"]
    additions = [cell for cell in generated["cells"] if _omar(cell)]
    assert len(additions) == 4
    assert all(cell["execution_count"] is None and cell["outputs"] == []
               for cell in additions if cell["cell_type"] == "code")
    assert before == (ROOT / "notebooks" / NAME).read_bytes()


def test_intentional_team_generator_edit_requires_explicit_preservation_opt_out(tmp_path):
    isolated, _baseline = _copy(tmp_path)
    script = isolated / "notebooks" / "build_results.py"
    text = script.read_text(encoding="utf-8")
    script.write_text(text.replace("# Can a trusted model catch backdoors by writing tests?",
                                   "# Intentional fixture edit"), encoding="utf-8")
    before = (isolated / "notebooks" / NAME).read_bytes()
    blocked = _build(isolated)
    assert blocked.returncode != 0 and "source mismatch" in blocked.stderr
    assert before == (isolated / "notebooks" / NAME).read_bytes()
    clean = _build(isolated, "--no-preserve-team")
    assert clean.returncode == 0, clean.stderr
    assert "preservation explicitly disabled" in clean.stderr
    generated = json.loads((isolated / "notebooks" / NAME).read_text(encoding="utf-8"))
    assert all(cell["execution_count"] is None and cell["outputs"] == []
               for cell in generated["cells"] if cell["cell_type"] == "code")
    assert "# Intentional fixture edit" in "".join(generated["cells"][0]["source"])


@pytest.mark.parametrize("unavailable", ["no_checkout", "git_missing"])
def test_missing_git_baseline_warns_and_generates_without_claiming_cached_evidence(tmp_path, unavailable):
    isolated, _baseline = _copy(tmp_path, git=False)
    environment = dict(os.environ)
    if unavailable == "git_missing":
        environment["PATH"] = ""
    completed = _build(isolated, env=environment)
    assert completed.returncode == 0, completed.stderr
    assert "Git baseline unavailable" in completed.stderr
    assert "no preservation claim" in completed.stderr
    generated = json.loads((isolated / "notebooks" / NAME).read_text(encoding="utf-8"))
    assert all(cell["execution_count"] is None and cell["outputs"] == []
               for cell in generated["cells"] if cell["cell_type"] == "code")
