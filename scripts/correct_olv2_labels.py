#!/usr/bin/env python3
"""Write a copy of the dataset with the corrected protocol labels of the Open LLM Leaderboard records.

    python scripts/correct_olv2_labels.py

The leaderboard publishes scores only. Shots, metric and chain-of-thought status of its
records are filled in by the pipeline from one table,
`OpenLLMLeaderboardV2Fetcher._BENCH_COLS`. That table used to mark BBH, GPQA, MuSR and
MMLU-Pro as chain-of-thought. The leaderboard documents all four as multiple choice
(scored by log-likelihood), so the label was wrong. This script applies the corrected
table to the records on disk, without fetching anything, and writes

    data/corrected/records/open_llm_leaderboard.jsonl
    data/corrected/aggregated/all_results.csv
    data/corrected/comparison.json      coverage and collision counts, before and after

The files under data/records and data/aggregated are not changed. Scores, model names and
benchmark names are the same in both copies.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import collision_prevalence as cp  # noqa: E402
import reproduce_paper as rp  # noqa: E402
from eee_eval.extraction.add_leaderboard_records import OpenLLMLeaderboardV2Fetcher  # noqa: E402

DATA = ROOT / "data"
OUT = DATA / "corrected"
RECORDS = "records/open_llm_leaderboard.jsonl"
CSV = "aggregated/all_results.csv"
SOURCE = "open_llm_leaderboard_v2"

# benchmark name in the records -> (shots, metric, note, chain of thought)
LABELS = {bench: (shots, metric, note, cot)
          for bench, shots, metric, note, cot in OpenLLMLeaderboardV2Fetcher._BENCH_COLS.values()}
# the aggregate renames the leaderboard's GPQA rows
CSV_NAME = {"GPQA-Diamond": "GPQA-Diamond (acc_norm)"}


def correct_records() -> Counter:
    changed = Counter()
    (OUT / RECORDS).parent.mkdir(parents=True, exist_ok=True)
    # newline="": the copy keeps the line endings of the file it is made from
    with open(DATA / RECORDS, encoding="utf-8", newline="") as src, \
            open(OUT / RECORDS, "w", encoding="utf-8", newline="") as dst:
        for line in src:
            end = line[len(line.rstrip("\r\n")):]
            rec = json.loads(line)
            for res in rec["evaluation_results"]:
                bench = res["evaluation_name"]
                if bench not in LABELS:
                    continue
                shots, metric, note, cot = LABELS[bench]
                before = json.dumps(res, sort_keys=True)
                res["metric_config"]["metric_name"] = metric
                config = res.setdefault("generation_config", {})
                args = config.setdefault("generation_args", {})
                args["shots"] = shots
                args.pop("chain_of_thought", None)
                if cot is not None:
                    args["chain_of_thought"] = cot
                details = config.setdefault("additional_details", {})
                details.pop("note", None)
                if note:
                    details["note"] = note
                changed[bench] += before != json.dumps(res, sort_keys=True)
            dst.write(json.dumps(rec, ensure_ascii=False) + end)
    return changed


def correct_csv() -> list[dict]:
    by_csv_name = {CSV_NAME.get(b, b): v for b, v in LABELS.items()}
    with open(DATA / CSV, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fields, rows = reader.fieldnames, list(reader)
    for r in rows:
        if r["source"] == SOURCE and r["benchmark"] in by_csv_name:
            shots, metric, _, cot = by_csv_name[r["benchmark"]]
            r["shots"], r["metric_name"] = str(shots), metric
            r["chain_of_thought"] = "" if cot is None else str(cot)
    (OUT / CSV).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT / CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return rows


def numbers(path: Path) -> dict:
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    cov = rp.coverage_numbers(rows)
    olv2 = [r for r in rows if r["source"] == SOURCE]
    labels = Counter((r["benchmark"], r["metric_name"], r["shots"], r["chain_of_thought"] or "not recorded")
                     for r in olv2)
    return {
        "coverage_full_dataset": cov["full_dataset"],
        "coverage_leaderboard_subset": cov["leaderboard_subset"],
        "coverage_open_llm_leaderboard_v2": cov["per_source"][SOURCE],
        "coverage_nine_sources_without_olv2": cov["nine_source_excl_olv2"],
        "collisions": cp.prevalence(cp.load_cells(path)[1]),
        "olv2_labels": [{"benchmark": b, "metric_name": m, "shots": s, "chain_of_thought": c, "records": n}
                        for (b, m, s, c), n in sorted(labels.items())],
    }


def main() -> int:
    if not (DATA / RECORDS).exists() or not (DATA / CSV).exists():
        sys.exit("The dataset is not on disk. Run: python scripts/fetch_data.py")
    changed = correct_records()
    correct_csv()
    out = {"results_changed_per_benchmark": dict(sorted(changed.items())),
           "before": numbers(DATA / CSV), "after": numbers(OUT / CSV)}
    (OUT / "comparison.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")

    print("results changed:", ", ".join(f"{b} {n:,}" for b, n in sorted(changed.items())))
    for field, title in (("chain_of_thought", "chain-of-thought status recorded"),
                         ("cot_true", "recorded as chain-of-thought")):
        print(f"\n{title:42}{'before':>8}{'after':>8}")
        for key, name in (("coverage_full_dataset", "all sources"),
                          ("coverage_leaderboard_subset", "10 leaderboard sources"),
                          ("coverage_open_llm_leaderboard_v2", "Open LLM Leaderboard v2")):
            print(f"{name:42}{out['before'][key][field]:>7}%{out['after'][key][field]:>7}%")
    same = all(out["before"][k] == out["after"][k] for k in out["before"]
               if k not in ("olv2_labels",) and not k.startswith("coverage"))
    others = all(out["before"][k][f] == out["after"][k][f]
                 for k in out["before"] if k.startswith("coverage")
                 for f in ("shots", "harness", "prompt_template", "temperature"))
    print(f"\ncollision counts unchanged: {same}; other coverage fields unchanged: {others}")
    print(f"written to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
