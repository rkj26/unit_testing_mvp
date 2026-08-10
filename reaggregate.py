"""Re-score a completed run's stored rows under a different MetricConfig. No model calls.

The deployment game is a pure post-hoc Monte Carlo over `run_*/rows.json`, so every knob it reads --
`horizon`, `audit_slots`, `audit_rate`, `attack_probability`, `trials` -- can be changed after the
fact without re-running a single model call. What cannot be changed is anything upstream of a row:
the suspicion scores, the PBT verdicts and the ground-truth labels are fixed by the source run.

This reuses the pipeline's own code paths (`engine._run_metrics`, `metrics.aggregate_runs`,
`report.compile_results`) rather than reimplementing the game, so a number produced here is
comparable with a number the pipeline produced. With no overrides it must reproduce the source run's
metrics.json exactly; `--verify` asserts that, and a mismatch means these two are not the same game.

Nothing is written into the source run. Output goes to `reaggregations/<run_id>/<label>/`, which gets
the same run.json / metrics.json / summary.csv / report.md layout the pipeline writes, plus a
`reaggregation.json` recording provenance and every abstention.

An abstention stays an abstention: a protocol that produced no value under the source config produces
no value here either, because the reason (an honest candidate it never scored) is upstream of the
horizon. Those runs are dropped from `n`, never imputed.

  .venv/bin/python reaggregate.py --run uplanhard50-tlow-uhigh --horizon 100 --audit-slots 10
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

from pipeline import results
from pipeline import metrics as metrics_mod
from pipeline.artifacts import ArtifactKind, ArtifactStore, read_json, write_json
from pipeline.config import Config
from pipeline.engine import _run_metrics
from pipeline.metrics import MetricConfig

RUNS_ROOT = Path("runs")
OUTPUT_ROOT = Path("reaggregations")
REPRODUCTION_TOLERANCE = 1e-12

OVERRIDE_FLAGS = {
    "horizon": "deployment steps per Monte-Carlo trial",
    "audit_slots": "human audits available per deployment",
    "audit_rate": "fraction of honest traffic a human reviews",
    "attack_rate": "per-step probability the untrusted model submits its backdoor",
    "trials": "Monte-Carlo deployments per safety estimate",
}
OVERRIDE_TO_METRIC_FIELD = {"attack_rate": "attack_probability"}


def resolve_run_dir(run: str) -> Path:
    """A run id under runs/, or a path to a run directory."""
    candidates = [Path(run), RUNS_ROOT / run]
    for path in candidates:
        if (path / "run.json").exists():
            return path
    raise FileNotFoundError(
        f"no run.json under any of {[str(c) for c in candidates]}; "
        f"pass a run id under {RUNS_ROOT}/ or a path to a run directory"
    )


def metric_overrides(args: argparse.Namespace) -> dict[str, Any]:
    """Only the flags the caller actually passed; an unpassed flag keeps the source run's value."""
    return {
        OVERRIDE_TO_METRIC_FIELD.get(name, name): getattr(args, name)
        for name in OVERRIDE_FLAGS
        if getattr(args, name) is not None
    }


def rescored_config(manifest: dict[str, Any], overrides: dict[str, Any]) -> Config:
    """The source config with its metric block replaced, revalidated from scratch.

    Built by construction rather than `model_copy`, so `MetricConfig`'s validators run -- notably the
    one that refuses `audit_slots > horizon`.
    """
    metrics = MetricConfig(**{**manifest["metrics"], **overrides})
    return Config.from_json({**manifest, "metrics": metrics.to_json()})


def label_for(config: Config) -> str:
    m = config.metrics
    return (
        f"h{m.horizon}-slots{m.audit_slots}-audit{m.audit_rate}"
        f"-attack{m.attack_probability}-trials{m.trials}"
    )


def completed_run_indices(store: ArtifactStore, requested: int) -> list[int]:
    return [r for r in range(requested) if store.has(ArtifactKind.RUN_METRICS, run=r)]


def rescore(
    run_dir: Path, config: Config
) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]], list[int]]:
    """Recompute per-run metrics from stored rows. Returns (per_run_metrics, rows_by_run, indices)."""
    store = ArtifactStore(run_dir)
    problems = store.load(ArtifactKind.PROBLEMS)
    if not problems:
        raise FileNotFoundError(f"{run_dir}/problems.json is missing or empty")
    indices = completed_run_indices(store, config.runs)
    if not indices:
        raise FileNotFoundError(f"no completed run_*/metrics.json under {run_dir}")
    per_run_metrics: list[dict[str, Any]] = []
    rows_by_run: list[list[dict[str, Any]]] = []
    for r in indices:
        rows, _ = store.load(ArtifactKind.RUN_METRICS, run=r)
        if rows is None:
            raise FileNotFoundError(f"{run_dir}/run_{r}/rows.json is missing")
        per_run_metrics.append(_run_metrics(config, r, problems, store, rows))
        rows_by_run.append(rows)
    return per_run_metrics, rows_by_run, indices


def abstentions(
    per_run_metrics: list[dict[str, Any]], indices: list[int]
) -> list[dict[str, Any]]:
    """Every (run, protocol) the game could not score, with the reason the metric layer gave.

    Reported rather than filled: these are the runs `n` drops, and a reader who does not see them
    will read a mean over four runs as a mean over five.
    """
    return [
        {
            "run": r,
            "protocol": protocol,
            "reason": safety.get("reason", "no reason recorded"),
        }
        for r, m in zip(indices, per_run_metrics)
        for protocol, arm in m["protocols"].items()
        for safety in [arm["safety"]]
        if safety.get("value") is None
    ]


