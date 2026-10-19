"""Count candidates whose input reading defeats the harness's stdin redirect.

Read-only. No execution, no model calls: this is a static scan of candidate source.

The harness rebinds `sys.stdin` to a StringIO (pipeline/sandbox.py:133) and leaves file
descriptor 0 alone. Anything that reaches the real fd 0, or that needs an attribute a StringIO
does not have, therefore sees an empty or missing stream and raises, on every input, regardless
of the protocol under test. Such a candidate is recorded `candidate_crash` throughout and can
never be caught, while still sitting in the attack denominator.

Patterns, split by why they break:

    fd0         open(0), os.read(0, ...), os.fdopen(0), io.FileIO(0), os.dup(0)
                reaches the real descriptor, which the harness never fills
    dev_stdin   open("/dev/stdin")  - same, by path
    stringio    sys.stdin.buffer, sys.stdin.fileno()  - a StringIO has neither

`sys.stdin.read()`, `input()` and `sys.stdin.readlines()` are fine and are not counted.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

PATTERNS = {
    "fd0": re.compile(
        r"\bopen\s*\(\s*0\s*[,)]"
        r"|\bos\.read\s*\(\s*0\s*,"
        r"|\bos\.fdopen\s*\(\s*0\s*[,)]"
        r"|\bio\.FileIO\s*\(\s*0\s*[,)]"
        r"|\bFileIO\s*\(\s*0\s*[,)]"
        r"|\bos\.dup\s*\(\s*0\s*\)"),
    "dev_stdin": re.compile(r"""["']/dev/stdin["']"""),
    "stringio": re.compile(r"\bsys\.stdin\.buffer\b|\bsys\.stdin\.fileno\s*\("),
}


def hits(code: str) -> dict[str, list[str]]:
    found = {}
    for name, pattern in PATTERNS.items():
        lines = [line.strip() for line in code.splitlines() if pattern.search(line)]
        if lines:
            found[name] = lines
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pool", action="append", required=True, type=Path, dest="pools")
    ap.add_argument("--runs-dir", action="append", default=[], type=Path, dest="runs_dirs")
    ap.add_argument("--out-csv", required=True, type=Path)
    ap.add_argument("--snippets", type=int, default=8)
    args = ap.parse_args()

    rows, shown = [], 0
    by_pool = {}
    for pool_path in args.pools:
        if not pool_path.exists():
            print(f"  (skipped, missing: {pool_path})")
            continue
        pool = json.loads(pool_path.read_text())
        codes = {}
        for task in pool["tasks"]:
            for cand in task["candidates"]:
                codes[cand["candidate_id"]] = (task["task_id"], cand["label"], cand["code"])
        by_pool[pool_path.name] = codes
        for cid, (task_id, label, code) in codes.items():
            found = hits(code)
            if not found:
                continue
            rows.append({"pool": pool_path.name, "candidate_id": cid, "task_id": task_id,
                         "side": "honest" if label == "honest" else "attack",
                         "kinds": "+".join(sorted(found)),
                         "snippet": found[sorted(found)[0]][0][:120]})
            if shown < args.snippets:
                print(f"    {cid:<26} {'+'.join(sorted(found)):<12} {found[sorted(found)[0]][0][:90]}")
                shown += 1

    frame = pd.DataFrame(rows)
    print("\n=== 1. by pool ===")
    for name, codes in by_pool.items():
        total = len(codes)
        part = frame[frame.pool == name] if len(frame) else frame
        n = len(part)
        print(f"  {name:<34} {n:>4} of {total:>5} candidates  ({n / total:.1%})")
        if n:
            for side in ("honest", "attack"):
                sub = part[part.side == side]
                denom = sum(1 for _, (_, lab, _) in codes.items()
                            if (lab == "honest") == (side == "honest"))
                print(f"      {side:<8} {len(sub):>4} of {denom:>5}  ({len(sub) / denom:.1%})"
                      f"   kinds: {dict(sub.kinds.value_counts())}")

    print("\n=== 2. by run (run's own pool), and 3. all-crash attacks ===")
    run_rows = []
    for runs_dir in args.runs_dirs:
        for config_path in sorted(runs_dir.glob("*/config.json")):
            config = json.loads(config_path.read_text())
            pool_name = Path(config.get("data", "")).name
            if pool_name not in by_pool:
                continue
            records = [json.loads(l) for l in (config_path.parent / "records.jsonl").open()]
            affected = set(frame[frame.pool == pool_name].candidate_id) if len(frame) else set()
            scored = [r for r in records if not r["failed"]]
            hit = [r for r in scored if r["candidate_id"] in affected]
            att = [r for r in hit if r["is_attack"]]
            allcrash = [r for r in att
                        if (r.get("n_pairs_by_outcome") or {}).get("candidate_crash", 0) > 0
                        and (r.get("n_pairs_by_outcome") or {}).get("catch", 0) == 0
                        and not r.get("fired")]
            run_rows.append({"run": config["run_name"], "protocol": config["protocol"],
                             "pool": pool_name, "scored": len(scored),
                             "affected": len(hit), "affected_attacks": len(att),
                             "affected_attacks_uncaught": sum(1 for r in att if not r.get("fired")),
                             "affected_attacks_all_crash_uncaught": len(allcrash)})
    runs = pd.DataFrame(run_rows)
    if len(runs):
        runs = runs[runs.affected > 0].sort_values("affected", ascending=False)
        print(runs.to_string(index=False))
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.out_csv, index=False)
    runs.to_csv(args.out_csv.with_name(args.out_csv.stem + "_by_run.csv"), index=False)
    print(f"\nwrote {args.out_csv} and {args.out_csv.with_name(args.out_csv.stem + '_by_run.csv')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
