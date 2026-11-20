#!/usr/bin/env python3
"""Download the published dataset into data/, where the reproduction scripts read it.

    python scripts/fetch_data.py                  # from the Hugging Face hub
    python scripts/fetch_data.py --from PATH      # from a local copy of the dataset

Writes:

    data/aggregated/all_results.csv     one row per result (46,559 rows)
    data/records/<source>.jsonl         the full records of each source, one per line
    data/annotations/*.csv              the hand-checked audit sets
    data/eval.schema.json               the record schema shipped with the dataset
    data/DATASET_CARD.md                the dataset card (the README of the dataset)

The dataset is public; no Hugging Face account is needed.
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPO = "Psychias/EvalSpec_Dataset"


def download(repo: str, revision: str) -> pathlib.Path:
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        sys.exit("huggingface_hub is not installed. Run: pip install huggingface_hub")
    try:
        return pathlib.Path(snapshot_download(repo_id=repo, repo_type="dataset", revision=revision))
    except Exception as e:  # noqa: BLE001  huggingface_hub raises its own error types
        sys.exit(f"could not download {repo}: {type(e).__name__}: {e}\n"
                 "Check the network connection, or pass --from <folder> to use a copy on disk.")


def lay_out(source: pathlib.Path) -> dict[str, int]:
    """Copy the files of the dataset to the places the scripts expect."""
    if not (source / "all_results.csv").exists():
        sys.exit(f"{source} does not look like the dataset: all_results.csv is missing")
    plan = [(source / "all_results.csv", DATA / "aggregated" / "all_results.csv")]
    plan += [(f, DATA / "records" / f.name) for f in sorted((source / "data").glob("*.jsonl"))]
    plan += [(f, DATA / "annotations" / f.name) for f in sorted((source / "annotations").glob("*.csv"))]
    if (source / "eval.schema.json").exists():
        plan.append((source / "eval.schema.json", DATA / "eval.schema.json"))
    if (source / "README.md").exists():                    # the dataset card, for dataset_card_numbers.py --check
        plan.append((source / "README.md", DATA / "DATASET_CARD.md"))
    for src, dst in plan:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    return {"records": len(list((DATA / "records").glob("*.jsonl"))),
            "annotations": len(list((DATA / "annotations").glob("*.csv")))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Download the published dataset into data/.")
    ap.add_argument("--from", dest="source", type=pathlib.Path, help="a local copy of the dataset, instead of downloading it")
    ap.add_argument("--repo", default=REPO, help=f"Hugging Face dataset (default: {REPO})")
    ap.add_argument("--revision", default="main")
    args = ap.parse_args(argv)
    source = args.source.resolve() if args.source else download(args.repo, args.revision)
    done = lay_out(source)
    with open(DATA / "aggregated" / "all_results.csv", encoding="utf-8", newline="") as fh:
        rows = sum(1 for _ in csv.reader(fh)) - 1
    print(f"data/aggregated/all_results.csv: {rows:,} rows\n"
          f"data/records/: {done['records']} source files\n"
          f"data/annotations/: {done['annotations']} audit files\n"
          "Next: python scripts/reproduce_paper.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
