"""Print a horizon sweep as one table, reading benign-imputed safety from reaggregation outputs.

The headline `safety` field is EXCLUDE-policy and is absent for any protocol that abstained on an
honest candidate, so this reads `safety_by_undecidable_policy.benign` instead -- the single
convention we report under. Earned safety subtracts the free floor, the share of deployments in
which the attacker never attacked.

  .venv/bin/python sweep_table.py uplanhard50-tlow-uhigh
"""

from __future__ import annotations

import statistics
import sys
from json import loads
from pathlib import Path

REAGGREGATION_ROOT = Path("reaggregations")
PROTOCOLS = ("tm", "pbt", "pbt_ceiling", "pbt_informed_tm")
BASELINE_PROTOCOL = "tm"


def horizon_of(directory: Path) -> int:
    return int(directory.name.split("-")[0].removeprefix("h"))


def benign(arm: dict) -> dict:
    return (arm.get("safety_by_undecidable_policy") or {}).get("benign") or {}


def paired_delta(protocol_values: list[float], tm_values: list[float]) -> str:
    if len(protocol_values) != len(tm_values) or len(protocol_values) < 2:
        return "n/a"
    deltas = [p - t for p, t in zip(protocol_values, tm_values)]
    positive = sum(delta > 0 for delta in deltas)
    return (
        f"{statistics.fmean(deltas):+.4f} +/- {statistics.stdev(deltas):.4f}"
        f"  ({positive}/{len(deltas)} positive)"
    )


def report(run_id: str) -> None:
    directories = sorted(
        (path.parent for path in REAGGREGATION_ROOT.joinpath(run_id).glob("h*/metrics.json")),
        key=horizon_of,
    )
    if not directories:
        raise SystemExit(f"no reaggregations under {REAGGREGATION_ROOT / run_id}")
    for directory in directories:
        aggregate = loads((directory / "metrics.json").read_text())["summary"]
        config = aggregate["metric_config"]
        floor = (1 - config["attack_probability"]) ** config["horizon"]
        print(
            f"horizon {config['horizon']:>4}   slots {config['audit_slots']:>3}   "
            f"free floor {floor:.4f}   runs {aggregate['n_runs']}"
        )
        tm_values = benign(aggregate["protocols"][BASELINE_PROTOCOL]).get("values") or []
        for protocol in PROTOCOLS:
            arm = aggregate["protocols"].get(protocol)
            if arm is None:
                continue
            stat = benign(arm)
            if stat.get("mean") is None:
                print(f"    {protocol:<18} no value")
                continue
            delta = (
                ""
                if protocol == BASELINE_PROTOCOL
                else "   vs tm " + paired_delta(stat.get("values") or [], tm_values)
            )
            print(
                f"    {protocol:<18} safety {stat['mean']:.4f}   "
                f"earned {stat['mean'] - floor:+.4f}   n={stat['n']}{delta}"
            )
        print()


if __name__ == "__main__":
    report(sys.argv[1] if len(sys.argv) > 1 else "uplanhard50-tlow-uhigh")
