"""Repeated-measures (within-subject) format ANOVA for the log-likelihood benchmarks.

Prompt format is a WITHIN-subject factor: each subject (a model, or a model x seed
cell) is scored under plain/instruct/cot. A one-way between-groups ANOVA wrongly puts
the large between-subject variance (e.g. a 1.5B vs a 14B model) into the error term
and masks the format effect. The repeated-measures ANOVA blocks on the subject:

  SS_treatment (format), df = k-1
  SS_subject   (block),  df = n-1        <- removed from error
  SS_error = SS_total - SS_treatment - SS_subject, df = (n-1)(k-1)
  F = (SS_treatment/df_t) / (SS_error/df_e)

Also reports partial eta^2 = SS_treatment / (SS_treatment + SS_error) and, as a
non-parametric cross-check, the Friedman test (same blocking). Subjects: models for
the seed-deterministic MMLU/GPQA; (model,seed) cells for ARC/WinoGrande/OpenBookQA.
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from common.stats import chi2_sf, f_sf, friedman  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
FORMATS = ("plain", "instruct", "cot")


def load(name):
    p = os.path.join(RESULTS_DIR, name)
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if os.path.exists(p) else []


def rm_anova(mat):  # mat: list of rows (subjects), each len k (formats)
    n = len(mat); k = len(mat[0])
    grand = sum(v for r in mat for v in r) / (n * k)
    col_means = [sum(r[c] for r in mat) / n for c in range(k)]
    row_means = [sum(r) / k for r in mat]
    ss_t = n * sum((cm - grand) ** 2 for cm in col_means)
    ss_s = k * sum((rm - grand) ** 2 for rm in row_means)
    ss_tot = sum((v - grand) ** 2 for r in mat for v in r)
    ss_e = ss_tot - ss_t - ss_s
    df_t, df_e = k - 1, (n - 1) * (k - 1)
    F = (ss_t / df_t) / (ss_e / df_e) if ss_e > 1e-12 else float("inf")
    p = f_sf(F, df_t, df_e) if ss_e > 1e-12 else 0.0
    peta2 = 100 * ss_t / (ss_t + ss_e) if (ss_t + ss_e) else 0.0
    chi, _df, _w = friedman(mat)
    return F, df_t, df_e, p, peta2, chi, chi2_sf(chi, k - 1), n


def subjects(rows, bench, unit):
    d = defaultdict(dict)
    for r in rows:
        if r.get("benchmark") == bench and r.get("status", "ok") == "ok" and r.get("score") is not None \
                and r.get("n_shot") == 5 and r.get("prompt_format") in FORMATS:
            if "Phi-3.5" in r["model_id"]:
                continue
            key = r["model_id"] if unit == "model" else (r["model_id"], r["random_seed"])
            d[key][r["prompt_format"]] = r["score"]
    return [[b[f] for f in FORMATS] for b in d.values() if all(f in b for f in FORMATS)]


# benchmark -> (result files, the unit that is scored under every format: a model, or a model and seed).
# A benchmark is added to the analysis by adding it here.
SEED_FILES = ("generalization_hf.jsonl", "generalization_multiseed.jsonl")
MODEL_FILES = ("mmlu_gpqa_8models.jsonl",)
DESIGNS = {
    "ARC-Challenge": (SEED_FILES, "cell"), "WinoGrande": (SEED_FILES, "cell"), "OpenBookQA": (SEED_FILES, "cell"),
    "MMLU": (MODEL_FILES, "model"), "GPQA": (MODEL_FILES, "model"),
}


def main():
    print(f"{'benchmark':15}{'subj':6}{'n':4}{'F':>8}{'df':>8}{'p (RM)':>10}{'p-eta2':>8}{'Friedman p':>12}")
    print("-" * 71)
    for bench, (files, unit) in DESIGNS.items():
        rows = [r for name in files for r in load(name)]
        m = subjects(rows, bench, unit)
        if len(m) < 2:
            print(f"{bench:15} (insufficient)"); continue
        F, dft, dfe, p, pe, chi, fp, n = rm_anova(m)
        print(f"{bench:15}{unit:6}{n:4}{F:8.2f}{f'({dft},{dfe})':>8}{p:10.4f}{pe:7.0f}%{fp:12.2e}")


if __name__ == "__main__":
    main()
