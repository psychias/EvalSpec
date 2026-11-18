"""Aggregate factorial-grid statistics for the paper's two-panel ANOVA figure.

Panel A: one-way eta-squared per benchmark x factor (copied from
anova_per_benchmark.json, i.e. the published values) plus bootstrap 95% CIs
recomputed from the raw run records with the same data selection.

Panel B: configuration-mismatch matrix -- mean absolute score delta (pp) when
exactly one factor differs and every other factor is held fixed.

Writes results/factorial_figure_stats.json. Stdlib + scipy only, matching
compute_anova_per_benchmark.py.
"""

import json
import os
import random
import sys
from collections import defaultdict

try:
    from scipy.stats import f_oneway  # noqa: F401  (parity with sibling script)
except ImportError:
    sys.exit("scipy is required (pip install scipy)")

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "..", "results")

BENCHMARKS = ["gsm8k", "mmlu", "gpqa", "ARC-Challenge", "WinoGrande", "OpenBookQA"]
DISPLAY = {
    "gsm8k": "GSM8K",
    "mmlu": "MMLU",
    "gpqa": "GPQA",
    "ARC-Challenge": "ARC-C",
    "WinoGrande": "WinoGrande",
    "OpenBookQA": "OBQA",
}

# Significance markers. Format factor: GSM8K is the one-way test (reported in
# the paper, p=1.6e-05); the four log-likelihood significances come from the
# repeated-measures ANOVAs reported in S4.3 / the Factorial Grid appendix
# (ARC F(2,22)=23.4 p<1e-4; WinoGrande F(2,22)=16.2 p<1e-4; MMLU F(2,12)=10.2
# p=.003; OpenBookQA F(2,22)=5.7 p=.01; GPQA null). n-shot / temperature use
# the one-way p from anova_per_benchmark.json (filled in below).
RM_FORMAT_SIG = {
    "ARC-Challenge": {"marker": "†", "p": 1e-4},
    "WinoGrande": {"marker": "†", "p": 1e-4},
    "mmlu": {"marker": "†", "p": 0.003},
    "OpenBookQA": {"marker": "†", "p": 0.01},
}

N_BOOT = 10_000
SEED = 12345


def load_jsonl(name):
    path = os.path.join(RESULTS, name)
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("status") != "ok" or rec.get("score") is None:
                continue
            rows.append(rec)
    return rows


def eta_squared(groups):
    all_scores = [s for g in groups for s in g]
    n = len(all_scores)
    grand = sum(all_scores) / n
    ss_total = sum((s - grand) ** 2 for s in all_scores)
    if ss_total == 0:
        return 0.0
    ss_between = sum(len(g) * ((sum(g) / len(g)) - grand) ** 2 for g in groups)
    return ss_between / ss_total


def bootstrap_ci(groups, rng):
    """Percentile bootstrap of eta-squared, resampling within each group
    (stratified, preserving the design's group sizes)."""
    stats = []
    for _ in range(N_BOOT):
        res = [[rng.choice(g) for _ in g] for g in groups]
        stats.append(eta_squared(res))
    stats.sort()
    lo = stats[int(0.025 * N_BOOT)]
    hi = stats[int(0.975 * N_BOOT)]
    return 100 * lo, 100 * hi


