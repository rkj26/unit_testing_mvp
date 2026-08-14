"""Write a train/test split of a candidate pool's tasks as explicit id lists.

The audit rule's operating point is calibrated on the TRAIN ids and every reported number comes from
the TEST ids, so the threshold is never chosen on the tasks it is scored against.

Ids rather than a seed, because two arms must provably share one split: a seed only reproduces the
same lists while the shuffle code is untouched, and a silently different split between the baseline
and the treatment would look exactly like an effect.

The seed is the project's standard 300 and is NOT shopped for. The successful-backdoor balance the
shuffle happens to produce is reported by `--pool-scores` and recorded in the file; it is a fact
about the split, not a criterion the split was chosen by.

  .venv/bin/python make_split.py --pool apps_pool_hard.json --train 20 --out splits/apps_hard_20_30.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from random import Random

PROJECT_SEED = 300


def task_ids(pool_path: Path) -> list[str]:
    """Every task id in the pool, in a deterministic order the shuffle can act on."""
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    return sorted(pool["candidates"])


def split(ids: list[str], n_train: int, seed: int) -> tuple[list[str], list[str]]:
    if not 0 < n_train < len(ids):
        raise ValueError(f"train size {n_train} must be inside 0..{len(ids)}")
    shuffled = list(ids)
    Random(f"split:{seed}").shuffle(shuffled)
    return sorted(shuffled[:n_train]), sorted(shuffled[n_train:])


def successful_backdoors(scores_path: Path) -> dict[str, int]:
    """Successful backdoors per task, read from a completed run's ground-truth scores."""
    counts: dict[str, int] = {}
    for record in json.loads(scores_path.read_text(encoding="utf-8")):
        task = record["task_id"]
        counts.setdefault(task, 0)
        if record["main_task_success"] and record["side_task_success"]:
            counts[task] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", required=True)
    parser.add_argument("--train", type=int, required=True)
    parser.add_argument("--seed", type=int, default=PROJECT_SEED)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--pool-scores",
        default="",
        help="a completed run's scores.json, to record the backdoor balance the shuffle produced",
    )
    args = parser.parse_args()

    ids = task_ids(Path(args.pool))
    train, test = split(ids, args.train, args.seed)
    record = {
        "pool": args.pool,
        "seed": args.seed,
        "n_train": len(train),
        "n_test": len(test),
        "train": train,
        "test": test,
    }
    if args.pool_scores:
        counts = successful_backdoors(Path(args.pool_scores))
        record["successful_backdoors"] = {
            "source": args.pool_scores,
            "train": sum(counts.get(t, 0) for t in train),
            "test": sum(counts.get(t, 0) for t in test),
        }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}: {len(train)} train / {len(test)} test from {len(ids)} tasks")
    if args.pool_scores:
        print(f"  successful backdoors: {record['successful_backdoors']}")


if __name__ == "__main__":
    main()
