"""
Factorial-grid figures of Section 4.

    python experiments/controlled_eval/scripts/compute_anova_per_benchmark.py
    python experiments/controlled_eval/scripts/compute_factorial_figure_stats.py
    python figures/scripts/factorial.py

Reads   experiments/controlled_eval/results/factorial_figure_stats.json
Writes  figures/factorial_eta.pdf, .png        share of score variance explained by each setting
        figures/factorial_mismatch.pdf, .png   mean score change when one setting differs

The script draws what the statistics file holds and computes nothing itself.
"""

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch, Rectangle

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "..")
STATS = os.path.join(SCRIPT_DIR, "..", "..", "experiments", "controlled_eval", "results",
                     "factorial_figure_stats.json")

BLUE, BLUE_EDGE = "#4A90D9", "#2F6DB0"
ORANGE, ORANGE_EDGE = "#E89A4F", "#C06A1C"
GREEN, GREEN_EDGE = "#2E7D4F", "#1B5233"
GREY, DGREY = "#999999", "#444444"
NOT_VARIED = "#F0F0F0"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "STIXGeneral", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "hatch.linewidth": 0.6,
})

# factor in the statistics file -> (legend label, fill, edge, hatch)
FACTORS = [
    ("format", "Prompt format", BLUE, BLUE_EDGE, None),
    ("n_shot", "n-shot (0 vs 5)", ORANGE, ORANGE_EDGE, "."),
    ("temperature", "Temperature (0.0 vs 0.7)", GREEN, GREEN_EDGE, "//"),
]
COLUMN_LABELS = {
    "plain_vs_cot": "plain↔\nCoT",
    "plain_vs_instruct": "plain↔\ninstr.",
    "shot_0_vs_5": "0↔5\nshot",
    "temp_00_vs_07": "temp\n0.0↔0.7",
    "seed_vs_seed": "seed↔\nseed",
}


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT_DIR, f"{name}.{ext}"), dpi=200, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    print(f"Saved figures/{name}.pdf and .png")


def draw_eta(stats):
    """Grouped bars: variance explained per benchmark, with bootstrap intervals."""
    order, names = stats["benchmark_order"], stats["display_names"]
    fig, ax = plt.subplots(figsize=(3.3, 2.55))
    width = 0.27
    for b, bench in enumerate(order):
        for f, (key, _, fill, edge, hatch) in enumerate(FACTORS):
            cell = stats["eta"][bench].get(key)
            if cell is None:                       # the setting was not varied on this benchmark
                continue
            x = b + (f - 1) * width
            eta, (low, high) = cell["eta_pct"], cell["ci_pct"]
            ax.bar(x, eta, width, color=fill, edgecolor=edge, hatch=hatch, linewidth=0.7, zorder=3)
            ax.errorbar(x, eta, yerr=[[eta - low], [high - eta]], color=GREY, linewidth=0.7,
                        capsize=1.6, capthick=0.7, zorder=4)
            if cell["sig"]["marker"]:
                ax.text(x, high + 2.5, cell["sig"]["marker"], ha="center", va="bottom", fontsize=7)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([names[b] for b in order], rotation=25, ha="right", rotation_mode="anchor", fontsize=7.5)
    ax.set_ylim(0, 108)
    ax.set_yticks(range(0, 101, 20))
    ax.set_ylabel(r"Variance explained, $\eta^2$ (%)", fontsize=8)
    ax.tick_params(axis="y", labelsize=7.5, colors=DGREY, length=2.5)
    ax.tick_params(axis="x", length=2.5)
    ax.yaxis.grid(True, linestyle=":", linewidth=0.5, color="#BBBBBB", zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#BBBBBB")
    handles = [Patch(facecolor=fill, edgecolor=edge, hatch=hatch, linewidth=0.7, label=label)
               for _, label, fill, edge, hatch in FACTORS]
    ax.legend(handles=handles, loc="upper right", bbox_to_anchor=(1.02, 1.04), fontsize=6.5,
              frameon=False, handlelength=1.6, labelspacing=0.25)
    save(fig, "factorial_eta")


def draw_mismatch(stats):
    """Heat map: mean absolute score change (pp) when exactly one setting differs."""
    order, names, columns = stats["benchmark_order"], stats["display_names"], stats["mismatch_columns"]
    cells = stats["mismatch"]
    top = max(c["mean_abs_delta_pp"] for row in cells.values() for c in row.values() if c)
    cmap = LinearSegmentedColormap.from_list("change", [(0.0, "#FFFDFB"), (0.22, "#F5D3B0"), (0.45, "#EAA566"),
                                                        (0.69, "#D98A3D"), (1.0, "#B96B1B")])
    fig, ax = plt.subplots(figsize=(3.3, 2.4))
    for r, bench in enumerate(order):
        for c, column in enumerate(columns):
            cell = cells[bench].get(column)
            if cell is None:                       # not varied in that arm
                colour, text, dark = NOT_VARIED, "–", False
            else:
                value = cell["mean_abs_delta_pp"]
                colour, text, dark = cmap(value / top), f"{value:.1f}", value / top > 0.6
            ax.add_patch(Rectangle((c, r), 1, 1, facecolor=colour, edgecolor="white", linewidth=1.2))
            ax.text(c + 0.5, r + 0.5, text, ha="center", va="center", fontsize=7.5,
                    color="white" if dark else "black")
    ax.set_xlim(0, len(columns))
    ax.set_ylim(len(order), 0)
    ax.set_xticks([c + 0.5 for c in range(len(columns))])
    ax.set_xticklabels([COLUMN_LABELS[c] for c in columns], fontsize=7)
    ax.set_yticks([r + 0.5 for r in range(len(order))])
    ax.set_yticklabels([names[b] for b in order], fontsize=8)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    save(fig, "factorial_mismatch")


def main():
    if not os.path.exists(STATS):
        raise SystemExit(f"{os.path.normpath(STATS)} is missing. Run "
                         "experiments/controlled_eval/scripts/compute_factorial_figure_stats.py first.")
    with open(STATS, encoding="utf-8") as fh:
        stats = json.load(fh)
    draw_eta(stats)
    draw_mismatch(stats)


if __name__ == "__main__":
    main()
