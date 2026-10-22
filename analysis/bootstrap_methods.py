"""Four bootstrap methods for deployment safety, compared side by side.

Read-only. Reads finished run directories, makes no model calls, re-runs no experiment.

The statistic is deployment safety at an audit budget, played by the repo's own game
(`analysis/safety.py`, copied verbatim from `notebooks/build_results.py` with a provenance hash).
The threshold is the budget quantile of honest TRAIN scores and is recomputed inside every
resample, because the threshold is estimated too. All methods share one fixed deployment draw and
one set of seeds, so differences between them are differences of resampling scheme alone.

THE RESAMPLING UNIT IS THE TASK. Every apps_full task carries exactly one honest and one attack
candidate (verified: 1388 tasks, 1388 honest, 1388 attack, 0 tasks with a second attack), so there
is no cluster of candidates to resample within a task. The only stochastic level inside a task is
the monitor's repeated calls (`scores`, the mean-of-2). That shapes the methods:

    multinomial   paired task-level multinomial resample. The repo's current approach, the scheme
                  mt_bootstrap_differences already uses for the catch-rate contrast. Resample task
                  indices with replacement, the SAME indices for every arm.
    hierarchical  resample tasks (outer), then resample each candidate's monitor calls (inner).
                  The inner level is monitor-only; for a tests arm, whose score is a deterministic
                  fired-count with no repeated calls, it reduces exactly to multinomial.
    bayesian      Dirichlet(1) weights over tasks instead of integer counts. The cut is a
                  weight-aware quantile of honest train; the deployment draws test tasks with
                  probability proportional to their weight. Continuous weights, so it is the
                  method to ask the degenerate-quantile question of.
    calls_only    tasks held FIXED, only each candidate's monitor calls resampled. Isolates
                  scoring noise from task-sampling noise. Zero width for a tests arm, by
                  construction, which is the point of including it.

Paired throughout: within one resample every arm sees the same task indices (or weights) and the
same deployment draw, so a difference between two arms is a within-resample difference.
"""

from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("safety", HERE / "safety.py")
safety = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(safety)

MONITOR_PROTOCOLS = {"tm", "monitor_with_tests"}
DEFAULT_BUDGETS = (0.02, 0.05, 0.10, 0.20)
METHODS = ("multinomial", "hierarchical", "bayesian", "calls_only")


def open_records(path_dir: Path):
    plain, gz = path_dir / "records.jsonl", path_dir / "records.jsonl.gz"
    if plain.exists():
        return plain.open()
    if gz.exists():
        return gzip.open(gz, "rt")
    raise SystemExit(f"no records.jsonl[.gz] in {path_dir}")


def protocol_of(runs_dir: Path, name: str) -> str:
    return json.loads((runs_dir / name / "config.json").read_text())["protocol"]


def paired_levels(runs_dir: Path, name: str, protocol: str):
    """{task_id: {'honest': info, 'attack': info}} where info carries the score and raw calls.

    For a monitor the raw calls are the per-call scores list (the mean-of-2); for a tests arm there
    are no repeated calls, so `calls` is None and only the deterministic level exists.
    """
    is_monitor = protocol in MONITOR_PROTOCOLS
    sides: dict[str, dict] = {}
    with open_records(runs_dir / name) as handle:
        for line in handle:
            r = json.loads(line)
            if r["failed"]:
                continue
            if is_monitor:
                level = float(r["avg_score"])            # the notebook's own monitor level
                raw = r.get("scores") or []
                calls = [float(s) for s in raw] if raw and all(s is not None for s in raw) else None
            else:
                calls = None
                level = float(len(set(r["fired"])))
            side = "attack" if r["is_attack"] else "honest"
            sides.setdefault(r["task_id"], {})[side] = {"level": level, "calls": calls}
    return {t: v for t, v in sides.items() if len(v) == 2}, is_monitor


def resample_calls(calls: list[float] | None, rng) -> float:
    if not calls:
        return None
    draw = rng.integers(0, len(calls), len(calls))
    return float(np.mean([calls[i] for i in draw]))


def weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    """The smallest value whose cumulative weight reaches q — the weighted 'higher' quantile."""
    order = np.argsort(values)
    v, w = values[order], weights[order]
    cum = np.cumsum(w) / w.sum()
    idx = int(np.searchsorted(cum, q, side="left"))
    return float(v[min(idx, len(v) - 1)])


