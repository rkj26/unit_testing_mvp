"""Draw the audit-budget figure (fig:budgets) for the paper: each protocol's safety relative to
trusted monitoring, with 95% multinomial-bootstrap CI bands, at budgets 1/2/5/10%.

Reads reports/safety_paper_model_8arm.csv (the paper's per-sample safety model under this repo's
bootstrap; see analysis/safety_paper_model.py) and writes a PDF. The plotted quantity is the
(arm - monitor) difference and its [lo, hi] interval, so the monitor is the zero line -- this is
what tab:budgets tabulates.

    python analysis/plot_budgets.py \\
        --csv reports/safety_paper_model_8arm.csv --out /path/to/paper/figures/budgets.pdf
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

# display name -> (short label, colour, marker); monitor is the baseline (the zero line).
STYLE = [
    ("monitor + tests property",   "Mon + property",          "#0072B2", "o"),
    ("monitor + tests plain_v3",   "Mon + plain",             "#56B4E9", "P"),
    ("monitor + u plans property", "Mon + $U$-plan property", "#882255", "*"),
    ("tests property/10",          "Property tests",          "#D55E00", "s"),
    ("tests plain_v3/10",          "Plain tests",             "#009E73", "D"),
    ("u plans property/10",        "$U$-plan property tests", "#CC79A7", "^"),
    ("u plans plain_v3/10",        "$U$-plan plain tests",    "#E69F00", "v"),
]
BUDGETS = [0.01, 0.02, 0.05, 0.10]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--method", default="multinomial")
    a = ap.parse_args()

    df = pd.read_csv(a.csv)
    df = df[(df.method == a.method) & (df.budget.isin(BUDGETS))]

    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    ax.axhline(0.0, color="#2b2b28", lw=1.0, zorder=1)
    ax.text(BUDGETS[-1], 0.0, "  trusted monitoring", va="center", ha="left",
            fontsize=8, color="#2b2b28")
    for name, label, colour, marker in STYLE:
        rows = df[df.arm == name].set_index("budget").reindex(BUDGETS)
        ax.fill_between(BUDGETS, rows.paper_diff_lo, rows.paper_diff_hi, color=colour, alpha=0.15,
                        lw=0, zorder=2)
        ax.plot(BUDGETS, rows.paper_diff, color=colour, marker=marker, lw=1.8, ms=6, label=label,
                zorder=3)

    ax.set_xscale("log")
    ax.set_xticks(BUDGETS)
    ax.set_xticklabels([f"{b:.0%}" for b in BUDGETS])
    ax.minorticks_off()
    ax.set_xlabel("audit budget")
    ax.set_ylabel("safety minus trusted monitoring")
    ax.grid(alpha=0.2, lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(loc="lower right", fontsize=8, frameon=False, ncol=2)
    fig.tight_layout()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.out, bbox_inches="tight")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
