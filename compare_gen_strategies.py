"""A/B(/C) compare gen-strategy runs by reading their metrics.json.

  .venv/bin/python compare_gen_strategies.py \
      blind_t=runs/apps-hard10 u_plans_t_writes=runs/apps-hard10-uplan u_writes=runs/apps-hard10-uwrite

Prints, per protocol, safety / FPR / evasion (mean ± 95% CI) for each arm side by side, then the
sound-suite and generation-health rates, then the key paired deltas. Designed for the capability
question: does eliciting a capable planner lift the DEPLOYABLE pbt (and tm+pbt / informed-tm) off the
audit floor without inflating false positives — and how close does it get to the non-deployable
pbt_ceiling upper bound.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROTOCOLS = ["tm", "pbt", "pbt_ceiling", "tm_plus_pbt", "tm_plus_pbt_ceiling", "pbt_informed_tm"]
METRICS = ["safety", "false_positive", "evasion"]


def load(run_dir: str) -> dict | None:
    p = Path(run_dir) / "metrics.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())["summary"]


def cell(stat: dict | None) -> str:
    if not stat:
        return "     —      "
    m = stat.get("mean")
    lo, hi = (stat.get("ci95") or [None, None])
    if m is None:
        return "     —      "
    half = (hi - lo) / 2 if lo is not None and hi is not None else 0.0
    return f"{m:6.3f}±{half:5.3f} (n{stat.get('n','?')})"


def get(summary: dict, proto: str, metric: str) -> dict | None:
    return (summary.get("protocols", {}).get(proto, {}) or {}).get(metric)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    arms: dict[str, dict] = {}
    for spec in sys.argv[1:]:
        label, _, run_dir = spec.partition("=")
        s = load(run_dir)
        if s is None:
            print(f"[skip] {label}: no metrics.json at {run_dir} (run not finished?)")
            continue
        arms[label] = s
    if not arms:
        print("no finished arms to compare yet.")
        return

    labels = list(arms)
    w = 24
    for metric in METRICS:
        print(f"\n================ {metric.upper()} (mean ± half-95%CI) ================")
        print(f"{'protocol':<22}" + "".join(f"{lab:<{w}}" for lab in labels))
        for proto in PROTOCOLS:
            print(f"{proto:<22}" + "".join(f"{cell(get(arms[lab], proto, metric)):<{w}}" for lab in labels))

    print("\n================ PBT SUITE HEALTH ================")
    print(f"{'metric':<22}" + "".join(f"{lab:<{w}}" for lab in labels))
    for key in ("pbt_soundness", "pbt_generation_health"):
        print(f"{key:<22}" + "".join(f"{cell(arms[lab].get(key)):<{w}}" for lab in labels))

    print("\n================ PAIRED DELTAS vs TM (within each arm) ================")
    dkeys = sorted({k for s in arms.values() for k in s.get("paired_deltas", {})})
    print(f"{'delta':<30}" + "".join(f"{lab:<{w}}" for lab in labels))
    for dk in dkeys:
        row = f"{dk:<30}"
        for lab in labels:
            d = arms[lab].get("paired_deltas", {}).get(dk)
            if not d:
                row += f"{'—':<{w}}"
            else:
                fp = d.get("fraction_positive")
                row += f"{d['mean']:+6.3f} (frac+{fp:.2f},n{d.get('n','?')})".ljust(w)
        print(row)

    print("\n================ SAFETY per-run values (paired by seed) ================")
    for proto in ("pbt", "pbt_ceiling", "tm_plus_pbt", "pbt_informed_tm"):
        print(f"\n  {proto}:")
        for lab in labels:
            v = get(arms[lab], proto, "safety")
            vals = v.get("values") if v else None
            print(f"    {lab:<20} {['%.3f' % x for x in vals] if vals else '—'}")


if __name__ == "__main__":
    main()