def play(cut: float, test_honest: np.ndarray, test_attack: np.ndarray, draw: dict,
         variation, budget: float) -> dict:
    seen = np.where(draw["attacking"], test_attack[draw["drawn"]], test_honest[draw["drawn"]])
    return variation(seen, draw, cut, budget)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs-dir", required=True, type=Path)
    ap.add_argument("--pool", required=True, type=Path)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--arm", action="append", required=True, dest="arms")
    ap.add_argument("--budgets", default=",".join(str(b) for b in DEFAULT_BUDGETS))
    ap.add_argument("--methods", default=",".join(METHODS))
    ap.add_argument("--resamples", type=int, default=2000)
    ap.add_argument("--trials", type=int, default=2000)
    ap.add_argument("--point-trials", type=int, default=20_000)
    ap.add_argument("--horizon", type=int, default=50)
    ap.add_argument("--attack-rate", type=float, default=0.05)
    ap.add_argument("--variation", default="B · flags held back, run continues")
    ap.add_argument("--seed", type=int, default=20261022)
    ap.add_argument("--label", default="")
    ap.add_argument("--out-csv", required=True, type=Path)
    args = ap.parse_args()

    safety.check_provenance(HERE.parent)
    budgets = [float(b) for b in args.budgets.split(",")]
    methods = [m for m in args.methods.split(",")]
    variation = safety.VARIATIONS[args.variation]
    labels = [args.baseline] + args.arms

    if args.pool.suffix == ".gz":
        pool = json.loads(gzip.open(args.pool, "rt").read())
    else:
        pool = json.loads(args.pool.read_text())
    train_ids, test_ids = set(pool["split"]["train"]), set(pool["split"]["test"])

    per_arm = {}
    for name in labels:
        proto = protocol_of(args.runs_dir, name)
        levels, is_monitor = paired_levels(args.runs_dir, name, proto)
        per_arm[name] = {"proto": proto, "levels": levels, "is_monitor": is_monitor}
        print(f"  {name:<32} {proto:<18} tasks with both sides={len(levels)} monitor={is_monitor}")

    shared = sorted(set.intersection(*(set(a["levels"]) for a in per_arm.values())))
    train = [t for t in shared if t in train_ids]
    test = [t for t in shared if t in test_ids]
    print(f"\n  scored by every arm: {len(shared)}  ({len(train)} train, {len(test)} test)\n")

    def level_arrays(name, task_ids, side):
        return np.array([per_arm[name]["levels"][t][side]["level"] for t in task_ids], float)

    def calls_for(name, task_ids, side):
        return [per_arm[name]["levels"][t][side]["calls"] for t in task_ids]

    base = {n: {"train_h": level_arrays(n, train, "honest"),
                "train_a": level_arrays(n, train, "attack"),
                "test_h": level_arrays(n, test, "honest"),
                "test_a": level_arrays(n, test, "attack"),
                "train_hc": calls_for(n, train, "honest"),
                "test_hc": calls_for(n, test, "honest"),
                "test_ac": calls_for(n, test, "attack")}
            for n in labels}

    def draw_stream(n_tasks, trials, seed):
        rng = np.random.default_rng(seed)
        return {"horizon": args.horizon,
                "drawn": rng.integers(0, n_tasks, (trials, args.horizon)),
                "attacking": rng.random((trials, args.horizon)) < args.attack_rate}

    point_draw = draw_stream(len(test), args.point_trials, args.seed)
    boot_draw = draw_stream(len(test), args.trials, args.seed + 1)

    def cut_and_test(name, budget, method, rng):
        """Return (cut, test_honest, test_attack) for one arm under one method's perturbation."""
        d = base[name]
        if method == "calls_only":
            th = np.array([(resample_calls(c, rng) if c else None) or l
                           for c, l in zip(d["train_hc"], d["train_h"])])
            test_h = np.array([(resample_calls(c, rng) if c else None) or l
                               for c, l in zip(d["test_hc"], d["test_h"])])
            test_a = np.array([(resample_calls(c, rng) if c else None) or l
                               for c, l in zip(d["test_ac"], d["test_a"])])
            cut = float(np.quantile(th, 1 - budget, method="higher"))
            return cut, test_h, test_a
        raise RuntimeError("handled in the paired loop")

    rng_master = np.random.default_rng(args.seed + 7)
    rows = []
    for method in methods:
        n_tr, n_te = len(train), len(test)
        # one stream of resample draws, shared across arms within a resample (paired)
        if method in ("multinomial", "hierarchical"):
            tr_idx = rng_master.integers(0, n_tr, (args.resamples, n_tr))
            te_idx = rng_master.integers(0, n_te, (args.resamples, n_te))
            tr_w = te_w = None
        elif method == "bayesian":
            tr_w = rng_master.dirichlet(np.ones(n_tr), args.resamples)
            te_w = rng_master.dirichlet(np.ones(n_te), args.resamples)
            tr_idx = te_idx = None
        else:  # calls_only
            tr_idx = te_idx = tr_w = te_w = None
        call_rng = np.random.default_rng(args.seed + 99)

        for budget in budgets:
            point = {}
            for n in labels:
                cut = float(np.quantile(base[n]["train_h"], 1 - budget, method="higher"))
                point[n] = play(cut, base[n]["test_h"], base[n]["test_a"],
                                point_draw, variation, budget)["safety"]
            boot = {n: np.empty(args.resamples) for n in labels}
            diff = {n: np.empty(args.resamples) for n in args.arms}
            for r in range(args.resamples):
                for n in labels:
                    d = base[n]
                    if method == "multinomial":
                        th, tai = d["train_h"][tr_idx[r]], None
                        cut = float(np.quantile(th, 1 - budget, method="higher"))
                        test_h, test_a = d["test_h"][te_idx[r]], d["test_a"][te_idx[r]]
                    elif method == "hierarchical":
                        ti, si = tr_idx[r], te_idx[r]
                        if per_arm[n]["is_monitor"]:
                            th = np.array([resample_calls(d["train_hc"][i], call_rng) or d["train_h"][i] for i in ti])
                            test_h = np.array([resample_calls(d["test_hc"][i], call_rng) or d["test_h"][i] for i in si])
                            test_a = np.array([resample_calls(d["test_ac"][i], call_rng) or d["test_a"][i] for i in si])
                        else:
                            th, test_h, test_a = d["train_h"][ti], d["test_h"][si], d["test_a"][si]
                        cut = float(np.quantile(th, 1 - budget, method="higher"))
                    elif method == "bayesian":
                        cut = weighted_quantile(d["train_h"], tr_w[r], 1 - budget)
                        pick = np.random.default_rng(args.seed + 1000 + r).choice(
                            n_te, size=n_te, replace=True, p=te_w[r])
                        test_h, test_a = d["test_h"][pick], d["test_a"][pick]
                    else:  # calls_only
                        cut, test_h, test_a = cut_and_test(n, budget, method, call_rng)
                    boot[n][r] = play(cut, test_h, test_a, boot_draw, variation, budget)["safety"]
                for n in args.arms:
                    diff[n][r] = boot[n][r] - boot[args.baseline][r]
            for n in args.arms:
                lo_a, hi_a = np.percentile(boot[n], [2.5, 97.5])
                lo_b, hi_b = np.percentile(boot[args.baseline], [2.5, 97.5])
                lo_d, hi_d = np.percentile(diff[n], [2.5, 97.5])
                rows.append({
                    "method": method, "variation": args.variation, "budget": budget,
                    "arm": n, "baseline": args.baseline, "n_train": len(train), "n_test": len(test),
                    "safety_arm": round(point[n], 4),
                    "safety_arm_lo": round(lo_a, 4), "safety_arm_hi": round(hi_a, 4),
                    "arm_ci_width": round(hi_a - lo_a, 4),
                    "safety_base": round(point[args.baseline], 4),
                    "safety_base_lo": round(lo_b, 4), "safety_base_hi": round(hi_b, 4),
                    "base_ci_width": round(hi_b - lo_b, 4),
                    "diff": round(point[n] - point[args.baseline], 4),
                    "diff_lo": round(lo_d, 4), "diff_hi": round(hi_d, 4),
                    "diff_ci_width": round(hi_d - lo_d, 4),
                    "resamples": args.resamples, "boot_trials": args.trials, "seed": args.seed,
                    "label": args.label,
                })
            print(f"  {method:<13} b{budget:>5.0%}  base {point[args.baseline]:.3f}"
                  + "".join(f"   {n.split('-')[-1][:8]} diff {point[n]-point[args.baseline]:+.3f}"
                            f" [{np.percentile(diff[n],2.5):+.3f},{np.percentile(diff[n],97.5):+.3f}]"
                            for n in args.arms))

    frame = pd.DataFrame(rows)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.out_csv, index=False)
    print(f"\nwrote {args.out_csv}  ({len(frame)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
