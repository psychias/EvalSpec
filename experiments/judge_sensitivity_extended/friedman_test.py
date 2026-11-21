"""Formal test that the judge model systematically affects ratings of FIXED
responses. Each block is one fixed response (contestant x question); the eight
judges are the repeated treatments. Friedman test (non-parametric, blocks =
responses, treatments = judges) asks whether the judges' ratings of the same
responses differ beyond chance. Also reports Kendall's W (effect size / concordance)
and the range of the judges' mean ratings.

    python friedman_test.py                    # the judge runs of this experiment
    python friedman_test.py path/to/judge_runs.jsonl

The input is one JSON object per line with `contestant`, `question_id`, `judge`,
`rating` and `raw_ok`, so the test runs on the judge runs of any experiment.
"""
import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common import stats  # noqa: E402

JUDGE_RUNS = os.path.join(os.path.dirname(__file__), "results", "judge_runs.jsonl")


def load_ratings(path):
    """The rows of a judge-runs file that carry a rating."""
    if not os.path.exists(path):
        raise SystemExit(f"{path} is not in the repository. See experiments/README.md for the run that writes it.")
    with open(path, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    return [r for r in rows if r.get("raw_ok") and r.get("rating") is not None]


def complete_blocks(rows):
    """(judges, blocks): one block per response that every judge rated, as {judge: rating}."""
    judges = sorted({r["judge"] for r in rows})
    blocks = defaultdict(dict)                  # (contestant, question_id) -> rating per judge
    for r in rows:
        blocks[(r["contestant"], r["question_id"])][r["judge"]] = r["rating"]
    return judges, [b for b in blocks.values() if len(b) == len(judges)]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Friedman test of the judges' ratings of the same responses.")
    ap.add_argument("judge_runs", nargs="?", default=JUDGE_RUNS, help="judge runs file (default: results/judge_runs.jsonl)")
    args = ap.parse_args(argv)

    judges, complete = complete_blocks(load_ratings(args.judge_runs))
    matrix = [[b[j] for j in judges] for b in complete]
    n, k = len(matrix), len(judges)
    print(f"judges k={k}, complete response-blocks n={n}")

    try:
        from scipy.stats import friedmanchisquare
        stat, p = friedmanchisquare(*[[row[c] for row in matrix] for c in range(k)])
        print(f"Friedman chi^2({k-1}) = {stat:.1f}, p = {p:.2e}")
        print(f"Kendall's W = {stat / (n * (k - 1)):.3f}")
    except ImportError as e:  # without SciPy: the statistic without the correction for ties
        print("scipy unavailable, computing manually:", str(e)[:60])
        stat, df, W = stats.friedman(matrix)
        print(f"Friedman chi^2({df}) = {stat:.1f}  (p far below 1e-6 for this magnitude)")
        print(f"Kendall's W = {W:.3f}")

    # mean rating per judge (over complete blocks) to show spread
    mj = {j: sum(b[j] for b in complete) / n for j in judges}
    lo, hi = min(mj.values()), max(mj.values())
    print(f"per-judge mean rating range: {lo:.2f}-{hi:.2f} (spread {hi-lo:.2f}/10)")


if __name__ == "__main__":
    main()
