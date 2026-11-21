#!/usr/bin/env python3
"""Collect the four good RESULT_JSON records (0.4.3 from the orchestrate combined
file, 0.4.11 from the two native-stack canary logs) into final_runs.jsonl.

    python assemble_final_runs.py                          # results/ next to this script
    python assemble_final_runs.py --results-dir DIR --logs 'c411*.log'

One record is kept per (lm-eval version, model): the first that finished with a score.
"""
import argparse
import glob
import json
import os

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
RESULT_PREFIX = "RESULT_JSON:"


def records_of(path):
    """The run records of a file: a .jsonl file of records, or a log with RESULT_JSON: lines."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if path.endswith(".jsonl") and line:
                yield json.loads(line)
            elif line.startswith(RESULT_PREFIX):
                yield json.loads(line[len(RESULT_PREFIX):])


def first_good_runs(records):
    """The first record with a score for each (lm-eval version, model)."""
    keep, seen = [], set()
    for d in records:
        key = (d["lm_eval_version"], d["model_id"])
        if d.get("status") == "ok" and d.get("score") is not None and key not in seen:
            seen.add(key)
            keep.append(d)
    return keep


def main(argv=None):
    ap = argparse.ArgumentParser(description="Collect the finished version runs into final_runs.jsonl.")
    ap.add_argument("--results-dir", default=RESULTS_DIR, help="folder with the run files (default: results/ next to this script)")
    ap.add_argument("--combined", default="all_version_runs.jsonl", help="file with the 0.4.3 records")
    ap.add_argument("--logs", default="c411*.log", help="pattern of the logs with the 0.4.11 records")
    ap.add_argument("--out", default="final_runs.jsonl")
    args = ap.parse_args(argv)

    sources = [os.path.join(args.results_dir, args.combined)] + glob.glob(os.path.join(args.results_dir, args.logs))
    keep = first_good_runs(d for path in sources for d in records_of(path))
    out = os.path.join(args.results_dir, args.out)
    with open(out, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(d) + "\n" for d in keep)
    print(f"wrote {os.path.relpath(out)} with {len(keep)} rows")
    for d in keep:
        print(f"  {d['lm_eval_version']:>7} | {d['model_id']:<30} | {d['score']} | {d['metric']}")


if __name__ == "__main__":
    main()
