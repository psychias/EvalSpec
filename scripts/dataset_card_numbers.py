#!/usr/bin/env python3
"""Recompute every number on the dataset card from the files of the dataset.

    python scripts/dataset_card_numbers.py            # print the numbers
    python scripts/dataset_card_numbers.py --check    # and compare them with the card

The card is the README of https://huggingface.co/datasets/Hermeneia/EvalSpec_Dataset.
`scripts/fetch_data.py` saves a copy of it as data/DATASET_CARD.md, which is what
--check reads. With --check the script exits with status 1 when a number it computes
is not on the card.

The corpus totals, the coverage table and the audits come from the functions of
reproduce_paper.py, so the card and the paper are computed the same way. This script
adds what only the card states: file sizes, the per-paper harness table, the kinds of
row in each audit file, and the collection dates.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import sys
from collections import Counter, defaultdict

import dataset_access as ds
import reproduce_paper as rp

CARD = ds.DATA / "DATASET_CARD.md"

# source key in all_results.csv -> file in data/ on the hub
SOURCE_FILES = {
    "open_llm_leaderboard_v2": "open_llm_leaderboard.jsonl", "arxiv_html_llm": "arxiv_extraction.jsonl",
    "papers_with_code": "papers_with_code.jsonl", "alpacaeval2": "alpacaeval2.jsonl", "bfcl": "bfcl.jsonl",
    "bigcodebench": "bigcodebench.jsonl", "chatbot_arena": "chatbot_arena.jsonl", "evalplus": "evalplus.jsonl",
    "hf_model_card": "hf_model_card.jsonl", "wildbench": "wildbench.jsonl", "swe_bench": "swe_bench.jsonl",
    "mt_bench": "mt_bench.jsonl",
}
# short names of the audited papers, as the card writes them
SHORT = {
    "Kimi-Audio": "Kimi-Audio", "Mistral 7B": "Mistral 7B", "Llama-Embed-Nemotron-8B": "Llama-Embed-Nemotron-8B",
    "Sailor": "Sailor", "Phi-4-reasoning-vision": "Phi-4-reasoning-vision", "Instella": "Instella",
    "SOLAR 10.7B": "SOLAR 10.7B", "TinyLlama": "TinyLlama", "Phi-3 ": "Phi-3", "Gemma 2": "Gemma 2",
    "BLOOM": "BLOOM", "Pre-training via Structured Pruning": "Sheared LLaMA", "Aya 23": "Aya 23", "Llemma": "Llemma",
    "Nemotron-4 15B": "Nemotron-4 15B", "A Comprehensive Overview": "Survey", "Mamba": "Mamba", "Jamba": "Jamba",
    "Code Llama": "Code Llama", "Reka": "Reka",
}


def short(title: str) -> str:
    return next((name for start, name in SHORT.items() if title.startswith(start)), title)


def pct(part: int, whole: int) -> str:
    """A share as the card writes it: one decimal, and 100% without one."""
    value = round(100 * part / whole, 1) if whole else 0.0
    return "100%" if value == 100 else f"{value}%"


def annotation_rows(name: str) -> list[dict]:
    path = ds.annotation_file(name)
    if not path.exists():
        sys.exit(ds.FETCH_HINT)
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def correct(row: dict) -> bool:
    return str(row.get("correct", "")).strip().lower() == "true"


# --------------------------------------------------------------------------- #
# Sections. Each returns (lines to print, numbers that must appear on the card).
# --------------------------------------------------------------------------- #
def files_and_size(rows: list[dict]) -> tuple[list[str], list[str]]:
    numbers = rp.dataset_numbers(rows)
    records = {f.name: len(ds.read_jsonl(f)) for f in sorted(ds.RECORDS.glob("*.jsonl"))}
    lb, arxiv, pwc = numbers["leaderboard_subtotal"], numbers["arxiv"], numbers["per_source"]["papers_with_code"]
    lines = [f"all_results.csv: {len(rows):,} rows, {len(rows[0])} columns",
             f"data/: {sum(records.values()):,} records in {len(records)} files",
             f"all 12 sources: {numbers['total_records']:,} results, {numbers['total_models']:,} models, {numbers['total_benchmarks']:,} benchmarks",
             f"10 leaderboard sources: {lb['records']:,} results, {lb['models']:,} models, {lb['benchmarks']:,} benchmarks",
             f"arXiv papers: {arxiv['records']:,} results, {arxiv['models']:,} models, {arxiv['benchmarks']:,} benchmarks",
             f"Papers With Code: {pwc['records']:,} results, {pwc['models']:,} models, {pwc['benchmarks']:,} benchmarks"]
    expect = [f"{len(rows):,}", f"{sum(records.values()):,}", f"{numbers['total_models']:,}", f"{numbers['total_benchmarks']:,}",
              f"{lb['records']:,}", f"{lb['models']:,}", f"{arxiv['records']:,}", f"{arxiv['models']:,}", f"{arxiv['benchmarks']:,}"]
    lines.append("per source (results, models, benchmarks):")
    for source, stats in sorted(numbers["per_source"].items(), key=lambda kv: -kv[1]["records"]):
        lines.append(f"  {SOURCE_FILES.get(source, source):28s} {stats['records']:>7,} {stats['models']:>6,} {stats['benchmarks']:>6,}")
        expect.append(f"| {stats['records']:,} | {stats['models']:,} | {stats['benchmarks']:,} |")
    return lines, expect


def columns(rows: list[dict]) -> tuple[list[str], list[str]]:
    empty = [c for c in rows[0] if not any((r[c] or "").strip() for r in rows)]
    no_score = sum(1 for r in rows if not _is_number(r.get("score")))
    relationships = Counter(r["evaluator_relationship"] for r in rows)
    lines = [f"columns that are empty in every row ({len(empty)}): {', '.join(empty)}",
             f"rows without a numeric score: {no_score:,} (all from {', '.join(sorted({r['source'] for r in rows if not _is_number(r.get('score'))}))})",
             f"evaluator_relationship values: {dict(relationships)}"]
    return lines, [f"{no_score:,}"] + [f"`{c}`" for c in empty] + [f"`{k}`" for k in relationships]


def _is_number(value) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def coverage(rows: list[dict]) -> tuple[list[str], list[str]]:
    cov = rp.coverage_numbers(rows)
    lines, expect = ["field: all sources / 10 leaderboard sources"], []
    for field in ("shots", "harness", "chain_of_thought", "prompt_template", "temperature"):
        full, subset = cov["full_dataset"][field], cov["leaderboard_subset"][field]
        lines.append(f"  {field:18s} {full}% / {subset}%")
        expect.append(f"| `{field}` | {full}% | {subset}% |")
    return lines, expect


def score_audit() -> tuple[list[str], list[str]]:
    audit = rp.score_audit()
    rows = annotation_rows("annotation_score_verification.csv")
    wrong = Counter(short(r["paper_title"]) for r in rows if r["verdict_type"] == "score" and not correct(r))
    lines = [f"{len(rows):,} rows from {len({r['arxiv_id'] for r in rows})} papers",
             f"score rows: {audit['entries']:,}, correct {audit['correct']:,} = {audit['agreement_pct']}% precision",
             f"recall rows: {audit['missed']:,}; recall {audit['entries']:,} of {audit['entries'] + audit['missed']:,} = {audit['recall_pct']}%",
             f"wrong rows: {audit['non_matches']} ({', '.join(f'{p} {n}' for p, n in wrong.most_common())})",
             "per paper (extracted, correct, missed, precision, recall):"]
    expect = [f"{len(rows):,}", f"{audit['entries']:,}", f"{audit['correct']:,}", f"{audit['agreement_pct']}%", f"{audit['recall_pct']}%",
              f"{audit['missed']}", "The 50 wrong rows" if audit["non_matches"] == 50 else f"The {audit['non_matches']} wrong rows"]
    expect += [f"({paper}, {n} rows)" if paper == "Kimi-Audio" else f"({paper}, {n})" for paper, n in wrong.items() if paper != "Gemma 2"]
    for title, s in audit["per_paper"].items():
        row = f"| {short(title)} | {s['entries']} | {s['correct']} | {s['missed']} | {pct(s['correct'], s['entries'])} | {pct(s['entries'], s['entries'] + s['missed'])} |"
        lines.append("  " + row)
        expect.append(row)
    return lines, expect


def harness_with() -> tuple[list[str], list[str]]:
    audit = rp.harness_audit()["with_harness"]
    rows = annotation_rows("annotation_eval_harness_WITH.csv")
    kinds = Counter(r["verdict_type"] for r in rows)
    per = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["verdict_type"] == "harness":
            per[short(r["paper_title"])][0] += 1
            per[short(r["paper_title"])][1] += correct(r)
    lines = [f"{len(rows):,} rows: {kinds['harness']} harness rows, {kinds['recall']} recall rows",
             (f"attributable {audit['attributable']}, named correctly {audit['named_correctly']} = {audit['named_correctly_pct']}%, "
             f"missed {audit['missed']}, named wrongly {audit['named_wrongly']}"),
             f"not attributable {audit['not_attributable']}, abstained correctly {audit['abstained_correctly']}",
             f"correct overall {audit['correct']} of {audit['rows']} = {audit['pct']}%", "per paper (rows, correct):"]
    expect = [f"{len(rows):,}", f"{kinds['harness']}", f"{kinds['recall']}", f"{audit['attributable']}", f"{audit['named_correctly']}",
              f"{audit['named_correctly_pct']}%", f"{audit['missed']}", f"{audit['not_attributable']}", f"{audit['correct']} of {audit['rows']}", f"{audit['pct']}%"]
    for paper, (n, ok) in sorted(per.items(), key=lambda kv: (-kv[1][1] / kv[1][0], -kv[1][0])):
        row = f"| {paper} | {n} | {ok} | {pct(ok, n)} |"
        lines.append("  " + row)
        expect.append(row)
    return lines, expect


def harness_without() -> tuple[list[str], list[str]]:
    rows = annotation_rows("annotation_eval_harness_WITHOUT.csv")
    kinds = Counter(r["verdict_type"] for r in rows)
    abstained = sum(1 for r in rows if r["verdict_type"] == "abstention" and correct(r))
    errors = Counter(short(r["paper_title"]) for r in rows if r["verdict_type"] == "score")
    lines = [f"{len(rows):,} rows from {len({r['arxiv_id'] for r in rows})} papers",
             f"abstention rows {kinds['abstention']}, correct {abstained}",
             f"score-error rows {kinds['score']} ({', '.join(f'{p} {n}' for p, n in errors.most_common())})",
             f"recall rows {kinds['recall']}"]
    expect = [f"{len(rows):,}", f"{kinds['abstention']}", f"{kinds['score']} rows", f"{kinds['recall']} rows",
              f"{errors['Mamba']} are in Mamba", f"{errors['Jamba']} are in Jamba"]
    return lines, expect


def metadata_audit() -> tuple[list[str], list[str]]:
    audit = rp.metadata_audit()
    defaults = audit["values"] - audit["stated"]
    lines = [(f"{audit['values']:,} rows; stated {audit['stated']:,}, agree {audit['agree']:,} = {audit['agreement_pct']}%; "
             f"defaults {defaults:,} = {audit['defaults_pct']}%"), "per field (values, stated, agree, agreement, defaults):"]
    expect = [f"{audit['values']:,}", f"{audit['stated']:,}", f"{audit['agree']:,}", f"{audit['agreement_pct']}%", f"{defaults:,}", f"{audit['defaults_pct']}%"]
    for field in ("n_shot", "decoding_strategy", "prompt_template", "temperature"):
        s = audit["per_field"][field]
        row = f"| `{field}` | {s['values']:,} | {s['stated']:,} | {s['agree']:,} | {pct(s['agree'], s['stated'])} | {s['defaults_pct']}% |"
        lines.append("  " + row)
        expect.append(row)
    return lines, expect


def collection_dates(rows: list[dict]) -> tuple[list[str], list[str]]:
    def day(stamp: str) -> str:
        try:
            return datetime.datetime.fromtimestamp(float(stamp), tz=datetime.timezone.utc).date().isoformat()
        except ValueError:
            return stamp[:10]
    spans = defaultdict(set)
    for r in rows:
        spans[r["source"]].add(day(r["retrieved_timestamp"]))
    by_span = defaultdict(list)
    for source, days in spans.items():
        by_span[(min(days), max(days))].append(source)
    lines = [f"{first} to {last}: {', '.join(sorted(sources))}" for (first, last), sources in sorted(by_span.items())]
    return lines, ["25 March 2026", "16 May 2026", "between April and June 2026"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Recompute every number on the dataset card.")
    ap.add_argument("--check", action="store_true", help="compare the numbers with data/DATASET_CARD.md")
    args = ap.parse_args(argv)
    rows = rp.load_aggregate(rebuild=False)

    sections = [("Files and size", files_and_size(rows)), ("Columns of all_results.csv", columns(rows)),
                ("How often the settings are recorded", coverage(rows)),
                ("annotation_score_verification.csv", score_audit()), ("annotation_eval_harness_WITH.csv", harness_with()),
                ("annotation_eval_harness_WITHOUT.csv", harness_without()), ("annotation_metadata_fields.csv", metadata_audit()),
                ("Collection dates", collection_dates(rows))]
    for title, (lines, _) in sections:
        print(f"\n== {title}")
        print("\n".join(lines))
    if not args.check:
        return 0

    if not CARD.exists():
        sys.exit(f"{CARD.relative_to(ds.ROOT)} is missing. Run: python scripts/fetch_data.py")
    card = " ".join(CARD.read_text(encoding="utf-8").split())        # the card wraps its lines
    missing = [(title, value) for title, (_, expect) in sections for value in expect if " ".join(value.split()) not in card]
    checked = sum(len(expect) for _, (_, expect) in sections)
    print(f"\n== Check against {CARD.relative_to(ds.ROOT)}")
    for title, value in missing:
        print(f"  not on the card ({title}): {value}")
    print(f"{checked - len(missing)} of {checked} computed values are on the card")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
