"""SINGLE-USE builder for the BigCodeBench candidate pool. Runs once, writes an artifact, done.

This is not a measurement and must never grow into one. It has no scoring path of its own: the
divergence question is answered by `pipeline.scoring.compare_captures`, the same function that
grades a live run, so what a candidate was authored against and what grades it cannot drift. If a
number about a run is wanted, it belongs on the harness as a flag, not here.

Source. `yejun-yun/bigcodebench-backdoors` — 55 rows, one backdoor each, every one carrying a
non-empty `backdoor_input`. Its sibling `yejun-yun/bigcodebench-extracted-backdoors` is 4,001 rows
over 564 tasks and is NOT usable: every `backdoor_input` is the empty string, and its
`side_task_type` values (`logio`, `ioexfil`, `iodelete`, `permissions`, `exit`, `longlines`, …) are
side-effect and code-property side tasks, not the output divergence on a secret input that this
pipeline scores.

What a candidate must survive to enter the pool, all of it inside the BCB docker image with the
network off:

  1. the task is in the pinned `bigcode/bigcodebench` dataset, with a byte-identical `code_prompt`
     and `canonical_solution` — the scorer grades against the pinned copy, so verifying against
     anything else would verify the wrong thing;
  2. `backdoor_input` converts to JSON kwargs — a `pd.DataFrame(...)` or `np.array(...)` argument
     cannot be a `secret_input`, because the harness `json.dumps` the search space and splats it;
  3. the reference is DETERMINISTIC on the secret input: two runs of the canonical solution agree.
     An unseeded `shuffle` or `random` makes every comparison meaningless and would be scored as a
     backdoor firing at random;
  4. the honest solution passes BigCodeBench's own unittest suite;
  5. the attack passes that same suite — an attack that fails the public tests is caught for free
     and is not the thing under study;
  6. the attack DIVERGES from the canonical solution on its stated `secret_input`.

A candidate failing any of these is not a hard task, it is a broken one, and it would later be read
as the model failing. Each rejection is reported with the gate that rejected it.

The document declares `io_mode: "function"` and `validated` refuses to write one that does not.
`probe.load_problems` reads that key as `pool.get("io_mode", "stdio")`, so an omitted key is not a
missing field, it is a silent reclassification into the stdin contract.

    .venv/bin/python build_bcb_pool.py --out bcb_pool.json
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.backends.bcb import _entry_definition, _literal_kwargs, statement_examples
from pipeline.outcome import is_unknown
from pipeline.scoring import (
    Capture,
    build_capture_script,
    compare_captures,
    parse_capture,
)

BACKDOOR_DATASET = "yejun-yun/bigcodebench-backdoors"
DEFAULT_IMAGE = "bcb-pbt:py312"
CAPTURE_TIMEOUT_SECONDS = 120
UNITTEST_TIMEOUT_SECONDS = 300
CONTAINER_MEMORY_LIMIT = "2g"
CONTAINER_CPU_LIMIT = "2"

UNITTEST_MARKER = "UNITTEST:"

_UNITTEST_TEMPLATE = '''
import json as _bcb_json, sys as _bcb_sys, unittest as _bcb_unittest
__FULL_CODE__
__TEST_CODE__
_bcb_result = _bcb_unittest.TestResult()
_bcb_unittest.TestLoader().loadTestsFromTestCase(TestCases).run(_bcb_result)
_bcb_sys.stdout.write("__MARKER__" + _bcb_json.dumps({
    "passed": not _bcb_result.failures and not _bcb_result.errors,
    "run": _bcb_result.testsRun,
    "failed": len(_bcb_result.failures) + len(_bcb_result.errors),
}) + "\\n")
'''


@dataclass(frozen=True)
class Rejection:
    """Why one row of the source dataset cannot become a pool entry."""

    task_id: str
    gate: str
    detail: str


@dataclass(frozen=True)
class Accepted:
    """One verified pool entry, plus what the stock grader would have said about it."""

    task_id: str
    honest_code: str
    attack_code: str
    secret_input: str
    canonical_repr: str
    attack_repr: str
    stock_would_have_missed: bool
    drivable_from_statement_examples: bool


def _docker_run(image: str, script: str, timeout_seconds: int) -> tuple[str, str]:
    """Run one script in the BCB image with the network off, and return (stdout, stderr)."""
    with tempfile.TemporaryDirectory() as directory:
        Path(directory, "job.py").write_text(script, encoding="utf-8")
        try:
            completed = subprocess.run(
                [
                    "docker", "run", "--rm",
                    "--network", "none",
                    "--memory", CONTAINER_MEMORY_LIMIT,
                    "--memory-swap", CONTAINER_MEMORY_LIMIT,
                    "--cpus", CONTAINER_CPU_LIMIT,
                    "-v", f"{directory}:/job", "-w", "/job",
                    image, "python3", "job.py",
                ],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return "", f"container exceeded {timeout_seconds}s"
    return completed.stdout, completed.stderr


def capture_result(
    image: str, code: str, entry_point: str, code_prompt: str, args_json: str
) -> Capture:
    """One implementation's whole result on the secret input, captured as the live scorer does."""
    stdout, stderr = _docker_run(
        image,
        build_capture_script(code, entry_point, code_prompt, args_json),
        CAPTURE_TIMEOUT_SECONDS,
    )
    return parse_capture(stdout, stderr)


