#!/usr/bin/env python3
"""Check the Open LLM Leaderboard scores that the paper quotes from the leaderboard's own table.

    python scripts/olv2_raw_scores.py            # check the quoted scores against the saved rows
    python scripts/olv2_raw_scores.py --fetch    # download the table again and compare the saved rows with it

The dataset holds the score the leaderboard displays (Gemma-7B on BBH: 21.12). The
leaderboard's table also has the score before rescaling (43.62), which the paper quotes
in Section 5.1, Section 5.3, Appendix E and Table 8, and which is not in the dataset.

The table is the Hugging Face dataset `open-llm-leaderboard/contents`. It has not changed
since 2025-03-20, and the revision read here is fixed, so the numbers cannot move. The
complete rows of the four models the paper quotes are saved in
`experiments/bbh_protocol/olv2_leaderboard_rows.json`; --fetch downloads the table at
that revision, checks its checksum and compares the saved rows with it.

Where the dataset is on disk (scripts/fetch_data.py), the displayed scores are also
compared with the records of the dataset.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROWS = ROOT / "experiments" / "bbh_protocol" / "olv2_leaderboard_rows.json"
CSV = ROOT / "data" / "aggregated" / "all_results.csv"

REPO = "open-llm-leaderboard/contents"
REVISION = "9c09a7cae43334062a82cb164f2ef255013dafa2"
FILE = "data/train-00000-of-00001.parquet"
SHA256 = "f13a7061e63133bc8745d89f8c7a56148584940ede22d3b27e21cad1e078dca5"

MODELS = ["google/gemma-7b", "google/gemma-2-2b", "TIGER-Lab/MAmmoTH2-7B-Plus", "google/gemma-2-9b"]

# (row of the table, column, score before rescaling in %, displayed score), as the paper quotes them
QUOTED = [
    ("google_gemma-7b_bfloat16", "BBH", 43.62, 21.12),
    ("google_gemma-2-2b_bfloat16", "BBH", 36.56, 11.76),
    ("TIGER-Lab_MAmmoTH2-7B-Plus_bfloat16", "BBH", 42.35, 18.93),
    ("google_gemma-2-9b_bfloat16", "BBH", 53.77, 34.10),
    ("google_gemma-2-9b_bfloat16", "GPQA", 32.89, 10.51),
    ("google_gemma-2-9b_bfloat16", "MMLU-PRO", 41.03, 34.48),
]
# column of the table -> benchmark name in the dataset
BENCHMARK = {"BBH": "BBH", "GPQA": "GPQA-Diamond (acc_norm)", "MMLU-PRO": "MMLU-Pro"}


def download() -> list[dict]:
    """The rows of the four models in the table at the fixed revision."""
    try:
        import pandas as pd
        from huggingface_hub import hf_hub_download
    except ImportError as e:
        sys.exit(f'--fetch needs pandas and huggingface_hub ({e}). Run: pip install -e ".[leaderboard]"')
    path = Path(hf_hub_download(REPO, FILE, repo_type="dataset", revision=REVISION))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != SHA256:
        sys.exit(f"{REPO}@{REVISION[:7]}: checksum {digest} is not the expected {SHA256}")
    try:
        table = pd.read_parquet(path)
    except ImportError:                      # pandas has no Parquet reader
        sys.exit('--fetch needs pyarrow to read the table. Run: pip install -e ".[leaderboard]"')
    rows = table[table["fullname"].isin(MODELS)].sort_values("eval_name")
    return json.loads(rows.to_json(orient="records"))


def saved() -> list[dict]:
    if not ROWS.exists():
        sys.exit(f"{ROWS.relative_to(ROOT)} is missing; write it with --fetch")
    return json.loads(ROWS.read_text(encoding="utf-8"))["rows"]


def write(rows: list[dict]) -> None:
    doc = {"source": f"https://huggingface.co/datasets/{REPO}", "revision": REVISION,
           "file": FILE, "sha256": SHA256, "models": MODELS, "rows": rows}
    ROWS.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def dataset_scores() -> dict[tuple[str, str], float]:
    """(model id in lower case, benchmark) -> displayed score in the dataset, if it is on disk.

    A few leaderboard records of the dataset have no organisation ("unknown/MAmmoTH2-7B-Plus").
    They are also filed under the model name alone, when only one model has that name.
    """
    if not CSV.exists():
        return {}
    out, by_name = {}, {}
    with open(CSV, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["source"] == "open_llm_leaderboard_v2":
                model = r["model_id"].lower()
                out[(model, r["benchmark"])] = float(r["score"])
                by_name.setdefault((model.split("/")[-1], r["benchmark"]), {})[model] = float(r["score"])
    for key, models in by_name.items():
        if len(models) == 1:
            out.setdefault(key, next(iter(models.values())))
    return out


def check(rows: list[dict]) -> int:
    by_name = {r["eval_name"]: r for r in rows}
    in_dataset = dataset_scores()
    failed = 0
    print(f"{'row of the table':38}{'column':10}{'raw':>7}{'shown':>7}  dataset")
    for name, column, raw, shown in QUOTED:
        row = by_name.get(name)
        if row is None:
            print(f"{name:38}{column:10}  not in the saved rows")
            failed += 1
            continue
        got_raw, got_shown = round(100 * row[f"{column} Raw"], 2), round(row[column], 2)
        ok = (got_raw, got_shown) == (raw, shown)
        model = row["fullname"].lower()
        ours = in_dataset.get((model, BENCHMARK[column]), in_dataset.get((model.split("/")[-1], BENCHMARK[column])))
        if ours is None:
            note = "not looked up" if not in_dataset else "model not in the dataset"
        else:
            note = f"{ours:.2f}"
            ok = ok and round(ours, 2) == shown
        failed += not ok
        print(f"{name:38}{column:10}{got_raw:>7.2f}{got_shown:>7.2f}  {note:10} {'ok' if ok else 'DIFFERS from the paper'}")
    return failed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Check the leaderboard scores the paper quotes from the leaderboard's table.")
    ap.add_argument("--fetch", action="store_true",
                    help="download the table at the fixed revision, compare the saved rows with it and rewrite them")
    args = ap.parse_args(argv)
    if args.fetch:
        rows = download()
        same = ROWS.exists() and saved() == rows
        print(f"{REPO}@{REVISION[:7]}: {len(rows)} rows of {len(MODELS)} models; "
              f"{'the saved rows are identical' if same else 'the saved rows were rewritten'}")
        if not same:
            write(rows)
    else:
        rows = saved()
    failed = check(rows)
    print("all quoted scores match" if not failed else f"{failed} quoted scores do not match")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