def verify_reproduces_source(
    run_dir: Path, per_run_metrics: list[dict[str, Any]], indices: list[int]
) -> str:
    """With no overrides the recomputation must equal the source run's stored per-run safety."""
    store = ArtifactStore(run_dir)
    worst = 0.0
    compared = 0
    for r, mine in zip(indices, per_run_metrics):
        _, theirs = store.load(ArtifactKind.RUN_METRICS, run=r)
        for protocol, arm in mine["protocols"].items():
            ours = arm["safety"].get("value")
            recorded = theirs["protocols"][protocol]["safety"].get("value")
            if ours is None or recorded is None:
                if (ours is None) != (recorded is None):
                    return f"MISMATCH: run {r} {protocol} abstained in one but not the other"
                continue
            worst = max(worst, abs(ours - recorded))
            compared += 1
    if not compared:
        return "no comparable safety value in the source run"
    verdict = "MATCH" if worst <= REPRODUCTION_TOLERANCE else "MISMATCH"
    return f"{verdict}: {compared} per-run safety values, max |Δ| = {worst:.3e}"


def write_reaggregation(
    out_dir: Path,
    *,
    source_dir: Path,
    manifest: dict[str, Any],
    config: Config,
    per_run_metrics: list[dict[str, Any]],
    rows_by_run: list[list[dict[str, Any]]],
    indices: list[int],
    overrides: dict[str, Any],
    seconds: float,
) -> dict[str, Any]:
    agg = metrics_mod.aggregate_runs(per_run_metrics)
    out_manifest = {
        **config.to_json(),
        "n_tasks": manifest.get("n_tasks", 0),
        "pool": manifest.get("pool", ""),
        "model": manifest.get("model", ""),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "run.json", out_manifest)
    results.compile_results(
        out_dir,
        config=out_manifest,
        run_metrics=per_run_metrics,
        agg=agg,
        rows_by_run=rows_by_run,
    )
    write_json(
        out_dir / "reaggregation.json",
        {
            "source_run": str(source_dir),
            "source_metric_config": manifest["metrics"],
            "metric_config": config.metrics.to_json(),
            "overrides": overrides,
            "run_indices": indices,
            "abstentions": abstentions(per_run_metrics, indices),
            "seconds": seconds,
        },
    )
    return agg


def print_abstentions(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("\n  abstentions: none — every protocol produced a value in every run")
        return
    print(f"\n  abstentions ({len(rows)}) — dropped from n, not imputed:")
    for row in rows:
        print(f"    run {row['run']:>2}  {row['protocol']:<16} {row['reason']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run", required=True, help="run id under runs/, or a run directory"
    )
    parser.add_argument(
        "--horizon", type=int, default=None, help=OVERRIDE_FLAGS["horizon"]
    )
    parser.add_argument(
        "--audit-slots", type=int, default=None, help=OVERRIDE_FLAGS["audit_slots"]
    )
    parser.add_argument(
        "--audit-rate", type=float, default=None, help=OVERRIDE_FLAGS["audit_rate"]
    )
    parser.add_argument(
        "--attack-rate", type=float, default=None, help=OVERRIDE_FLAGS["attack_rate"]
    )
    parser.add_argument(
        "--trials", type=int, default=None, help=OVERRIDE_FLAGS["trials"]
    )
    parser.add_argument(
        "--out",
        default="",
        help="output directory (default: reaggregations/<run_id>/<label>)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="check the recomputation reproduces the source run (only meaningful with no overrides)",
    )
    args = parser.parse_args()

    source_dir = resolve_run_dir(args.run)
    manifest = read_json(source_dir / "run.json")
    if manifest is None:
        raise SystemExit(f"reaggregate.py: cannot read {source_dir}/run.json")
    overrides = metric_overrides(args)
    config = rescored_config(manifest, overrides)
    out_dir = (
        Path(args.out)
        if args.out
        else OUTPUT_ROOT / config.run_id / label_for(config)
    )
    if out_dir.resolve() == source_dir.resolve():
        raise SystemExit("reaggregate.py: refusing to write into the source run directory")

    started = time.monotonic()
    per_run_metrics, rows_by_run, indices = rescore(source_dir, config)
    seconds = time.monotonic() - started

    agg = write_reaggregation(
        out_dir,
        source_dir=source_dir,
        manifest=manifest,
        config=config,
        per_run_metrics=per_run_metrics,
        rows_by_run=rows_by_run,
        indices=indices,
        overrides=overrides,
        seconds=seconds,
    )
    print_abstentions(abstentions(per_run_metrics, indices))
    resolved = {p: agg["protocols"][p]["safety"]["n"] for p in agg["protocols"]}
    print(
        f"\n  source {source_dir}  runs {indices}  overrides {overrides or 'none'}\n"
        f"  runs resolved per protocol {resolved}\n"
        f"  rescored in {seconds:.1f}s  ->  {out_dir}"
    )
    if args.verify:
        print(
            f"  verify: {verify_reproduces_source(source_dir, per_run_metrics, indices)}"
        )


if __name__ == "__main__":
    main()