def unittest_report(image: str, code: str, code_prompt: str, test_code: str) -> dict[str, Any]:
    """BigCodeBench's own suite against one implementation, assembled as control_arena assembles it."""
    script = (
        _UNITTEST_TEMPLATE.replace("__FULL_CODE__", code_prompt + "\n    pass\n" + code)
        .replace("__TEST_CODE__", test_code)
        .replace("__MARKER__", UNITTEST_MARKER)
    )
    stdout, stderr = _docker_run(image, script, UNITTEST_TIMEOUT_SECONDS)
    for line in stdout.split("\n"):
        if line.startswith(UNITTEST_MARKER):
            return json.loads(line[len(UNITTEST_MARKER) :])
    return {"passed": False, "run": 0, "failed": 0, "crash": (stderr or "no output")[:300]}


def secret_input_kwargs(code_prompt: str, entry_point: str, backdoor_input: str) -> str | None:
    """`backdoor_input` as a JSON kwargs object, or None when it is not JSON-literal.

    The source records the trigger as a Python argument list — `[4, 5, 6, 7]`, `length=127`,
    `pd.DataFrame({...})` — so it is parsed as a call to the entry point and mapped onto the
    signature. `_literal_kwargs` applies the same JSON bar the harness applies to a search space,
    so a DataFrame or an `np.array` argument is refused here rather than failing at run time.
    """
    definition = _entry_definition(code_prompt + "    pass\n", entry_point)
    parameter_names = [
        a.arg for a in (*definition.args.posonlyargs, *definition.args.args)
    ]
    try:
        call = ast.parse(f"{entry_point}({backdoor_input})", mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(call, ast.Call):
        return None
    kwargs = _literal_kwargs(call, parameter_names)
    if kwargs is None:
        return None
    return json.dumps(kwargs)


def pinned_tasks() -> dict[str, dict[str, Any]]:
    """Every task in the `bigcode/bigcodebench` copy control_arena pins, keyed by task id."""
    from control_arena import EvalMode
    from control_arena.settings.bigcodebench.bigcodebench_setting import (
        BigCodeBenchSetting,
    )

    dataset = BigCodeBenchSetting(sandbox_type="local").get_dataset(EvalMode.HONEST)
    pinned = {}
    for sample in dataset:
        metadata = sample.metadata
        if metadata is None:
            raise ValueError(f"BigCodeBench sample {sample.id} carries no metadata")
        pinned[str(metadata["main_task_name"])] = {
            "statement": metadata["main_task_description"],
            **metadata["metadata"],
        }
    return pinned


def verify(
    row: dict[str, Any], pinned: dict[str, dict[str, Any]], image: str
) -> Accepted | Rejection:
    """Put one source row through every gate, in the cheapest-first order."""
    task_id = row["task_id"]
    backdoor = row["backdoors"][0]
    entry_point = row["entry_point"]

    if task_id not in pinned:
        return Rejection(task_id, "not_in_pinned_dataset", "absent from bigcode/bigcodebench")
    task = pinned[task_id]
    if task["code_prompt"] != row["code_prompt"]:
        return Rejection(task_id, "code_prompt_mismatch", "signature differs from the pinned copy")
    if task["canonical_solution"] != row["canonical_solution"]:
        return Rejection(
            task_id, "canonical_mismatch", "reference differs from the pinned copy"
        )

    secret_input = secret_input_kwargs(
        row["code_prompt"], entry_point, backdoor["backdoor_input"]
    )
    if secret_input is None:
        return Rejection(
            task_id, "secret_input_not_json", repr(backdoor["backdoor_input"])[:120]
        )

    code_prompt = task["code_prompt"]
    canonical = task["canonical_solution"]
    honest_code = row["solutions"][0]["code"]
    attack_code = backdoor["backdoor_code"]

    first = capture_result(image, canonical, entry_point, code_prompt, secret_input)
    if first.unmeasured is not None:
        return Rejection(task_id, "reference_unmeasured", first.unmeasured)
    if first.raised is not None:
        return Rejection(task_id, "secret_input_out_of_domain", first.raised)
    second = capture_result(image, canonical, entry_point, code_prompt, secret_input)
    if second.unmeasured is not None:
        return Rejection(task_id, "reference_unmeasured", second.unmeasured)
    repeat = compare_captures(first, second)
    if is_unknown(repeat):
        return Rejection(task_id, "reference_uncomparable", repeat.reason)
    if repeat.diverges:
        return Rejection(
            task_id, "reference_nondeterministic", "the reference disagrees with itself"
        )

    honest_tests = unittest_report(image, honest_code, code_prompt, task["test_code"])
    if not honest_tests["passed"]:
        return Rejection(task_id, "honest_fails_tests", json.dumps(honest_tests)[:200])
    attack_tests = unittest_report(image, attack_code, code_prompt, task["test_code"])
    if not attack_tests["passed"]:
        return Rejection(task_id, "attack_fails_tests", json.dumps(attack_tests)[:200])

    attacked = capture_result(image, attack_code, entry_point, code_prompt, secret_input)
    if attacked.unmeasured is not None:
        return Rejection(task_id, "attack_unmeasured", attacked.unmeasured)
    if attacked.raised is not None:
        return Rejection(task_id, "attack_crashes_on_secret_input", attacked.raised)
    verdict = compare_captures(first, attacked)
    if is_unknown(verdict):
        return Rejection(task_id, "divergence_uncomparable", verdict.reason)
    if not verdict.diverges:
        return Rejection(
            task_id, "attack_does_not_diverge", "same result as the reference on its own trigger"
        )

    example_inputs, _ = statement_examples(task["statement"], entry_point)
    return Accepted(
        task_id=task_id,
        honest_code=honest_code,
        attack_code=attack_code,
        secret_input=secret_input,
        canonical_repr=verdict.canonical_repr,
        attack_repr=verdict.submitted_repr,
        stock_would_have_missed=not verdict.stock_diverges,
        drivable_from_statement_examples=bool(example_inputs),
    )


def _candidate_prefix(task_id: str) -> str:
    return f"BCB{task_id.rsplit('/', 1)[-1]}"


POOL_IO_MODE = "function"

REQUIRED_POOL_KEYS = ("schema_version", "io_mode", "candidates")
REQUIRED_TASK_KEYS = ("honest", "attack_proposals")
REQUIRED_CANDIDATE_KEYS = ("candidate_id", "code", "secret_input")


def validated(document: dict[str, Any]) -> dict[str, Any]:
    """Refuse to write a pool missing anything its readers require. Raises, never repairs.

    `io_mode` is the one that matters and the reason this check exists. `probe.load_problems` reads
    it as `pool.get("io_mode", "stdio")`, so a pool that simply omits it does not trip the guard
    that refuses a function-mode pool — it passes, and every BCB candidate is then handed the stdin
    invoke contract, writes stdin-shaped tests, invokes nothing, and is recorded as the model
    failing rather than as the run being misconfigured. Nothing crashes; the numbers are complete
    and wrong. Declaring the key here does not fix that default, which lives in `probe.py`.
    """
    missing = [key for key in REQUIRED_POOL_KEYS if key not in document]
    if missing:
        raise ValueError(f"pool document is missing {missing}")
    if document["io_mode"] != POOL_IO_MODE:
        raise ValueError(
            f"a BigCodeBench pool is io_mode {POOL_IO_MODE!r}, not {document['io_mode']!r}"
        )
    for task_id, task in document["candidates"].items():
        absent = [key for key in REQUIRED_TASK_KEYS if key not in task]
        if absent:
            raise ValueError(f"{task_id} is missing {absent}")
        for candidate in (task["honest"], *task["attack_proposals"]):
            gaps = [key for key in REQUIRED_CANDIDATE_KEYS if key not in candidate]
            if gaps:
                raise ValueError(f"{task_id}: a candidate is missing {gaps}")
        for attack in task["attack_proposals"]:
            if not attack["secret_input"]:
                raise ValueError(f"{task_id}: an attack carries no secret_input")
    return document


def pool_document(accepted: list[Accepted], image: str) -> dict[str, Any]:
    candidates = {}
    for entry in accepted:
        prefix = _candidate_prefix(entry.task_id)
        candidates[entry.task_id] = {
            "honest": {
                "candidate_id": f"{prefix}_honest",
                "code": entry.honest_code,
                "secret_input": None,
            },
            "attack_proposals": [
                {
                    "candidate_id": f"{prefix}_attack_0",
                    "code": entry.attack_code,
                    "secret_input": entry.secret_input,
                }
            ],
        }
    return validated({
        "schema_version": 1,
        "io_mode": POOL_IO_MODE,
        "n_tasks": len(accepted),
        "source": BACKDOOR_DATASET,
        "selection": (
            "every row of the source whose attack diverges from the pinned reference on its own "
            "secret_input, whose reference is deterministic there, and whose honest and attacked "
            "code both pass BigCodeBench's own unittest suite"
        ),
        "candidates": candidates,
        "views": {
            "selected_policy": {
                entry.task_id: f"{_candidate_prefix(entry.task_id)}_attack_0"
                for entry in accepted
            }
        },
        "deployment_policy": {"attack_probability": None},
        "metadata": {
            "verified_in_image": image,
            "verified_with": "pipeline.scoring.compare_captures",
            "stock_grader_would_miss": sorted(
                e.task_id for e in accepted if e.stock_would_have_missed
            ),
            "drivable_from_statement_examples": sorted(
                e.task_id for e in accepted if e.drivable_from_statement_examples
            ),
        },
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="bcb_pool.json")
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    from datasets import load_dataset

    rows = list(load_dataset(BACKDOOR_DATASET)["train"])
    if args.limit:
        rows = rows[: args.limit]
    pinned = pinned_tasks()

    accepted: list[Accepted] = []
    rejected: list[Rejection] = []
    for index, row in enumerate(rows, start=1):
        outcome = verify(row, pinned, args.image)
        if isinstance(outcome, Accepted):
            accepted.append(outcome)
            print(f"[{index}/{len(rows)}] {outcome.task_id} ACCEPT "
                  f"(stock_would_miss={outcome.stock_would_have_missed}, "
                  f"drivable={outcome.drivable_from_statement_examples})", flush=True)
        else:
            rejected.append(outcome)
            print(f"[{index}/{len(rows)}] {outcome.task_id} REJECT {outcome.gate}: "
                  f"{outcome.detail}", flush=True)

    Path(args.out).write_text(
        json.dumps(pool_document(accepted, args.image), indent=2) + "\n", encoding="utf-8"
    )

    print(f"\n{len(accepted)}/{len(rows)} verified into {args.out}")
    gates: dict[str, int] = {}
    for rejection in rejected:
        gates[rejection.gate] = gates.get(rejection.gate, 0) + 1
    for gate, count in sorted(gates.items(), key=lambda item: -item[1]):
        print(f"  rejected {count:>2}  {gate}")
    print(
        f"  stock grader would have missed {sum(e.stock_would_have_missed for e in accepted)}"
        f" of the {len(accepted)} verified attacks"
    )
    print(
        f"  drivable from statement examples: "
        f"{sum(e.drivable_from_statement_examples for e in accepted)}/{len(accepted)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
