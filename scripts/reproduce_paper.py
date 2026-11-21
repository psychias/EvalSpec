#!/usr/bin/env python3
"""
reproduce_paper.py — regenerate every headline number in the paper from the
repository's data and experiment outputs, in one command.

This is the single source of truth for the paper's quantitative claims. It
rebuilds the canonical aggregate from ``data/`` (ArXiv = the per-benchmark
``llm/`` extraction only; audit-sample copies and the naive extraction are
excluded), recomputes the dataset, coverage and audit numbers of §3, and reads the
experiment results of §4, §5 and Appendix M from ``experiments/``. All values are written
to ``analysis_output/paper_numbers.json`` and printed as a report.

Usage
-----
    python scripts/reproduce_paper.py                 # recompute and write paper_numbers.json
    python scripts/reproduce_paper.py --no-rebuild    # skip the (slow) aggregate rebuild
    python scripts/reproduce_paper.py --list          # the sections and what each computes
    python scripts/reproduce_paper.py --only coverage,collisions_3_3
    python scripts/reproduce_paper.py --data FOLDER   # another copy of the dataset

Extending
---------
The script is a list of sections (``SECTIONS`` at the end of the file). A section has a
key in paper_numbers.json, a function that computes its numbers and a function that
writes its lines of the report. A new analysis is a new entry in that list.

The metadata fields of the coverage table are the entries of ``COVERAGE_FIELDS``, and
the sources of the leaderboard subset are ``LEADERBOARD_SOURCES``. The functions take
their rows and file paths as arguments, so they can be imported and run on other data.

Determinism: everything here is a pure function of the on-disk data plus the
seeded experiment outputs. No network, no randomness. The only non-reproducible
inputs are the upstream dataset-build steps (LLM extraction, leaderboard
fetches), which are documented separately in the README.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import collision_prevalence as cp
import dataset_access as ds

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_OUT = ROOT / "analysis_output"
EXP = ROOT / "experiments"

# Where each experiment section reads its results.
EXPERIMENT_FILES = {
    "factorial_grid": EXP / "controlled_eval" / "results" / "controlled_eval_results.jsonl",
    "scoring_mode_e2": EXP / "scoring_mode_eval" / "scoring_mode_results.jsonl",
    "harness_version_e3": EXP / "harness_reeval" / "version_compare" / "results" / "full_version_runs.jsonl",
    "judge_sensitivity": EXP / "judge_sensitivity" / "results" / "judge_runs.jsonl",
    "bbh_protocol": EXP / "bbh_protocol" / "sealion_provenance" / "olv2_gemma2_9b_bbh.json",
}

# Sources that make up the "10-source leaderboard subset" (§3.1, §3.3). ArXiv
# and Papers With Code are not leaderboards and are excluded from the subset;
# both are included in the full-dataset totals.
LEADERBOARD_SOURCES = {
    "open_llm_leaderboard_v2", "alpacaeval2", "bfcl", "bigcodebench",
    "chatbot_arena", "evalplus", "hf_model_card", "wildbench",
    "swe_bench", "mt_bench",
}
ARXIV_SOURCES = {"arxiv_html_llm", "arxiv_html_naive"}
OLV2 = cp.OLV2
# Benchmarks on which OLv2 is compared with the other sources (App. F): normalised name -> name in the report.
OLV2_GAP_BENCHMARKS = {"bbh": "BBH", "mmlupro": "MMLU-Pro"}


# --------------------------------------------------------------------------- #
# Coverage field predicates — match src/analysis/coverage_audit.py exactly so
# the coverage numbers of §3.3 are consistent with the audited methodology.
# --------------------------------------------------------------------------- #
def _present(value) -> bool:
    s = "" if value is None else str(value).strip()
    return s != "" and s.lower() != "unknown" and s.lower() != "nan"


def _prompt_present(value) -> bool:
    s = "" if value is None else str(value).strip()
    return s not in ("", "standard") and s.lower() != "nan"


def _is_cot(cot_flag, prompt_template) -> bool:
    """The record says the evaluation used chain-of-thought."""
    pt = ("" if prompt_template is None else str(prompt_template)).lower()
    flag = str(cot_flag).strip().lower() not in ("", "none", "false", "0", "nan")
    return flag or ("chain" in pt) or ("cot" in pt)


def _cot_recorded(cot_flag, prompt_template) -> bool:
    """The record says whether the evaluation used chain-of-thought, yes or no."""
    return str(cot_flag).strip().lower() in ("false", "0") or _is_cot(cot_flag, prompt_template)


# Field of the coverage table -> whether a row of all_results.csv has a value for it.
# A field added here is computed for the full dataset, the leaderboard subset and every
# source; add it to COVERAGE_REPORT as well to show it in the report.
# chain_of_thought: the status is recorded, as yes or as no (a record with 0 shots
# counts for shots in the same way). cot_true: the records that say yes.
COVERAGE_FIELDS: dict[str, Callable[[dict], bool]] = {
    "shots": lambda r: _present(r.get("shots")),
    # the harness of a record is its eval_library.name (App. C)
    "harness": lambda r: _present(r.get("eval_library", r.get("harness"))),
    "prompt_template": lambda r: _prompt_present(r.get("prompt_template")),
    "temperature": lambda r: _present(r.get("temperature")),
    "chain_of_thought": lambda r: _cot_recorded(r.get("chain_of_thought"), r.get("prompt_template")),
    "cot_true": lambda r: _is_cot(r.get("chain_of_thought"), r.get("prompt_template")),
}
# The fields the report prints, in the order of Figure 2.
COVERAGE_REPORT = ["shots", "harness", "chain_of_thought", "prompt_template", "temperature"]


# --------------------------------------------------------------------------- #
# §3.1 — dataset composition
# --------------------------------------------------------------------------- #
def load_aggregate(rebuild: bool = False, path: Path | None = None) -> list[dict]:
    """Rebuild the canonical aggregate (optional) and return its rows."""
    if rebuild:
        from eee_eval.analysis import aggregate_results
        aggregate_results.aggregate(ds.DATA)
    path = path or ds.AGGREGATE_CSV
    if not path.exists():
        sys.exit(ds.FETCH_HINT)
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def dataset_numbers(rows: list[dict], leaderboards=None) -> dict:
    leaderboards = LEADERBOARD_SOURCES if leaderboards is None else leaderboards
    by_source = defaultdict(list)
    for r in rows:
        by_source[r["source"]].append(r)

    def stats(src_rows):
        return {
            "records": len(src_rows),
            "models": len({r["model_id"] for r in src_rows}),
            "benchmarks": len({r["benchmark"] for r in src_rows}),
        }

    per_source = {s: stats(rs) for s, rs in sorted(by_source.items())}
    lb_rows = [r for r in rows if r["source"] in leaderboards]
    arxiv_rows = [r for r in rows if r["source"] in ARXIV_SOURCES]
    return {
        "total_records": len(rows),
        "total_models": len({r["model_id"] for r in rows}),
        "total_benchmarks": len({r["benchmark"] for r in rows}),
        "leaderboard_subtotal": stats(lb_rows),
        "arxiv": stats(arxiv_rows),
        "per_source": per_source,
    }


def coverage(rows: list[dict], fields=None) -> dict:
    """The share of `rows`, in percent, that has a value for each field."""
    fields = COVERAGE_FIELDS if fields is None else fields
    n = len(rows)
    if n == 0:
        return {name: 0.0 for name in fields}
    return {name: round(100 * sum(bool(has_value(r)) for r in rows) / n, 1) for name, has_value in fields.items()}


def coverage_numbers(rows: list[dict], fields=None, leaderboards=None) -> dict:
    """Coverage of the full dataset, of the leaderboard subset and of each source in it (§3.3)."""
    leaderboards = LEADERBOARD_SOURCES if leaderboards is None else leaderboards

    def cover(subset):
        return coverage(subset, fields)

    subset = [r for r in rows if r["source"] in leaderboards]
    tail = [r for r in subset if r["source"] != OLV2]
    per_source = {}
    for src in sorted(leaderboards):
        src_rows = [r for r in subset if r["source"] == src]
        per_source[src] = {"n": len(src_rows), **cover(src_rows)}
    return {"full_dataset": cover(rows), "leaderboard_subset": cover(subset),
            "nine_source_excl_olv2": cover(tail),
            "full_n": len(rows), "subset_n": len(subset), "nine_source_n": len(tail),
            "per_source": per_source}


def collision_numbers(path: Path | None = None) -> dict:
    """Section 3.3 collisions and the OLv2 direction of App. F (scripts/collision_prevalence.py)."""
    _rows, cells = cp.load_cells(path)
    out = cp.prevalence(cells)
    gaps = cp.reference_gaps(cells, OLV2)
    for bench in OLV2_GAP_BENCHMARKS:
        g = gaps.get(bench, [])
        out[f"olv2_{bench}"] = {"pairs": len(g), "olv2_lower": sum(1 for x in g if x > 0),
                                "median_gap_pp": round(statistics.median(g), 1) if g else None}
    return out


def arxiv_score_presence() -> dict:
    """§3.2 structural-presence check over the canonical ArXiv extraction."""
    n = nn = 0
    for rec in ds.arxiv_records():
        for er in rec.get("evaluation_results", []):
            n += 1
            if (er.get("score_details") or {}).get("score") not in ("", None):
                nn += 1
    return {"arxiv_records": n, "non_null_score": nn,
            "pct": round(100 * nn / n, 1) if n else 0.0}


# --------------------------------------------------------------------------- #
# §3.2 — annotation audits
# --------------------------------------------------------------------------- #
def _read_csv_rows(path: Path) -> list[dict]:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            with open(path, encoding=enc) as fh:
                return list(csv.DictReader(fh))
        except UnicodeDecodeError:
            continue
    return []


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes", "y")


def score_audit() -> dict:
    rows = _read_csv_rows(ds.annotation_file("annotation_score_verification.csv"))
    # §3.2 score-verification audit. The verdict_type column separates the two
    # axes: 'score' rows are the pipeline's extractions (the precision basis);
    # 'recall' rows are paper-reported scores the pipeline missed (appended as
    # correct=FALSE during the senior-annotator re-audit). agreement_pct is
    # precision over the 'score' rows; recall is captured / reported.
    score_rows = [r for r in rows if (r.get("verdict_type") or "score") == "score"]
    missed = sum(1 for r in rows if r.get("verdict_type") == "recall")
    correct = sum(1 for r in score_rows if _truthy(r.get("correct")))
    captured = len(score_rows)
    reported = captured + missed
    per_paper = {}
    for r in rows:                                    # Table 4
        p = per_paper.setdefault(r.get("paper_title") or r.get("paper_folder"),
                                 {"entries": 0, "correct": 0, "missed": 0})
        if r.get("verdict_type") == "recall":
            p["missed"] += 1
        else:
            p["entries"] += 1
            p["correct"] += _truthy(r.get("correct"))
    for p in per_paper.values():
        p["precision_pct"] = round(100 * p["correct"] / p["entries"], 1) if p["entries"] else 0.0
        p["recall_pct"] = round(100 * p["entries"] / (p["entries"] + p["missed"]), 1)
    return {"entries": captured, "correct": correct, "non_matches": captured - correct,
            "agreement_pct": round(100 * correct / captured, 1) if captured else 0.0,
            "missed": missed,
            "recall_pct": round(100 * captured / reported, 1) if reported else 0.0,
            "per_paper": per_paper}


def harness_audit() -> dict:
    # Precision is computed over the verdict_type rows that 'correct' actually
    # judges: 'harness' rows for the with-harness pool, 'abstention' rows for the
    # without-harness pool. ('score'/'recall' rows carry value/coverage defects
    # surfaced in the re-audit and are excluded from the harness-call precision.)
    def precision(path, vtype):
        rows = [r for r in _read_csv_rows(path) if (r.get("verdict_type") or vtype) == vtype]
        ok = sum(1 for r in rows if _truthy(r.get("correct")))
        return {"rows": len(rows), "correct": ok,
                "pct": round(100 * ok / len(rows), 1) if rows else 0.0}
    # Within the with-harness pool, a row is attributable when the paper names a
    # harness for that (model, benchmark) cell: the annotation is not "unknown".
    def unknown(v):
        return (v or "").strip().lower() in ("", "unknown")
    with_path = ds.annotation_file("annotation_eval_harness_WITH.csv")
    with_rows = [r for r in _read_csv_rows(with_path) if (r.get("verdict_type") or "harness") == "harness"]
    att = [r for r in with_rows if not unknown(r.get("annotation"))]
    wrong = [r for r in att if not _truthy(r.get("correct"))]
    named_ok = len(att) - len(wrong)
    breakdown = {"attributable": len(att), "named_correctly": named_ok,
                 "named_correctly_pct": round(100 * named_ok / len(att), 1) if att else 0.0,
                 "missed": sum(1 for r in wrong if unknown(r.get("eval_library"))),
                 "named_wrongly": sum(1 for r in wrong if not unknown(r.get("eval_library"))),
                 "not_attributable": len(with_rows) - len(att),
                 "abstained_correctly": sum(1 for r in with_rows
                                            if unknown(r.get("annotation")) and _truthy(r.get("correct")))}
    return {"with_harness": {**precision(with_path, "harness"), **breakdown},
            "without_harness": precision(ds.annotation_file("annotation_eval_harness_WITHOUT.csv"), "abstention")}


def metadata_audit() -> dict:
    """Section 3.2 / Table 5: extracted metadata values against a second reading of the paper.

    verdict_type 'metadata' marks a value the paper states (correct = the two readings
    agree); 'default' marks a value the paper never states.
    """
    rows = _read_csv_rows(ds.annotation_file("annotation_metadata_fields.csv"))

    def summary(sub):
        stated = [r for r in sub if r.get("verdict_type") == "metadata"]
        agree = sum(1 for r in stated if _truthy(r.get("correct")))
        return {"values": len(sub), "stated": len(stated), "agree": agree,
                "agreement_pct": round(100 * agree / len(stated), 1) if stated else 0.0,
                "defaults_pct": round(100 * (len(sub) - len(stated)) / len(sub), 1) if sub else 0.0}

    def by(key):
        groups = defaultdict(list)
        for r in rows:
            groups[r.get(key)].append(r)
        return {k: summary(v) for k, v in sorted(groups.items())}

    return {**summary(rows), "per_field": by("field"), "per_paper": by("paper_title")}


# --------------------------------------------------------------------------- #
# §4, §5, Appendix M — experiments
# --------------------------------------------------------------------------- #
MISSING_RESULTS: list[str] = []      # experiment result files that are not on disk


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        MISSING_RESULTS.append(ds.shown(path))
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _eta_and_f(groups: list[list[float]]):
    from scipy.stats import f_oneway
    vals = [v for g in groups for v in g]
    n = len(vals)
    if n == 0 or sum(len(g) for g in groups) == 0:
        return None
    grand = sum(vals) / n
    ss_tot = sum((v - grand) ** 2 for v in vals)
    ss_btw = sum(len(g) * (sum(g) / len(g) - grand) ** 2 for g in groups if g)
    eta2 = ss_btw / ss_tot if ss_tot else float("nan")
    F = p = float("nan")
    if all(len(g) >= 2 for g in groups) and len(groups) >= 2:
        F, p = (float(x) for x in f_oneway(*groups))
    return {"eta_squared_pct": round(100 * eta2, 1), "F": round(F, 2), "p": p}


def factorial_grid(path: Path | None = None) -> dict:
    rows = [r for r in _read_jsonl(path or EXPERIMENT_FILES["factorial_grid"]) if r.get("status") == "ok"]
    out = {"n_ok": len(rows)}
    for bench in ("gsm8k", "mmlu"):
        b5 = [r for r in rows if r["benchmark"] == bench and r["n_shot"] == 5]
        fmt = defaultdict(list)
        for r in b5:
            fmt[r["prompt_format"]].append(float(r["score"]))
        out[f"{bench}_format_5shot"] = _eta_and_f([fmt[k] for k in sorted(fmt)])
        # n_shot factor (pooled)
        ns = defaultdict(list)
        for r in rows:
            if r["benchmark"] == bench:
                ns[r["n_shot"]].append(float(r["score"]))
        out[f"{bench}_nshot"] = _eta_and_f([ns[k] for k in sorted(ns)])
        out[f"{bench}_nshot_means"] = {str(k): round(sum(v) / len(v), 2) for k, v in sorted(ns.items())}
        out[f"{bench}_format_5shot_means"] = {k: round(sum(v) / len(v), 2) for k, v in sorted(fmt.items())}
    if not rows:
        return out
    g5 = [r for r in rows if r["benchmark"] == "gsm8k" and r["n_shot"] == 5]
    temp = defaultdict(list)
    for r in g5:
        temp[r["temperature"]].append(float(r["score"]))
    out["gsm8k_temperature_5shot"] = _eta_and_f([temp[k] for k in sorted(temp)])
    plain = defaultdict(list)
    for r in rows:
        if r["benchmark"] == "gsm8k" and r["prompt_format"] == "plain":
            plain[r["n_shot"]].append(float(r["score"]))
    out["gsm8k_nshot_plain"] = _eta_and_f([plain[k] for k in sorted(plain)])
    # Exp1: the Qwen2.5-14B-Instruct, GSM8K, 5-shot cells (Table 22)
    exp1 = defaultdict(list)
    for r in g5:
        if r["model_id"].endswith("Qwen2.5-14B-Instruct"):
            exp1[(r["temperature"], r["prompt_format"])].append(float(r["score"]))
    out["exp1_qwen14b_gsm8k_5shot"] = {f"temp{t}|{f}": round(sum(v) / len(v), 2)
                                       for (t, f), v in sorted(exp1.items())}
    return out


def scoring_mode_e2(path: Path | None = None) -> dict:
    rows = _read_jsonl(path or EXPERIMENT_FILES["scoring_mode_e2"])
    by = defaultdict(dict)
    for r in rows:
        mode = r.get("scoring_mode") or r.get("mode") or r.get("method")
        by[r.get("model_id") or r.get("model")][mode] = r.get("score")
    gaps = [abs(round(v["log_likelihood"], 2) - round(v["generation"], 2)) for v in by.values()
            if v.get("log_likelihood") is not None and v.get("generation") is not None]
    return {"raw_rows": len(rows), "models": {k: v for k, v in by.items()},
            "max_gap_pp": round(max(gaps), 2) if gaps else None}


def harness_version_e3(path: Path | None = None) -> dict:
    rows = _read_jsonl(path or EXPERIMENT_FILES["harness_version_e3"])
    cells = {}
    for r in rows:
        cells[f"{r['model_id'].split('/')[-1]}|{r['lm_eval_version']}|seed{r['seed']}"] = r["score"]
    score = {(r["model_id"], r["lm_eval_version"], r["seed"]): r["score"] for r in rows}
    cross = [abs(v - score[(m, "0.4.11", s)]) for (m, ver, s), v in score.items()
             if ver == "0.4.3" and (m, "0.4.11", s) in score]
    seeds = [abs(v - score[(m, ver, 123)]) for (m, ver, s), v in score.items()
             if s == 42 and (m, ver, 123) in score]
    return {"n_cells": len(rows), "cells": cells,
            "max_cross_version_diff_pp": round(max(cross), 2) if cross else None,
            "max_seed_spread_pp": round(max(seeds), 2) if seeds else None}


def judge_sensitivity(path: Path | None = None) -> dict:
    rows = [r for r in _read_jsonl(path or EXPERIMENT_FILES["judge_sensitivity"]) if r.get("rating") is not None]
    means = defaultdict(list)
    for r in rows:
        means[(r["contestant"], r["judge"])].append(r["rating"])
    mat = {f"{c}|{j}": round(sum(v) / len(v), 2) for (c, j), v in means.items()}
    spreads = {}
    contestants = {c for (c, _j) in means}
    judges = sorted({j for (_c, j) in means})
    for c in contestants:
        vals = [sum(means[(c, j)]) / len(means[(c, j)]) for j in judges if (c, j) in means]
        if len(vals) >= 2:
            spreads[c] = round(max(vals) - min(vals), 2)
    return {"matrix_means": mat,
            "mean_spread": round(sum(spreads.values()) / len(spreads), 2) if spreads else None,
            "max_spread": round(max(spreads.values()), 2) if spreads else None}


def bbh_protocol(path: Path | None = None) -> dict:
    """Section 5.1 / 5.3: the leaderboard's Gemma-2-9B BBH record and our re-run of it.

    The re-run was made on a GPU runtime; its score is recorded next to the
    leaderboard's own values in the provenance file.
    """
    path = path or EXPERIMENT_FILES["bbh_protocol"]
    if not path.exists():
        MISSING_RESULTS.append(ds.shown(path))
        return {}
    rec = json.loads(path.read_text(encoding="utf-8"))
    raw, rerun = rec["bbh_raw_acc_norm_pct"], rec["rerun_leaderboard_bbh_acc_norm_pct"]
    return {"olv2_display": round(rec["bbh_display_normalized"], 2), "olv2_raw": round(raw, 2),
            "rerun_raw": round(rerun, 2), "rerun_minus_olv2_pp": round(rerun - raw, 2),
            "other_models_raw": rec.get("other_models_raw_acc_norm_pct", {})}


# --------------------------------------------------------------------------- #
# The report: one function per section, from the numbers of that section to its lines.
# --------------------------------------------------------------------------- #
def report_dataset(d: dict) -> list[str]:
    return [(f"Total records:   {d['total_records']:,}   models: {d['total_models']:,}   "
             f"benchmarks: {d['total_benchmarks']:,}"),
            (f"Leaderboard subtotal: {d['leaderboard_subtotal']['records']:,} | "
             f"ArXiv: {d['arxiv']['records']:,}")]


def report_coverage(cov: dict) -> list[str]:
    order = COVERAGE_REPORT

    def values(c):
        return "/".join(str(c[k]) for k in order)

    lines = [f"Coverage full   (shots/harness/CoT/prompt/temp): {values(cov['full_dataset'])}",
             f"Coverage subset (shots/harness/CoT/prompt/temp): {values(cov['leaderboard_subset'])}",
             (f"Coverage 9-source, without OLv2 ({cov['nine_source_n']:,} records): "
              f"{values(cov['nine_source_excl_olv2'])}"),
             "Coverage per leaderboard source (Table 7):"]
    return lines + [f"  {src:26}{c['n']:>7,}  {values(c)}" for src, c in cov["per_source"].items()]


def report_collisions(co: dict) -> list[str]:
    lines = [(f"Collisions: {co['pairs']:,} model-benchmark pairs, {co['collisions']} in two or more sources "
              f"({100 * co['collisions'] / co['pairs']:.2f}%); differ by >1 pp: {co['differ_gt_1pp']}, "
              f">5 pp: {co['differ_gt_5pp']}; harness missing in "
              f"{co['harness_missing']}/{co['differ_gt_1pp']} = "
              f"{100 * co['harness_missing'] / max(co['differ_gt_1pp'], 1):.0f}% of the disagreements")]
    for bench, label in OLV2_GAP_BENCHMARKS.items():
        g = co[f"olv2_{bench}"]
        lines.append(f"  OLv2 lower than the model paper on {label}: {g['olv2_lower']}/{g['pairs']}, "
                     f"median gap {g['median_gap_pp']} pp")
    return lines


def report_score_presence(ap41: dict) -> list[str]:
    return [f"ArXiv records with a score: {ap41['non_null_score']:,}/{ap41['arxiv_records']:,} = {ap41['pct']}%"]


def report_score_audit(sa: dict) -> list[str]:
    lines = [(f"Score audit: precision {sa['correct']}/{sa['entries']} = {sa['agreement_pct']}% "
              f"({sa['non_matches']} non-matches) | "
              f"recall {sa['entries']}/{sa['entries'] + sa['missed']} = {sa['recall_pct']}%")]
    return lines + [(f"  {title[:34]:34}{p['entries']:>5} entries  precision {p['precision_pct']:>5}%  "
                     f"recall {p['recall_pct']:>5}%") for title, p in sa["per_paper"].items()]


def report_harness_audit(ha: dict) -> list[str]:
    hw = ha["with_harness"]
    return [(f"Harness audit, with-harness pool: {hw['rows']} rows, {hw['attributable']} attributable, "
             f"named correctly {hw['named_correctly']} = {hw['named_correctly_pct']}%, missed {hw['missed']}, "
             f"named wrongly {hw['named_wrongly']}; abstained correctly on "
             f"{hw['abstained_correctly']}/{hw['not_attributable']} non-attributable rows"),
            (f"Harness audit, without-harness pool: abstained on "
             f"{ha['without_harness']['correct']}/{ha['without_harness']['rows']}")]


def report_metadata_audit(ma: dict) -> list[str]:
    lines = [(f"Metadata audit: {ma['values']:,} values, {ma['stated']:,} stated, agreement "
              f"{ma['agree']:,}/{ma['stated']:,} = {ma['agreement_pct']}%, defaults {ma['defaults_pct']}%")]
    for name, m in list(ma["per_field"].items()) + list(ma["per_paper"].items()):
        name = name.encode("ascii", "ignore").decode().replace("emojidizzy", "").lstrip("\\")
        lines.append(f"  {name[:34]:34}{m['values']:>6,} values  {m['agree']:>5,}/{m['stated']:<5,} = "
                     f"{m['agreement_pct']:>5}%  defaults {m['defaults_pct']}%")
    return lines


def report_factorial_grid(fg: dict) -> list[str]:
    if not fg.get("n_ok"):
        return []
    f, t, n = fg["gsm8k_format_5shot"], fg["gsm8k_temperature_5shot"], fg["gsm8k_nshot"]
    return [(f"Factorial grid: {fg['n_ok']} runs. GSM8K 5-shot, prompt format: eta^2 {f['eta_squared_pct']}%, "
             f"F={f['F']}, p={f['p']:.1e}; temperature: eta^2 {t['eta_squared_pct']}%, F={t['F']}, p={t['p']:.2f}"),
            (f"  GSM8K shot count: eta^2 {n['eta_squared_pct']}% "
             f"(plain only {fg['gsm8k_nshot_plain']['eta_squared_pct']}%), means {fg['gsm8k_nshot_means']}; "
             f"MMLU: eta^2 {fg['mmlu_nshot']['eta_squared_pct']}%, means {fg['mmlu_nshot_means']}"),
            f"  Exp1, Qwen2.5-14B-Instruct on GSM8K 5-shot: {fg['exp1_qwen14b_gsm8k_5shot']}"]


def report_scoring_mode(e2: dict) -> list[str]:
    if e2.get("max_gap_pp") is None:
        return []
    return [f"Exp2, MMLU log-likelihood against generation: largest gap {e2['max_gap_pp']} pp"]


def report_harness_version(e3: dict) -> list[str]:
    if not e3.get("n_cells"):
        return []
    return [(f"Exp3, lm-eval 0.4.3 against 0.4.11: largest difference at the same seed "
             f"{e3['max_cross_version_diff_pp']} pp, largest seed spread {e3['max_seed_spread_pp']} pp")]


def report_judge_sensitivity(js: dict) -> list[str]:
    if js.get("mean_spread") is None:
        return []
    return [f"Judge model, 4 judges: mean spread {js['mean_spread']}, largest {js['max_spread']} (of 10)"]


def report_bbh_protocol(bb: dict) -> list[str]:
    if not bb:
        return []
    return [(f"BBH, Gemma-2-9B: leaderboard {bb['olv2_display']} (raw {bb['olv2_raw']}), "
             f"re-run {bb['rerun_raw']}, {bb['rerun_minus_olv2_pp']:+} pp")]


# --------------------------------------------------------------------------- #
# The sections, in the order of the report and of paper_numbers.json.
# --------------------------------------------------------------------------- #
class Section(NamedTuple):
    key: str                                  # key in paper_numbers.json
    title: str                                # what it computes, for --list
    compute: Callable[..., dict]              # the numbers of the section
    report: Callable[[dict], list[str]]       # its lines of the report
    uses_rows: bool = False                   # compute(rows) instead of compute()


SECTIONS = [
    Section("dataset", "records, models and benchmarks per source (3.1)", dataset_numbers, report_dataset, True),
    Section("coverage", "how often each setting is recorded (3.3, Figure 2, Table 7)",
            coverage_numbers, report_coverage, True),
    Section("collisions_3_3", "pairs reported by several sources; OLv2 against the others (3.3, App. F)",
            collision_numbers, report_collisions),
    Section("arxiv_score_presence_4_1", "arXiv records that carry a score (3.2)",
            arxiv_score_presence, report_score_presence),
    Section("score_audit_4_1", "hand-checked scores: precision and recall (3.2, Table 4)",
            score_audit, report_score_audit),
    Section("harness_audit_4_2", "hand-checked harness names (3.2)", harness_audit, report_harness_audit),
    Section("metadata_audit", "hand-checked metadata values (3.2, Table 5)", metadata_audit, report_metadata_audit),
    Section("factorial_grid", "the 312-run grid: effect of format, shots, temperature (4, App. M.1)",
            factorial_grid, report_factorial_grid),
    Section("scoring_mode_e2", "Exp2: log-likelihood against generation on MMLU (App. M.4)",
            scoring_mode_e2, report_scoring_mode),
    Section("harness_version_e3", "Exp3: two lm-eval versions (App. M.5)",
            harness_version_e3, report_harness_version),
    Section("judge_sensitivity", "the same answers under four judge models (App. M.6)",
            judge_sensitivity, report_judge_sensitivity),
    Section("bbh_protocol", "the leaderboard's Gemma-2-9B BBH record and its re-run (5.1, 5.3)",
            bbh_protocol, report_bbh_protocol),
]


def compute(sections=None, rows: list[dict] | None = None) -> dict:
    """The numbers of the given sections (all of them by default), keyed as in paper_numbers.json."""
    sections = SECTIONS if sections is None else sections
    if rows is None and any(s.uses_rows for s in sections):
        rows = load_aggregate()
    MISSING_RESULTS.clear()
    numbers = {s.key: s.compute(rows) if s.uses_rows else s.compute() for s in sections}
    numbers["missing_result_files"] = sorted(set(MISSING_RESULTS))
    return numbers


def report(numbers: dict, sections=None) -> list[str]:
    """The lines of the report for the sections present in `numbers`."""
    sections = SECTIONS if sections is None else sections
    return [line for s in sections if s.key in numbers for line in s.report(numbers[s.key])]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-rebuild", action="store_true",
                    help="skip rebuilding data/aggregated/all_results.csv (use the existing file)")
    ap.add_argument("--only", metavar="KEYS", help="comma-separated sections to compute (see --list); "
                    "the result is printed, and written only if --out is given")
    ap.add_argument("--list", action="store_true", help="list the sections and exit")
    ap.add_argument("--out", type=Path, help="where to write the numbers (default: analysis_output/paper_numbers.json)")
    ds.add_data_option(ap)
    args = ap.parse_args(argv)
    ds.apply_data_option(args)

    if args.list:
        for s in SECTIONS:
            print(f"{s.key:26}{s.title}")
        return 0
    sections = SECTIONS
    if args.only:
        wanted = [k.strip() for k in args.only.split(",") if k.strip()]
        unknown = sorted(set(wanted) - {s.key for s in SECTIONS})
        if unknown:
            ap.error(f"unknown section: {', '.join(unknown)} (see --list)")
        sections = [s for s in SECTIONS if s.key in wanted]

    # The aggregate can only be rebuilt from the pipeline's per-record tree. With the
    # published dataset (scripts/fetch_data.py) the shipped all_results.csv is used as is.
    rebuild = not args.no_rebuild and (ds.DATA / "open_llm_leaderboard_v2").is_dir()
    print("[reproduce_paper] loading canonical aggregate "
          f"({f'rebuilding from {ds.shown(ds.DATA)}/' if rebuild else f'using {ds.shown(ds.AGGREGATE_CSV)}'})...")
    numbers = compute(sections, load_aggregate(rebuild=rebuild))

    out_path = args.out or (None if args.only else ANALYSIS_OUT / "paper_numbers.json")
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(numbers, indent=2, default=str), encoding="utf-8")

    print("\n================ PAPER NUMBERS (canonical) ================")
    print("\n".join(report(numbers, sections)))
    if not args.only:
        print("The other experiment numbers come from the analysis scripts listed in experiments/README.md.")
    if MISSING_RESULTS:
        print("\nExperiment numbers left empty, because these result files are not on disk:")
        for path in sorted(set(MISSING_RESULTS)):
            print(f"  {path}")
        print("See experiments/README.md for which run writes each file.")
    if out_path:
        print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
