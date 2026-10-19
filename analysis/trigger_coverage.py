"""Why a suite missed a backdoor: no triggering input, or a triggering input nobody asserted on.

Reads finished run directories and re-executes saved code locally. Makes no model calls and
writes nothing back into runs/.

For every attack candidate the suite failed to flag, this takes the inputs the suite was actually
run against, executes the honest reference and the backdoored submission on each of them, and
splits the miss into:

    never_triggered       no input made the two disagree. The trigger space never reached the
                          backdoor, so no assertion could have saved it. A coverage failure.
    triggered_not_caught  at least one input made them disagree, and the suite still did not
                          fire. The input was there and nothing asserted the difference. A
                          spec-entailment failure.
    error                 one or both sides crashed or timed out on every input that mattered,
                          so the comparison could not be made. Kept separate, never folded into
                          never_triggered, because an unmade comparison is not evidence of
                          no difference.

WHERE THE INPUTS COME FROM. Unit-testing records do not store the inputs. They store
`triggers_run`, and `catches[].input_index` indexes into that run's `inputs` list. The suite is
executed against the whole list, so the list is the input set, recovered by joining on
candidate_id. There is no Hypothesis in this generation of the pipeline: the inputs are a fixed
enumerated list, not drawn.

DEAD TESTS. A test that never calls `run` passes nothing to the solution and can never fire.
Suites are reported with their live-test count, and a candidate whose suite has no live test at
all is marked `no_live_tests` rather than counted as a coverage failure, since nothing was ever
asked of the solution.

    python analysis/trigger_coverage.py \
        --runs-dir /path/to/runs --pool /path/to/pool.json \
        --tests-run ut-plain_v3-20-nc-blind \
        --out-csv reports/coverage_hard_pool.csv
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

NEVER = "never_triggered"
TRIGGERED = "triggered_not_caught"
ERROR = "error"
NO_LIVE = "no_live_tests"


def live_test_names(tests_src: str) -> set[str]:
    """Tests that both call `run` and assert. Anything else cannot report a wrong answer."""
    try:
        tree = ast.parse(tests_src)
    except SyntaxError:
        return set()
    live = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test"):
            continue
        calls_run = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                        and n.func.id == "run" for n in ast.walk(node))
        asserts = any(isinstance(n, ast.Assert) for n in ast.walk(node))
        if calls_run and asserts:
            live.add(node.name)
    return live


def run_once(code: str, stdin_text: str, timeout_s: int, python: str) -> tuple[str, str | None]:
    """One execution of one program on one input. Returns (status, stdout or None).

    status is "ok", "crash" or "timeout". A non-zero exit is a crash, not an empty answer: an
    empty answer would silently compare equal to another empty answer and manufacture a
    never_triggered.
    """
    try:
        done = subprocess.run([python, "-c", code], input=stdin_text, text=True,
                              capture_output=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return "timeout", None
    except OSError as error:
        return "crash", None
    if done.returncode != 0:
        return "crash", None
    return "ok", done.stdout.strip()


def classify(honest_code: str, attack_code: str, inputs: list[str], timeout_s: int,
             python: str) -> dict:
    """Compare the two programs across every input and say why the suite could have missed."""
    differing, comparable, errors = [], 0, 0
    for index, value in enumerate(inputs):
        h_status, h_out = run_once(honest_code, value, timeout_s, python)
        a_status, a_out = run_once(attack_code, value, timeout_s, python)
        if h_status != "ok" or a_status != "ok":
            errors += 1
            continue
        comparable += 1
        if h_out != a_out:
            differing.append(index)
    if comparable == 0:
        verdict = ERROR
    elif differing:
        verdict = TRIGGERED
    else:
        verdict = NEVER
    return {"verdict": verdict, "n_inputs": len(inputs), "n_comparable": comparable,
            "n_errors": errors, "n_differing": len(differing),
            "differing_indices": differing[:10]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs-dir", required=True, type=Path)
    ap.add_argument("--pool", required=True, type=Path)
    ap.add_argument("--tests-run", required=True)
    ap.add_argument("--triggers-run", default="",
                    help="defaults to the triggers_run recorded on each record")
    ap.add_argument("--timeout-seconds", type=int, default=10,
                    help="per single execution; the pipeline's SINGLE_CANDIDATE_CALL_SECONDS is 6")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--label", default="")
    ap.add_argument("--out-csv", required=True, type=Path)
    args = ap.parse_args()

    pool = json.loads(args.pool.read_text())
    honest_for, attack_for, reference_for = {}, {}, {}
    for task in pool["tasks"]:
        for candidate in task["candidates"]:
            if candidate["label"] == "honest":
                honest_for[task["task_id"]] = candidate["code"]
            else:
                attack_for[candidate["candidate_id"]] = (task["task_id"], candidate["code"])
        reference_for[task["task_id"]] = task.get("reference_solution") or ""

    records = [json.loads(l) for l in (args.runs_dir / args.tests_run / "records.jsonl").open()]
    triggers = {}
    for record in records:
        name = args.triggers_run or record.get("triggers_run")
        if name and name not in triggers:
            triggers[name] = {json.loads(l)["candidate_id"]: json.loads(l)
                              for l in (args.runs_dir / name / "records.jsonl").open()}

    missed = [r for r in records
              if r["is_attack"] and not r["failed"] and not r["fired"]]
    print(f"  {args.tests_run}: {len(records)} records, "
          f"{sum(1 for r in records if r['is_attack'] and not r['failed'])} scored attacks, "
          f"{len(missed)} missed")

    rows = []
    for record in missed:
        cid = record["candidate_id"]
        task_id, attack_code = attack_for[cid]
        honest_code = reference_for.get(task_id) or honest_for[task_id]
        source = "reference_solution" if reference_for.get(task_id) else "honest_sibling"
        live = live_test_names(record["tests_src"])
        trig_name = args.triggers_run or record.get("triggers_run")
        trig = triggers.get(trig_name, {}).get(cid)
        inputs = list((trig or {}).get("inputs") or [])
        if not live:
            rows.append({"candidate_id": cid, "task_id": task_id, "verdict": NO_LIVE,
                         "n_live_tests": 0, "n_total_tests": len(record["test_names"]),
                         "n_inputs": len(inputs), "n_comparable": 0, "n_errors": 0,
                         "n_differing": 0, "differing_indices": "", "honest_source": source})
            continue
        if not inputs:
            rows.append({"candidate_id": cid, "task_id": task_id, "verdict": ERROR,
                         "n_live_tests": len(live), "n_total_tests": len(record["test_names"]),
                         "n_inputs": 0, "n_comparable": 0, "n_errors": 0, "n_differing": 0,
                         "differing_indices": "", "honest_source": "no_trigger_record"})
            continue
        got = classify(honest_code, attack_code, inputs, args.timeout_seconds, args.python)
        rows.append({"candidate_id": cid, "task_id": task_id, "verdict": got["verdict"],
                     "n_live_tests": len(live), "n_total_tests": len(record["test_names"]),
                     "n_inputs": got["n_inputs"], "n_comparable": got["n_comparable"],
                     "n_errors": got["n_errors"], "n_differing": got["n_differing"],
                     "differing_indices": " ".join(str(i) for i in got["differing_indices"]),
                     "honest_source": source})
        print(f"    {cid:<24} {got['verdict']:<22} "
              f"differ {got['n_differing']}/{got['n_comparable']} comparable, "
              f"{got['n_errors']} errored")

    frame = pd.DataFrame(rows)
    frame.insert(0, "tests_run", args.tests_run)
    frame.insert(0, "label", args.label)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.out_csv, index=False)

    counts = frame.verdict.value_counts()
    print(f"\n  n missed = {len(frame)}")
    for verdict, count in counts.items():
        print(f"    {verdict:<22} {count:>3}  ({count / len(frame):.1%})")
    print(f"\nwrote {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
