"""
Metadata-coverage bar chart of Section 3.3 (Figure 2).

    python scripts/reproduce_paper.py
    python figures/scripts/coverage_bars.py

Reads   analysis_output/paper_numbers.json
Writes  figures/coverage_bars.pdf, .png   share of records with a value for each field,
                                          for the full dataset and the 10 leaderboard sources

The script draws the coverage numbers of reproduce_paper.py and computes nothing itself,
so the figure always shows the values of the coverage table.

    python figures/scripts/coverage_bars.py --numbers other_numbers.json --out-dir /tmp/figs

draws the same chart for another numbers file. The rows of the chart are the entries of
FIELDS: a field that reproduce_paper.py computes is added to the chart by adding it there.
"""

import argparse
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "..")
PAPER_NUMBERS = os.path.join(SCRIPT_DIR, "..", "..", "analysis_output", "paper_numbers.json")

BLUE, BLUE_EDGE = "#A8C8EC", "#4A90D9"
ORANGE, ORANGE_EDGE = "#F8D2A8", "#C06A1C"
DGREY, MGREY = "#444444", "#CCCCCC"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "STIXGeneral", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "hatch.linewidth": 0.8,
})

# field in paper_numbers.json -> label, from the top of the chart down
FIELDS = [
    ("shots", "Shots"),
    ("harness", "Harness"),
    ("chain_of_thought", "CoT"),
    ("prompt_template", "Prompt\ntemplate"),
    ("temperature", "Tempr."),
]
BAR, GAP = 0.36, 0.02


def save(fig, name, out_dir=OUT_DIR):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(out_dir, f"{name}.{ext}"), dpi=200, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    where = "figures" if out_dir == OUT_DIR else os.path.normpath(out_dir)
    print(f"Saved {where}/{name}.pdf and .png")


def value_label(ax, value, y, edge):
    """The percentage beside a bar; a zero is set in bold in the colour of its series."""
    if value == 0:
        ax.text(1.6, y, "0.0%", va="center", ha="left", fontsize=8, color=edge, fontweight="bold", zorder=4)
    else:
        ax.text(value + 1.4, y, f"{value:.1f}%", va="center", ha="left", fontsize=7.5, color=DGREY, zorder=4)


def draw(numbers, out_dir=OUT_DIR, fields=FIELDS):
    """Draw the chart for the `coverage` and `dataset` sections of a paper_numbers.json."""
    coverage, dataset = numbers["coverage"], numbers["dataset"]
    full, subset = coverage["full_dataset"], coverage["leaderboard_subset"]
    fig, ax = plt.subplots(figsize=(3.3, 2.2))
    rows = list(reversed(fields))                       # barh counts from the bottom
    for y, (key, _) in enumerate(rows):
        upper, lower = y + (BAR + GAP) / 2, y - (BAR + GAP) / 2
        ax.barh(upper, full[key], height=BAR, color=BLUE, edgecolor=BLUE_EDGE, hatch="//", linewidth=0.8, zorder=3)
        ax.barh(lower, subset[key], height=BAR, color=ORANGE, edgecolor=ORANGE_EDGE, hatch="..", linewidth=0.8, zorder=3)
        value_label(ax, full[key], upper, BLUE_EDGE)
        value_label(ax, subset[key], lower, ORANGE_EDGE)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([label for _, label in rows], fontsize=8)
    ax.set_ylim(-1.75, len(rows) - 0.45)                # room for the legend under the bars
    ax.set_xlim(0, 112)
    ax.set_xticks(range(0, 101, 20))
    ax.set_xlabel("Coverage (%)", fontsize=8, color=DGREY)
    ax.tick_params(axis="x", labelsize=8, colors=DGREY, length=2.5)
    ax.tick_params(axis="y", length=0)
    ax.xaxis.grid(True, linestyle=":", linewidth=0.5, color=MGREY, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MGREY)
    handles = [
        Patch(facecolor=BLUE, edgecolor=BLUE_EDGE, hatch="//", linewidth=0.8,
              label=f"Full dataset ({dataset['total_records']:,})"),
        Patch(facecolor=ORANGE, edgecolor=ORANGE_EDGE, hatch="..", linewidth=0.8,
              label=f"Leaderboard subset ({dataset['leaderboard_subtotal']['records']:,})"),
    ]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 0.0), fontsize=7.5, frameon=False,
              handlelength=1.6, labelspacing=0.3, prop={"family": "DejaVu Sans", "size": 7.5})
    save(fig, "coverage_bars", out_dir)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Draw the metadata-coverage bar chart (Figure 2).")
    ap.add_argument("--numbers", default=PAPER_NUMBERS, help="numbers file (default: analysis_output/paper_numbers.json)")
    ap.add_argument("--out-dir", default=OUT_DIR, help="folder for the figure (default: figures/)")
    args = ap.parse_args(argv)
    if not os.path.exists(args.numbers):
        raise SystemExit(f"{os.path.normpath(args.numbers)} is missing. Run scripts/reproduce_paper.py first.")
    os.makedirs(args.out_dir, exist_ok=True)
    with open(args.numbers, encoding="utf-8") as fh:
        draw(json.load(fh), args.out_dir)


if __name__ == "__main__":
    main()
