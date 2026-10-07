"""Omar's multi-turn arm adapter for the shared APPS and BigCodeBench notebooks.

This module reads an existing UnitTesting arm, replays its saved tests in the normal
Docker sandbox, and starts the registered SecondRevision protocol. It changes no
other arm's scores or files. The replay worker uses no model API calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .. import launch, sandbox
from ..data import Dataset, load_records
from .second_revision import SecondRevision
from .test_repair import feedback_summary
from .unit_testing import UnitTesting, spaces_from, suite_source


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hash_object(value: object) -> str:
    return _sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _save_once(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, sort_keys=True, indent=2) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != raw:
            raise ValueError(f"existing artifact differs: {path}")
        return
    with path.open("x", encoding="utf-8") as stream:
        stream.write(raw)
        stream.flush()


def freeze_bundle(request_path: Path) -> Path:
    """Replay each saved baseline suite once; write an immutable source bundle."""
    request = json.loads(request_path.read_text(encoding="utf-8"))
    baseline = UnitTesting.attach(request["baseline_run"])
    data = Dataset.load(baseline.data_path)
    if baseline.pending():
        raise ValueError("baseline has not scored every candidate")
    paths = {
        "dataset_sha256": Path(baseline.data_path),
        "source_config_sha256": baseline.config_path,
        "source_records_sha256": baseline.records_path,
        "input_records_sha256": Path("runs") / baseline.triggers / "records.jsonl",
    }
    for key, path in paths.items():
        if _sha(path.read_bytes()) != request[key]:
            raise ValueError(f"{key} changed since feedback was requested")
    spaces, unusable = spaces_from(baseline.triggers, data)
    if unusable:
        raise ValueError(f"{len(unusable)} candidate(s) lack usable fixed inputs")
    rows = load_records(baseline.run_name)
    by_id = {row["candidate_id"]: row for row in rows}
    wanted = {candidate.candidate_id for _, candidate in data.candidates()}
    if len(rows) != len(wanted) or set(by_id) != wanted:
        raise ValueError("baseline has duplicate or missing candidates")
    bundle = {"schema_version": 1, "candidates": {},
              **{key: request[key] for key in paths}}
    output = Path(request["bundle"])
    for task, candidate in data.candidates():
        cid = candidate.candidate_id
        row = by_id[cid]
        raw = row["calls"][0]["raw"] if row["calls"] else ""
        source, error = suite_source(raw)
        identity = {
            "source_record_sha256": _hash_object(row),
            "inputs_sha256": _hash_object(spaces[cid]),
            "code_sha256": _sha(candidate.code.encode()),
            "suite_sha256": None if source is None else _sha(source.encode()),
        }
        # Candidate IDs come from dataset artifacts, not a filesystem namespace.
        cache = output.parent / "source-feedback" / f"{_sha(cid.encode())}.json"
        if cache.exists():
            saved = json.loads(cache.read_text(encoding="utf-8"))
            if saved["identity"] != identity:
                raise ValueError(f"cached feedback source changed for {cid}")
            result = saved["result"]
        else:
            result = None
            if source is not None:
                try:
                    result = sandbox.run_raw(
                        task, candidate.code, source, spaces[cid],
                        timeout_s=baseline.sandbox_seconds,
                        isolation=sandbox.Isolation.DOCKER,
                        docker_image=baseline.docker_image,
                    )
                except Exception as exc:
                    result = {"ok": False, "complete": False, "props": [],
                              "records": [], "n_records": 0, "n_expected": 0,
                              "error": f"{type(exc).__name__}: {exc}"[:300]}
            _save_once(cache, {"identity": identity, "result": result})
        if raw:
            feedback_summary(result, error, source, spaces[cid])
        bundle["candidates"][cid] = {**identity, "result": result}
    _save_once(output, bundle)
    return output


def advance(baseline: UnitTesting, *, prefix: str, launch_paid: bool = False,
            include_no_feedback: bool = False) -> tuple[str, dict[str, SecondRevision]]:
    """Advance one stage and return finished revisions for the notebook's ARMS dict.

    Call this same function again after an unfinished stage. Running revisions needs
    ``launch_paid=True``. All stages reuse the original baseline and trigger inputs.
    """
    if type(baseline) is not UnitTesting:
        raise TypeError("baseline must be an existing UnitTesting arm")
    if not prefix or not prefix.replace("-", "").replace("_", "").isalnum():
        raise ValueError("prefix must contain letters, numbers, dashes or underscores")
    if baseline.code_visible is not True or baseline.n_tests != 10 or baseline.runs != 1:
        raise ValueError("baseline must have code visible, one run, and ten tests")
    if baseline.pending():
        return f"Finish existing baseline {baseline.run_name} first", {}
    folder = Path("runs") / f"{prefix}-source-feedback"
    bundle = folder / "source-bundle.json"
    request_path = folder / "request.json"
    paths = {"dataset_sha256": Path(baseline.data_path),
             "source_config_sha256": baseline.config_path,
             "source_records_sha256": baseline.records_path,
             "input_records_sha256": Path("runs") / baseline.triggers / "records.jsonl"}
    request = {"baseline_run": baseline.run_name, "bundle": str(bundle),
               **{key: _sha(path.read_bytes()) for key, path in paths.items()}}
    _save_once(request_path, request)
    if not bundle.exists():
        if not launch.alive(f"{prefix}-source-feedback"):
            launch.launch(f"{prefix}-source-feedback",
                          [sys.executable, "-m", "pipeline.protocols.omar_shared",
                           "--freeze", str(request_path)])
        return f"Feedback replay running in runs/{prefix}-source-feedback; rerun this cell when it finishes", {}
    saved = json.loads(bundle.read_text(encoding="utf-8"))
    if any(saved[key] != value for key, value in request.items() if key.endswith("sha256")):
        raise ValueError("source bundle dependencies changed")
    bundle_hash = _sha(bundle.read_bytes())
    arms = {}
    for label, visible in (("multi-turn + feedback", True),
                           ("multi-turn without feedback", False)):
        if not visible and not include_no_feedback:
            continue
        name = f"{prefix}-{'feedback' if visible else 'no-feedback'}"
        arm = SecondRevision(
            run_name=name, baseline_run=baseline.run_name, source_bundle=str(bundle),
            source_bundle_sha256=bundle_hash, feedback_visible=visible,
            max_candidates=baseline.total, data=baseline.data_path, model=baseline.model,
            triggers=baseline.triggers, n_tests=10, code_visible=False,
            test_gen_prompt="traceable_v1", resolve="with",
            reasoning=baseline.reasoning.value,
            max_tokens=baseline.max_tokens, call_seconds=baseline.call_seconds,
            sandbox_seconds=baseline.sandbox_seconds, docker_image=baseline.docker_image,
            seed=baseline.seed, cache=False,
        )
        if arm.config_path.exists():
            saved_config = json.loads(arm.config_path.read_text(encoding="utf-8"))
            if saved_config != arm.config():
                raise ValueError(f"{name} already exists with different settings")
        if arm.pending():
            if not launch_paid:
                return f"{name} needs paid calls; set launch_paid=True after reviewing the bundle", {}
            arm.run(wait=False)
            return f"{name} is running; rerun this cell when it finishes", {}
        if len(arm.get_records()) != arm.total:
            raise ValueError(f"{name} has duplicate or unexpected records")
        arms[label] = arm
    return "Multi-turn arm complete", arms


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze Omar's existing-baseline feedback")
    parser.add_argument("--freeze", type=Path, required=True)
    args = parser.parse_args()
    print(freeze_bundle(args.freeze))


if __name__ == "__main__":
    main()
