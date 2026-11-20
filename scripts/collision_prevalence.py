"""Corpus-wide cross-source collision prevalence (paper Section 3.3,
"Cross-source verification is rare"; OLv2 gaps in App. F).

Reads data/aggregated/all_results.csv (the flattened union of all sources) and
reports, over distinct model-benchmark pairs after name normalisation:
  - how many pairs are reported by >=2 sources (collisions),
  - what fraction of collisions disagree by >1pp / >5pp,
  - for how many disagreements the harness is missing from at least one record,
    and for how many the scoring mode is missing (it is never recorded).

Name normalisation is purely lexical and self-contained: lower-case, drop
parenthesised qualifiers from benchmark names, drop the HF org prefix from model
ids, and keep only [a-z0-9]. No alias or canonical-name map is applied, and
capability suffixes (instruct/chat/base) are kept, so the collision count is a
LOWER BOUND on true overlap. Run from the repo root:

    python scripts/collision_prevalence.py [path/to/all_results.csv]

On the published dataset (Hermeneia/EvalSpec_Dataset, 46,559 rows) this prints the
Section 3.3 numbers: 41,999 pairs, 291 collisions, 214 >1pp, 169 >5pp, harness
missing for 210/214 (98%) of the disagreements.
"""
import csv
import os
import re
import statistics
import sys
from collections import defaultdict

CSV_PATH = os.path.join("data", "aggregated", "all_results.csv")


def norm_bench(b):
    key = re.sub(r"\s+", " ", (b or "").strip().lower())
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\s*\(.*?\)", "", key))


def norm_model(model_id, name):
    # Strip the org prefix + separators only. We deliberately do NOT strip
    # capability suffixes (instruct/chat/base): conflating a base and an
    # instruct checkpoint would manufacture false collisions and inflate the
    # disagreement rate. This keeps the collision count a conservative lower
    # bound on true cross-source overlap.
    tail = (model_id or name or "").strip().split("/")[-1]
    return re.sub(r"[^a-z0-9]", "", tail.lower())


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def has(rec, field):
    v = (rec.get(field) or "").strip().lower()
    return v not in ("", "unknown", "none", "nan", "null")


def load_cells(path=CSV_PATH):
    with open(path, encoding="utf-8", errors="replace") as fh:
        rows = list(csv.DictReader(fh))
    cells = defaultdict(list)
    for r in rows:
        m, b = norm_model(r.get("model_id"), r.get("model")), norm_bench(r.get("benchmark"))
        if m and b:
            cells[(m, b)].append(r)
    return rows, cells


def prevalence(cells):
    """Collision counts of Section 3.3."""
    multi = disagree = big = no_harness = no_scoring = 0
    for recs in cells.values():
        if len({r.get("source") for r in recs}) < 2:
            continue
        multi += 1
        scores = [fnum(r.get("score")) for r in recs if fnum(r.get("score")) is not None]
        if len(scores) < 2:
            continue
        spread = max(scores) - min(scores)
        if spread > 1.0:
            disagree += 1
            if spread > 5.0:
                big += 1
            # a disagreement cannot be attributed when a record omits the field
            if any(not has(r, "harness") for r in recs):
                no_harness += 1
            if any(not has(r, "scoring_method") for r in recs):
                no_scoring += 1
    return {"pairs": len(cells), "collisions": multi, "differ_gt_1pp": disagree,
            "differ_gt_5pp": big, "harness_missing": no_harness, "scoring_mode_missing": no_scoring}


def olv2_gaps(cells):
    """OLv2 against the other sources, per benchmark (Section 3.3, App. F).

    OLv2 scores by log-likelihood, so it should sit below sources that use the
    documented chain-of-thought protocol, in the same direction across models.
    Returns {benchmark: [median of the other sources - OLv2, one per model]}.
    """
    olv2 = "open_llm_leaderboard_v2"
    gaps = defaultdict(list)
    for (_model, bench), recs in cells.items():
        srcs = {r.get("source") for r in recs}
        if olv2 not in srcs or len(srcs) < 2:
            continue
        own = [fnum(r["score"]) for r in recs if r.get("source") == olv2 and fnum(r.get("score")) is not None]
        oth = [fnum(r["score"]) for r in recs if r.get("source") != olv2 and fnum(r.get("score")) is not None]
        if own and oth:
            gaps[bench].append(statistics.median(oth) - own[0])
    return gaps


def main():
    rows, cells = load_cells(sys.argv[1] if len(sys.argv) > 1 else CSV_PATH)
    p = prevalence(cells)
    n, d = p["collisions"], p["differ_gt_1pp"]
    print(f"records: {len(rows)}")
    print(f"distinct model-benchmark pairs: {p['pairs']}")
    print(f"collisions (>=2 sources): {n} ({100*n/p['pairs']:.2f}% of pairs)")
    print(f"  disagree >1pp: {d} ({100*d/max(n,1):.1f}% of collisions)")
    print(f"  disagree >5pp: {p['differ_gt_5pp']} ({100*p['differ_gt_5pp']/max(n,1):.1f}% of collisions)")
    print(f"  harness missing among disagreements: {p['harness_missing']}/{d} "
          f"({100*p['harness_missing']/max(d,1):.0f}%)")
    print(f"  scoring mode missing among disagreements: {p['scoring_mode_missing']}/{d} "
          f"({100*p['scoring_mode_missing']/max(d,1):.0f}%)")

    print("\nOLv2 against the other sources, per benchmark (median of the others minus OLv2, one comparison per model):")
    for b, gs in sorted(olv2_gaps(cells).items(), key=lambda x: -len(x[1])):
        if len(gs) >= 2:
            print(f"  {b:14} n={len(gs):3}  median={statistics.median(gs):+.1f}pp  "
                  f"OLv2 lower in {sum(1 for g in gs if g > 0)}/{len(gs)}")


if __name__ == "__main__":
    main()
