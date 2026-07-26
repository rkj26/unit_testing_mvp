import json

import pytest

from config import Config
from run_artifacts import build_manifest, write_new_manifest


def test_manifest_records_exact_prompts_and_execution_files(tmp_path):
    manifest = build_manifest(Config(task_ids=["BigCodeBench/4"]), ["PBT"])
    assert manifest["schema_version"] == 1
    assert manifest["manifest_sha256"]
    assert "pbt_monitor/v1_baseline" in manifest["prompts"]
    assert manifest["prompts"]["pbt_monitor/v1_baseline"]["content"]
    assert len(manifest["execution_files"]) == 2
    assert manifest["source_files"]
    assert "dirty" in manifest["repository_state"]
    write_new_manifest(tmp_path, manifest)
    assert json.loads((tmp_path / "manifest.json").read_text())["manifest_sha256"]


def test_run_directory_is_immutable(tmp_path):
    manifest = build_manifest(Config(task_ids=["BigCodeBench/4"]), ["PBT"])
    write_new_manifest(tmp_path, manifest)
    with pytest.raises(FileExistsError):
        write_new_manifest(tmp_path, manifest)
