"""Check one archived BCB honest replay inside the pinned nested Docker sandbox.

This script is intended to run in the reproduction runner image with the Docker socket
and a writable /results mount. It performs no provider/model calls and never executes
candidate code in the runner container itself.
"""

from __future__ import annotations

from collections import Counter
import argparse
import json
import os
from pathlib import Path
import sys
import time


ARCHIVE = Path("/opt/archive/snapshot")
OUTPUT = Path("/results/real-candidate-check.json")
PREFIX = "azure-terra-pbt-bcb26-s300-v1"
INPUTS = "azure-terra-pbt-bcb26-s300-v1-reviewed-inputs"
TIMEOUT_SECONDS = 120


def exact_grid(result: object, expected_inputs: int) -> dict[tuple[str, int], str]:
    if not isinstance(result, dict) or result.get("ok") is not True or result.get("complete") is not True:
        raise ValueError("saved honest replay was not successful and complete")
    props, records = result.get("props"), result.get("records")
    if not isinstance(props, list) or not props or not all(isinstance(name, str) for name in props):
        raise ValueError("saved replay has no valid property list")
    if not isinstance(records, list):
        raise ValueError("saved replay records are not a list")
    expected_keys = {(name, i) for name in props for i in range(expected_inputs)}
    observed: dict[tuple[str, int], str] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("saved replay contains a malformed record")
        key = (record.get("prop"), record.get("i"))
        if key in observed or key not in expected_keys:
            raise ValueError("saved replay contains a duplicate or out-of-grid record")
        observed[key] = record.get("outcome")
    if set(observed) != expected_keys:
        raise ValueError("saved replay does not contain the full property/input grid")
    if result.get("n_records") != len(expected_keys) or result.get("n_expected") != len(expected_keys):
        raise ValueError("saved replay count fields disagree with its full grid")
    if any(outcome != "pass" for outcome in observed.values()):
        raise ValueError("selected archived honest replay was not all-pass")
    return observed


def select_case(backend, data, spaces):
    from pipeline.protocols.unit_testing import suite_source

    baseline_name = PREFIX + "-baseline"
    baseline_config_path = Path("runs") / baseline_name / "config.json"
    baseline_records_path = Path("runs") / baseline_name / "records.jsonl"
    baseline_config = json.loads(baseline_config_path.read_text(encoding="utf-8"))
    image = baseline_config["params"]["docker_image"]
    records = backend.read_complete(baseline_name, data)
    wrapper = backend.literal("notebooks/azure_pbt_bcb_replication.ipynb", "BCB_WRAPPER_SOURCE")
    replay_root = Path("runs") / (PREFIX + "-study") / "same-input-honest-replay-v1" / baseline_name

    for task in data.tasks:
        candidate = task.attack
        row = records[candidate.candidate_id]
        if row.get("failed") is not False or not row.get("tests_src"):
            continue
        calls = row.get("calls")
        if not isinstance(calls, list) or len(calls) != 1:
            continue
        parsed, parse_error = suite_source(calls[0].get("raw", ""))
        suite = row["tests_src"]
        if parse_error is not None or parsed != suite:
            continue

        replay_path = replay_root / f"{task.task_id}.json"
        if not replay_path.is_file():
            continue
        archived = json.loads(replay_path.read_text(encoding="utf-8"))
        identity = archived.get("identity", {})
        expected_identity = {
            "dataset_sha256": backend.file_hash(backend.DATA),
            "docker_image": image,
            "honest_code_sha256": backend.byte_hash(task.honest.code.encode()),
            "inputs_sha256": backend.object_hash(spaces[candidate.candidate_id]),
            "source_config_sha256": backend.file_hash(baseline_config_path),
            "source_record_sha256": backend.object_hash(row),
            "suite_sha256": backend.byte_hash(suite.encode()),
            "timeout_seconds": TIMEOUT_SECONDS,
            "wrapper_sha256": backend.byte_hash(wrapper.encode()),
        }
        if any(identity.get(key) != value for key, value in expected_identity.items()):
            continue
        if archived.get("failure") is not None:
            continue
        saved = archived.get("result")
        saved_grid = exact_grid(saved, len(spaces[candidate.candidate_id]))
        return task, candidate, suite, saved, saved_grid, image, replay_path, expected_identity
    raise RuntimeError("no archived passing honest baseline suite/replay matched the reviewed inputs")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', help='Immutable locally built unified image ID; default reuses the historical image')
    args = parser.parse_args()
    if args.image:
        import re
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', args.image):
            raise ValueError('--image requires an immutable full local image ID')
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite evidence: {OUTPUT}")
    sys.path.insert(0, str(Path("/opt/runner")))
    sys.path.insert(0, str(ARCHIVE))
    os.chdir(ARCHIVE)
    from pbt_runner import backend

    started = time.time()
    data, spaces = backend.validate_inputs()
    task, attack_candidate, suite, saved, expected_grid, image, replay_path, identity = select_case(backend, data, spaces)
    executed_image = args.image or image.split('@')[-1]

    # Reuse the archived BCB deepcopy wrapper and route all candidate execution to Docker.
    backend.install_sandbox()
    from pipeline import sandbox

    actual = sandbox.run_raw(
        task,
        task.honest.code,
        suite,
        spaces[attack_candidate.candidate_id],
        timeout_s=TIMEOUT_SECONDS,
        isolation=sandbox.Isolation.DOCKER,
        docker_image=executed_image,
    )
    verification_error = None
    try:
        observed_grid = exact_grid(actual, len(spaces[attack_candidate.candidate_id]))
    except (TypeError, ValueError, KeyError) as error:
        observed_grid = {}
        verification_error = f"{type(error).__name__}: {str(error)[:300]}"
    if verification_error is None and observed_grid != expected_grid:
        verification_error = "real Docker run outcomes differ from the saved archived outcomes"

    evidence = {
        "schema_version": 1,
        "status": "passed" if verification_error is None else "failed",
        "provider_calls": 0,
        "candidate_executed_on_runner_host": False,
        "task_id": task.task_id,
        "attack_candidate_id_for_suite_linkage": attack_candidate.candidate_id,
        "suite_source_sha256": identity["suite_sha256"],
        "reviewed_inputs_sha256": identity["inputs_sha256"],
        "docker_image": image,
        "executed_local_image_id": executed_image,
        "timeout_seconds": TIMEOUT_SECONDS,
        "saved_replay_path": str(replay_path),
        "grid_expected": len(expected_grid),
        "grid_observed": len(observed_grid),
        "saved_outcomes": dict(sorted(Counter(expected_grid.values()).items())),
        "observed_outcomes": dict(sorted(Counter(observed_grid.values()).items())),
        "saved_result_sha256": backend.object_hash(saved),
        "observed_result_sha256": backend.object_hash(actual),
        "verification_error": verification_error,
        "elapsed_seconds": round(time.time() - started, 3),
    }
    with OUTPUT.open("x", encoding="utf-8") as stream:
        json.dump(evidence, stream, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps(evidence, sort_keys=True))
    return 0 if verification_error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
