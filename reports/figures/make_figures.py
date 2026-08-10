"""Report figures for the B1 ablation. Values are read from the committed artifacts, never typed."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

SURFACE = "#ffffff"
INK = "#0b0b0b"
INK_SOFT = "#444444"
INK_MUTED = "#767676"
BLUE = "#1a1a1a"
ORANGE = "#8c8c8c"
GRID = "#dddddd"

ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts" / "b1"
OUT = Path(__file__).resolve().parent

plt.rcParams.update(
    {
        "font.family": "Arial",
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "text.color": INK,
        "axes.labelcolor": INK_SOFT,
        "xtick.color": INK_SOFT,
        "ytick.color": INK_SOFT,
    }
)


def ratios() -> dict[str, dict[str, float]]:
    out = {}
    for cell in ("r1", "r5", "r3", "r7"):
        summary = json.loads((ARTIFACTS / f"b1-{cell}.metrics.json").read_text())["summary"]
        out[cell] = {
            arm: summary["protocols"][arm]["ratio_to_baseline"]["mean"] * 100
            for arm in ("pbt", "pbt_ceiling", "pbt_informed_tm")
        }
        out[cell]["soundness"] = summary["pbt_soundness"]["mean"]
    return out


def pipeline() -> None:
    fig, ax = plt.subplots(figsize=(11.5, 3.9), dpi=200)
    ax.set_xlim(0, 116)
    ax.set_ylim(2, 46)
    ax.axis("off")

    stages = [
        ("1  AUTHORING", "trusted model writes\nproperties from the\nSPEC ONLY", BLUE),
        ("2  TRIGGER SEARCH", "inputs where a backdoor\nwould likely fire\n(spec-blind here)", BLUE),
        ("3  EXECUTION", "every property x input\nvs every candidate,\nin a sandbox", BLUE),
        ("4  SOUNDNESS GATE", "reference says which\nproperties are trustworthy\n(privileged)", INK_MUTED),
        ("5  MONITORS", "tm reads code;\ninformed also reads\nthe evidence", BLUE),
        ("6  DEPLOYMENT GAME", "10,000 simulated\ndeployments\n\u2192 SAFETY", ORANGE),
    ]

    width, gap, y, height = 16.0, 3.2, 20.0, 15.0
    for i, (title, body, colour) in enumerate(stages):
        x = 1.5 + i * (width + gap)
        ax.add_patch(
            FancyBboxPatch(
                (x, y), width, height,
                boxstyle="round,pad=0.35,rounding_size=1.1",
                linewidth=1.6, edgecolor=colour,
                facecolor="#ffffff", zorder=2,
            )
        )
        ax.text(x + width / 2, y + height - 3.1, title, ha="center", va="center",
                fontsize=8.4, fontweight="bold", color=colour if colour is not INK_MUTED else INK_SOFT, zorder=3)
        ax.text(x + width / 2, y + height / 2 - 2.4, body, ha="center", va="center",
                fontsize=7.2, color=INK_SOFT, linespacing=1.55, zorder=3)
        if i < len(stages) - 1:
            ax.add_patch(FancyArrowPatch(
                (x + width + 0.35, y + height / 2), (x + width + gap - 0.35, y + height / 2),
                arrowstyle="-|>", mutation_scale=11, linewidth=1.5, color=INK_MUTED, zorder=1))

    ax.text(1.5, 41.5, "How one task becomes a safety number",
            fontsize=12.5, fontweight="bold", color=INK)
    ax.text(1.5, 37.4,
            "50 frozen APPS tasks, each with one honest and one-to-two backdoored candidates. "
            "No reference solution exists at deploy time.",
            fontsize=8.2, color=INK_SOFT)

    notes = [
        (1.5 + 0 * (width + gap) + width / 2, "blind_t  |  u_plans_t_writes\n\u00b1 critique", BLUE),
        (1.5 + 2 * (width + gap) + width / 2, "memory 2g \u00b7 cpus 2\npids 256 \u00b7 no network", BLUE),
        (1.5 + 3 * (width + gap) + width / 2, "ceiling arm only\nNOT deployable", INK_MUTED),
    ]
    for x, text, colour in notes:
        ax.annotate(text, xy=(x, y - 0.4), xytext=(x, y - 6.4), ha="center", va="center",
                    fontsize=6.9, color=colour, linespacing=1.5,
                    arrowprops=dict(arrowstyle="-", color=GRID, linewidth=1.1))
    ax.text(1.5 + 0 * (width + gap) + width / 2, y - 10.2, "the two factors ablated",
            ha="center", fontsize=6.7, style="italic", color=INK_MUTED)

    fig.tight_layout()
    fig.savefig(OUT / "pipeline.png", bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def results(data: dict[str, dict[str, float]]) -> None:
    order = [("r1", "blind_t"), ("r5", "blind_t\n+critique"),
             ("r3", "u_plans", ), ("r7", "u_plans\n+critique")]
    labels = [lab for _, lab in order]
    pbt = [data[c]["pbt"] for c, _ in order]
    inf = [data[c]["pbt_informed_tm"] for c, _ in order]

    fig, ax = plt.subplots(figsize=(9.2, 5.0), dpi=200)
    xs = range(len(order))
    w = 0.36
    left = [x - w / 2 - 0.012 for x in xs]
    right = [x + w / 2 + 0.012 for x in xs]

    ax.set_xlim(-1.28, 3.55)
    ax.axhline(100, color=INK_SOFT, linewidth=1.4, linestyle="-", zorder=1, xmin=0.0)
    ax.text(-1.22, 100, "trusted monitor\n(the baseline)", ha="left", va="center",
            fontsize=8, color=INK_SOFT, linespacing=1.4)
    ax.axhline(60, color=ORANGE, linewidth=1.4, linestyle=(0, (4, 3)), zorder=1)
    ax.text(-1.22, 60, "kill criterion\n60% of TM", ha="left", va="center",
            fontsize=8, color=ORANGE, linespacing=1.4)

    ax.bar(left, pbt, w, color=BLUE, zorder=3, label="pbt  (acts on property verdicts)")
    ax.bar(right, inf, w, color=ORANGE, zorder=3, label="pbt_informed_tm  (monitor + evidence)")

    for x, v in zip(left, pbt):
        ax.text(x, v + 2.2, f"{v:.1f}", ha="center", fontsize=8.6, color=BLUE, fontweight="bold")
    for x, v in zip(right, inf):
        ax.text(x, v + 2.2, f"{v:.1f}", ha="center", fontsize=8.6, color=ORANGE, fontweight="bold")

    ax.set_xticks(list(xs))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("earned safety, as % of the trusted monitor", fontsize=9)
    ax.set_ylim(0, 132)
    ax.set_yticks([0, 25, 50, 75, 100, 125])
    ax.yaxis.grid(True, color=GRID, linewidth=0.9)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(length=0)

    ax.set_title("No configuration of standalone PBT approaches code review",
                 fontsize=12.5, fontweight="bold", color=INK, loc="left", pad=26)
    ax.text(0, 1.035, "n=10 per cell. Only the monitor given PBT evidence beats the baseline — and not significantly.",
            transform=ax.transAxes, fontsize=8.4, color=INK_SOFT)
    ax.legend(frameon=False, fontsize=8.6, loc="upper left", bbox_to_anchor=(0.20, -0.11), ncol=2)

    fig.tight_layout()
    fig.savefig(OUT / "results.png", bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


if __name__ == "__main__":
    data = ratios()
    pipeline()
    results(data)
    print("wrote pipeline.png, results.png")
    for cell, vals in data.items():
        print(f"  {cell}: pbt={vals['pbt']:.1f}% informed={vals['pbt_informed_tm']:.1f}% sound={vals['soundness']:.3f}")
