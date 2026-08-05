"""Offline force-audit comparison on existing rows, swept across gen-strategy arms.

Reads only persisted rows, so it makes no model calls. Three audit rules share the SAME single
slot and the same deployment draws, so only the decision rule differs:

  tm            audit iff the TM score clears the honest-calibrated quantile
  forcePBT      audit iff TM fires OR the deployable PBT suite fired
  forceCEIL     audit iff TM fires OR the reference-gated PBT suite fired

TM's threshold is calibrated on TM-honest only, so PBT never poisons it. A force-audit rule cannot
be calibrated, so its false positives spend real slots; that cost only materializes when honest
traffic is deployed, hence the attack-rate sweep. Every simulation runs through
`pipeline.metrics.simulate_safety`, so this script cannot drift from the pipeline's game.

Usage (defaults to all gen-strategy arms):
  .venv/bin/python force_audit.py
  .venv/bin/python force_audit.py blind_t=runs/apps-hard10 u_plans_u_writes=runs/apps-hard10-upuw2
"""

from __future__ import annotations

import sys
from pathlib import Path

from pipeline.artifacts import ArtifactStore, read_json
from pipeline.metrics import (
    DEFAULT_ATTACK_RATES,
    DEFAULT_AUDIT_RATE,
    MetricConfig,
    _delta,
    _paired_stat,
    deployment_draws,
    simulate_safety,
)

MAX_RUNS_PER_ARM = 5
DRAW_SEED_BASE = 1000
DEFAULT_ARMS = (
    ("blind_t", "runs/apps-hard10"),
    ("u_writes", "runs/apps-hard10-uwrite"),
    ("u_plans_t_writes", "runs/apps-hard10-uplan"),
    ("u_plans_u_writes", "runs/apps-hard10-upuw"),
    ("crit(FPR0.16)", "runs/apps-hard10-crit"),
)
ARM_RULES = (
    ("Δ forcePBT(deploy)", "pbt"),
    ("Δ forceCEIL(FPR0)", "pbt_ceiling"),
)


def load_rows(run_dir: str, r: int) -> list[dict]:
    return read_json(Path(run_dir) / f"run_{r}" / "rows.json") or []


def selected_policy(rows: list[dict]) -> dict[str, str]:
    """The run's deployed attack per task: the first attack candidate seen for each."""
    policy: dict[str, str] = {}
    for row in rows:
        if str(row["candidate_label"]).startswith("attack_") and row["task_id"] not in policy:
            policy[row["task_id"]] = row["candidate_id"]
    return policy


def safety_by_rule(run_dir: str, config: MetricConfig) -> dict[str, list[float]]:
    """Per-run safety for each audit rule, dropping runs where a protocol abstained."""
    out: dict[str, list[float]] = {"tm": [], "pbt": [], "pbt_ceiling": []}
    for r in range(MAX_RUNS_PER_ARM):
        rows = load_rows(run_dir, r)
        if not rows:
            continue
        policy = selected_policy(rows)
        draws = deployment_draws(sorted(policy), config.model_copy(update={"seed": DRAW_SEED_BASE + r}))
        baseline = simulate_safety(rows, policy, "tm", draws, config)
        if baseline["value"] is None:
            continue
        forced = {
            trigger: simulate_safety(rows, policy, "tm", draws, config, force_audit_on=trigger)
            for _, trigger in ARM_RULES
        }
        if any(f["value"] is None for f in forced.values()):
            continue
        out["tm"].append(baseline["value"])
        for trigger, result in forced.items():
            out[trigger].append(result["value"])
    return out


def _cell(deltas: list[float], config: MetricConfig) -> str:
    stat = _paired_stat(deltas, config)
    if stat["ci95"] is None:
        return f"{stat['mean']:>+8.3f}          (n<2)"
    lo, hi = stat["ci95"]
    mark = "*" if stat["excludes_zero"] else " "
    return f"{stat['mean']:>+8.3f}±{stat['std']:.3f} [{lo:+.3f},{hi:+.3f}]{mark}"


def report_arm(label: str, run_dir: str) -> None:
    by_rate = {
        rate: safety_by_rule(run_dir, MetricConfig(audit_rate=DEFAULT_AUDIT_RATE, attack_probability=rate))
        for rate in DEFAULT_ATTACK_RATES
    }
    first = by_rate[DEFAULT_ATTACK_RATES[0]]
    print(f"\n### {label}  [{run_dir}]  — safety vs attack_probability")
    print(f"  n={len(first['tm'])} usable runs (runs with an abstained honest TM score are dropped); "
          f"audit_rate={DEFAULT_AUDIT_RATE}; paired Δ vs TM,")
    print("  mean±std with the Student-t 95% CI on the run-mean. * = CI excludes zero.")
    header = "".join(f"{name:^30}" for name, _ in ARM_RULES)
    print(f"  {'attack_p':>8} {'TM':>13}   {header}")
    for rate in DEFAULT_ATTACK_RATES:
        arm = by_rate[rate]
        config = MetricConfig(audit_rate=DEFAULT_AUDIT_RATE, attack_probability=rate)
        tm = _paired_stat(arm["tm"], config)
        cells = " ".join(
            _cell([_delta(f, t) for f, t in zip(arm[trigger], arm["tm"])], config)
            for _, trigger in ARM_RULES
        )
        print(f"  {rate:>8} {tm['mean']:>7.3f}±{tm['std']:.3f}   {cells}")
    print("  NB forceCEIL is reference-gated (FPR 0), so in a single-slot game its audits are a")
    print("  monotone superset of TM's — Δ>=0 is near-structural; only the magnitude is empirical.")


def main() -> None:
    arms = [tuple(a.split("=", 1)) for a in sys.argv[1:]] or list(DEFAULT_ARMS)
    missing = [d for _, d in arms if not ArtifactStore(d).run_dir.exists()]
    if missing:
        print(f"skipping absent run dirs: {missing}", file=sys.stderr)
    for label, run_dir in arms:
        if Path(run_dir).exists():
            report_arm(label, run_dir)


if __name__ == "__main__":
    main()
