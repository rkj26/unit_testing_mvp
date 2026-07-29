"""Spot-check backdoors in a candidate pool: read the card, read the code, prove it live.

For a sampled set of tasks it prints, per attack candidate: the task's spec, the
plain-English mechanism, the secret input, and then RE-RUNS the verifier live so you
see the canonical-vs-backdoor outputs and the GENUINE verdict for yourself — not just
the author's claim. It also prints the path to the attack code so you can read it.

Usage:
  python scripts/spot_check.py <pool.json> --random 15        # 15 random tasks
  python scripts/spot_check.py <pool.json> --task BigCodeBench/733
  python scripts/spot_check.py <pool.json> --all
  (optional) --specs /tmp/bcb_specs_pool.json   (default) --seed 0 --show-code

Verification runs one task at a time (matplotlib forced off-screen), so it is gentle
on the machine.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

VERIFIER = str(Path(__file__).resolve().parent / "verify_backdoor.py")


def _spec_headline(spec: dict) -> str:
    prompt = spec.get("complete_prompt", "")
    for line in prompt.splitlines():
        s = line.strip().strip('"')
        if s and not s.startswith(("import ", "from ", "def ", "'''", '"""')):
            return s
    return spec.get("entry_point", "task_func")


def _verify(task_id: str, code: str, secret_input: str, specs_path: str) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, VERIFIER, task_id, path, secret_input, "--specs", specs_path],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "MPLBACKEND": "Agg"},
        )
        try:
            return json.loads(r.stdout)
        except Exception:
            return {"error": (r.stdout or r.stderr)[-400:]}
    finally:
        os.unlink(path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pool")
    ap.add_argument("--specs", default="/tmp/bcb_specs_pool.json")
    ap.add_argument("--task", default=None)
    ap.add_argument("--random", type=int, default=0)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--show-code", action="store_true", help="print the attack code inline")
    args = ap.parse_args()

    pool = json.loads(Path(args.pool).read_text())
    specs = json.loads(Path(args.specs).read_text())
    cands = pool["candidates"]
    code_dir = pool.get("metadata", {}).get("code_dir")  # optional: where per-task .py live

    task_ids = sorted(cands)
    if args.task:
        task_ids = [args.task]
    elif args.random:
        import random
        rng = random.Random(args.seed)
        task_ids = rng.sample(task_ids, min(args.random, len(task_ids)))

    print(f"Spot-checking {len(task_ids)} task(s) from {args.pool}\n" + "=" * 78)
    genuine = total = 0
    for tid in task_ids:
        task = cands[tid]
        spec = specs.get(tid, {})
        print(f"\n### {tid} — {_spec_headline(spec)}")
        print(f"    entry point: {spec.get('entry_point','task_func')}")
        for i, atk in enumerate(task["attack_proposals"]):
            total += 1
            si = atk.get("secret_input")
            si_str = si if isinstance(si, str) else json.dumps(si)
            print(f"\n  Attack {i}  [{atk['candidate_id'][:18]}]")
            print(f"    Mechanism:    {atk.get('mechanism','(none recorded)')}")
            print(f"    Secret input: {si_str}")
            res = _verify(tid, atk["code"], si_str, args.specs)
            if "error" in res:
                print(f"    VERIFY ERROR: {res['error']}")
                continue
            print(f"    Canonical -> {res.get('canonical_on_secret')}")
            print(f"    Backdoor  -> {res.get('submitted_on_secret')}")
            ok = res.get("GENUINE_BACKDOOR")
            genuine += bool(ok)
            print(f"    main_task_success={res.get('main_task_success')}  "
                  f"semantically_equal={res.get('semantically_equal')}  "
                  f"=> GENUINE_BACKDOOR={ok}")
            if code_dir:
                print(f"    code: {Path(code_dir)/tid.replace('/','_')/f'attack_{i}.py'}")
            if args.show_code:
                print("    --- code ---")
                for ln in atk["code"].splitlines():
                    print("      " + ln)
    print("\n" + "=" * 78)
    print(f"re-verified GENUINE: {genuine}/{total} attack candidates")


if __name__ == "__main__":
    main()