def main():
    with open(os.path.join(RESULTS, "anova_per_benchmark.json"), encoding="utf-8") as fh:
        anova = json.load(fh)

    # Raw pools. Mirror compute_anova_per_benchmark.py's selection for the
    # ANOVA-backed panels (controlled_eval + gpqa + generalization_hf);
    # generalization_multiseed.jsonl additionally feeds the seed column.
    core = (
        load_jsonl("controlled_eval_results.jsonl")
        + load_jsonl("gpqa_results.jsonl")
        + load_jsonl("generalization_hf.jsonl")
    )
    multiseed = load_jsonl("generalization_multiseed.jsonl")
    pool = core + multiseed

    rng = random.Random(SEED)
    eta_out = {}
    for bench in BENCHMARKS:
        rows5 = [r for r in core if r["benchmark"] == bench and int(r["n_shot"]) == 5]
        by_fmt = defaultdict(list)
        for r in rows5:
            by_fmt[r["prompt_format"]].append(float(r["score"]))
        fmt_groups = [by_fmt[k] for k in sorted(by_fmt)]

        # --- format ---
        rep = anova[bench]["format"]["anova"]
        eta_recomputed = 100 * eta_squared(fmt_groups)
        assert abs(eta_recomputed - 100 * rep["eta_squared"]) < 0.1, (
            f"{bench} format eta mismatch: recomputed {eta_recomputed:.2f} "
            f"vs published {100 * rep['eta_squared']:.2f}"
        )
        lo, hi = bootstrap_ci(fmt_groups, rng)
        if bench == "gsm8k":
            sig = {"marker": "*", "p": rep["p"]}
        else:
            sig = RM_FORMAT_SIG.get(bench, {"marker": "", "p": rep["p"]})
        eta_out.setdefault(bench, {})["format"] = {
            "eta_pct": round(100 * rep["eta_squared"], 1),
            "ci_pct": [round(lo, 1), round(hi, 1)],
            "sig": sig,
        }

        # --- n-shot (pooled variant: the published one) ---
        rep_ns = anova["_nshot"][bench]["pooled"]["anova"]
        by_ns = defaultdict(list)
        for r in core:
            if r["benchmark"] == bench and int(r["n_shot"]) in (0, 5):
                by_ns[int(r["n_shot"])].append(float(r["score"]))
        ns_groups = [by_ns[k] for k in sorted(by_ns)]
        eta_ns = 100 * eta_squared(ns_groups)
        assert abs(eta_ns - 100 * rep_ns["eta_squared"]) < 0.1, (
            f"{bench} n-shot eta mismatch: {eta_ns:.2f} vs {100 * rep_ns['eta_squared']:.2f}"
        )
        lo, hi = bootstrap_ci(ns_groups, rng)
        eta_out[bench]["n_shot"] = {
            "eta_pct": round(100 * rep_ns["eta_squared"], 1),
            "ci_pct": [round(lo, 1), round(hi, 1)],
            "sig": {"marker": "*" if rep_ns["p"] < 0.05 else "", "p": rep_ns["p"]},
        }

        # --- temperature (varied only in the gsm8k/bbh arm) ---
        by_temp = defaultdict(list)
        for r in rows5:
            by_temp[float(r["temperature"])].append(float(r["score"]))
        if len(by_temp) >= 2:
            rep_t = anova[bench]["temperature"]["anova"]
            t_groups = [by_temp[k] for k in sorted(by_temp)]
            lo, hi = bootstrap_ci(t_groups, rng)
            eta_out[bench]["temperature"] = {
                "eta_pct": round(100 * rep_t["eta_squared"], 1),
                "ci_pct": [round(lo, 1), round(hi, 1)],
                "sig": {"marker": "*" if rep_t["p"] < 0.05 else "", "p": rep_t["p"]},
            }
        else:
            eta_out[bench]["temperature"] = None

    # ------------------------------------------------------------------
    # Panel B: mean |delta| pp with exactly one factor mismatched.
    # Non-n-shot columns are restricted to the 5-shot stratum.
    # ------------------------------------------------------------------
    def key(r, without):
        parts = {
            "model": r["model_id"],
            "format": r["prompt_format"],
            "n_shot": int(r["n_shot"]),
            "temp": float(r["temperature"]),
            "seed": int(r["random_seed"]),
        }
        parts.pop(without)
        return tuple(sorted(parts.items()))

    def mismatch(bench, target, level_a, level_b, restrict_5shot):
        field = {"format": "prompt_format", "n_shot": "n_shot", "temp": "temperature",
                 "seed": "random_seed"}[target]
        cells = defaultdict(dict)
        for r in pool:
            if r["benchmark"] != bench:
                continue
            if restrict_5shot and int(r["n_shot"]) != 5:
                continue
            lvl = r[field]
            lvl = float(lvl) if target == "temp" else (int(lvl) if target in ("n_shot", "seed") else lvl)
            cells[key(r, target)][lvl] = float(r["score"])
        deltas = []
        for levels in cells.values():
            if level_a == "any":  # all pairwise (seed column)
                ks = sorted(levels)
                for i in range(len(ks)):
                    for j in range(i + 1, len(ks)):
                        deltas.append(abs(levels[ks[i]] - levels[ks[j]]))
            elif level_a in levels and level_b in levels:
                deltas.append(abs(levels[level_a] - levels[level_b]))
        if not deltas:
            return None, 0
        return sum(deltas) / len(deltas), len(deltas)

    COLUMNS = [
        ("plain_vs_cot", "format", "plain", "cot", True),
        ("plain_vs_instruct", "format", "plain", "instruct", True),
        ("shot_0_vs_5", "n_shot", 0, 5, False),
        ("temp_00_vs_07", "temp", 0.0, 0.7, True),
        ("seed_vs_seed", "seed", "any", None, True),
    ]
    mismatch_out = {}
    for bench in BENCHMARKS:
        mismatch_out[bench] = {}
        for col, target, a, b, r5 in COLUMNS:
            val, n = mismatch(bench, target, a, b, r5)
            mismatch_out[bench][col] = None if val is None else {
                "mean_abs_delta_pp": round(val, 2), "n_pairs": n,
            }

    # Sanity gates
    gsm_ci = eta_out["gsm8k"]["format"]["ci_pct"]
    assert abs(gsm_ci[0] - 14.1) <= 1.5 and abs(gsm_ci[1] - 44.8) <= 1.5, (
        f"GSM8K format CI {gsm_ci} drifted from published [14.1, 44.8]"
    )
    gsm_ns = mismatch_out["gsm8k"]["shot_0_vs_5"]["mean_abs_delta_pp"]
    assert abs(gsm_ns - 30.7) <= 2.0, (
        f"GSM8K 0-vs-5-shot mismatch {gsm_ns} drifted from published 30.7 pp gap"
    )

    out = {
        "benchmark_order": BENCHMARKS,
        "display_names": DISPLAY,
        "eta": eta_out,
        "mismatch": mismatch_out,
        "mismatch_columns": [c[0] for c in COLUMNS],
        "meta": {
            "n_boot": N_BOOT,
            "rng_seed": SEED,
            "sources": [
                "controlled_eval_results.jsonl", "gpqa_results.jsonl",
                "generalization_hf.jsonl", "generalization_multiseed.jsonl",
            ],
            "notes": "eta values copied from anova_per_benchmark.json (one-way, "
                     "5-shot stratum for format/temperature; pooled 0-vs-5 for "
                     "n-shot). Dagger markers = repeated-measures significance "
                     "reported in the paper.",
        },
    }
    out_path = os.path.join(RESULTS, "factorial_figure_stats.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"Wrote {os.path.normpath(out_path)}")
    print(f"GSM8K format eta 27.4, bootstrap CI {gsm_ci}")
    for bench in BENCHMARKS:
        row = {c: (mismatch_out[bench][c] or {}).get("mean_abs_delta_pp") for c in out["mismatch_columns"]}
        print(DISPLAY[bench], row)


if __name__ == "__main__":
    main()
