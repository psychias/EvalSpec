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
LOWER BOUND on true overlap.

    python scripts/collision_prevalence.py                       # the dataset in data/
    python scripts/collision_prevalence.py path/to/results.csv   # any file with the same columns
    python scripts/collision_prevalence.py --reference bigcodebench --small 2 --large 10

The thresholds, the fields a disagreement is attributed to and the source that the
others are compared with are arguments of `prevalence` and `reference_gaps`, so the
same analysis runs on another corpus or with another reference source.

On the published dataset (Psychias/EvalSpec_Dataset, 46,559 rows) this prints the
Section 3.3 numbers: 41,999 pairs, 291 collisions, 214 >1pp, 169 >5pp, harness
missing for 210/214 (98%) of the disagreements.
"""
import argparse
import csv
import re
import statistics
from collections import defaultdict

import dataset_access as ds

OLV2 = "open_llm_leaderboard_v2"


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


def load_cells(path=None):
    """(rows, {(model, benchmark): rows}) of a results CSV, the dataset's by default."""
    with open(path or ds.AGGREGATE_CSV, encoding="utf-8", errors="replace") as fh:
        rows = list(csv.DictReader(fh))
    cells = defaultdict(list)
    for r in rows:
        m, b = norm_model(r.get("model_id"), r.get("model")), norm_bench(r.get("benchmark"))
        if m and b:
            cells[(m, b)].append(r)
    return rows, cells


def prevalence(cells, small=1.0, large=5.0):
    """Collision counts of Section 3.3.

    A pair disagrees when its scores are more than `small` points apart, and by a
    wide margin when they are more than `large` points apart.
    """
    multi = disagree = big = no_harness = no_scoring = 0
    for recs in cells.values():
        if len({r.get("source") for r in recs}) < 2:
            continue
        multi += 1
        scores = [fnum(r.get("score")) for r in recs if fnum(r.get("score")) is not None]
        if len(scores) < 2:
            continue
        spread = max(scores) - min(scores)
        if spread > small:
            disagree += 1
            if spread > large:
                big += 1
            # a disagreement cannot be attributed when a record omits the field
            if any(not has(r, "harness") for r in recs):
                no_harness += 1
            if any(not has(r, "scoring_method") for r in recs):
                no_scoring += 1
    return {"pairs": len(cells), "collisions": multi, "differ_gt_1pp": disagree,
            "differ_gt_5pp": big, "harness_missing": no_harness, "scoring_mode_missing": no_scoring}


def reference_gaps(cells, reference=OLV2):
    """One source against the others, per benchmark (Section 3.3, App. F).

    Returns {benchmark: [median of the other sources - reference, one per model]}.
    The paper uses OLv2 as the reference: it scores by log-likelihood, so it should
    sit below sources that use the documented chain-of-thought protocol, in the same
    direction across models.
    """
    gaps = defaultdict(list)
    for (_model, bench), recs in cells.items():
        srcs = {r.get("source") for r in recs}
        if reference not in srcs or len(srcs) < 2:
            continue
        own = [fnum(r["score"]) for r in recs if r.get("source") == reference and fnum(r.get("score")) is not None]
        oth = [fnum(r["score"]) for r in recs if r.get("source") != reference and fnum(r.get("score")) is not None]
        if own and oth:
            gaps[bench].append(statistics.median(oth) - own[0])
    return gaps


def olv2_gaps(cells):
    """`reference_gaps` with the Open LLM Leaderboard v2 as the reference."""
    return reference_gaps(cells, OLV2)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Count the model-benchmark pairs that several sources report.")
    ap.add_argument("csv", nargs="?", help="results file (default: aggregated/all_results.csv of the dataset)")
    ap.add_argument("--reference", default=OLV2, help=f"source compared with the others (default: {OLV2})")
    ap.add_argument("--small", type=float, default=1.0, help="points apart that count as a disagreement (default: 1)")
    ap.add_argument("--large", type=float, default=5.0, help="points apart that count as a wide one (default: 5)")
    ds.add_data_option(ap)
    args = ap.parse_args(argv)
    ds.apply_data_option(args)
    rows, cells = load_cells(args.csv)
    p = prevalence(cells, args.small, args.large)
    n, d = p["collisions"], p["differ_gt_1pp"]
    print(f"records: {len(rows)}")
    print(f"distinct model-benchmark pairs: {p['pairs']}")
    print(f"collisions (>=2 sources): {n} ({100*n/p['pairs']:.2f}% of pairs)")
    print(f"  disagree >{args.small:g}pp: {d} ({100*d/max(n,1):.1f}% of collisions)")
    print(f"  disagree >{args.large:g}pp: {p['differ_gt_5pp']} ({100*p['differ_gt_5pp']/max(n,1):.1f}% of collisions)")
    print(f"  harness missing among disagreements: {p['harness_missing']}/{d} "
          f"({100*p['harness_missing']/max(d,1):.0f}%)")
    print(f"  scoring mode missing among disagreements: {p['scoring_mode_missing']}/{d} "
          f"({100*p['scoring_mode_missing']/max(d,1):.0f}%)")

    name = "OLv2" if args.reference == OLV2 else args.reference
    print(f"\n{name} against the other sources, per benchmark (median of the others minus {name}, one comparison per model):")
    for b, gs in sorted(reference_gaps(cells, args.reference).items(), key=lambda x: -len(x[1])):
        if len(gs) >= 2:
            print(f"  {b:14} n={len(gs):3}  median={statistics.median(gs):+.1f}pp  "
                  f"{name} lower in {sum(1 for g in gs if g > 0)}/{len(gs)}")


if __name__ == "__main__":
    main()
