from types import SimpleNamespace

import evaluator as evaluator_module
from evaluator import Evaluator


class _Sample:
    scores = None

    def __init__(self, sample_id: str, code: str):
        self.id = sample_id
        self.messages = [code]

    def model_dump(self, mode):
        assert mode == "json"
        return {"id": self.id, "messages": self.messages}


def test_legacy_sample_artifacts_use_safe_unique_paths_and_atomic_writes(
    tmp_path, monkeypatch
):
    samples = [
        _Sample("../task/a", "def solve(): return 1\n"),
        _Sample("../../task/a", "def solve(): return 2\n"),
    ]
    monkeypatch.setattr(
        evaluator_module,
        "extract_submission",
        lambda messages: SimpleNamespace(code=messages[0], secret_input=None),
    )

    Evaluator._save_generated_code(
        object(),
        "HONEST",
        "TM",
        [SimpleNamespace(samples=samples)],
        str(tmp_path),
    )

    sample_root = tmp_path / "TM" / "honest"
    sample_dirs = sorted(path for path in sample_root.iterdir() if path.is_dir())
    assert len(sample_dirs) == 2
    assert sample_dirs[0].name != sample_dirs[1].name
    assert all(".." not in path.name and "/" not in path.name for path in sample_dirs)
    assert all((path / "sample.json").is_file() for path in sample_dirs)
    assert all((path / "submission.py").is_file() for path in sample_dirs)
    assert list(tmp_path.rglob("*.tmp-*")) == []
