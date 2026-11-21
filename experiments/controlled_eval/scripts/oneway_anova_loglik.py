"""Powered prompt-format ANOVA for every log-likelihood benchmark, using the
appropriate replication unit for each:

  * Random-few-shot benchmarks (ARC-Challenge, WinoGrande, OpenBookQA) vary by seed,
    so they are powered by SEEDS: 4 models x 3 seeds = n=12 per format.
  * Deterministic fixed-few-shot benchmarks (MMLU, GPQA) do not vary by seed, so they
    are powered by MODELS: 8 models x 1 seed = n=8 per format.

Reports F, p (approx via F-dist survival), and eta^2 per benchmark, for comparison with the repeated-measures test of Appendix M.1.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from common.stats import oneway_anova  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def load(name):
    p = os.path.join(RESULTS_DIR, name)
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if os.path.exists(p) else []


FORMATS = ("plain", "instruct", "cot")


def groups_for(rows, bench, key):
    g = {f: [] for f in FORMATS}
    for r in rows:
        if r.get("benchmark") == bench and r.get("status", "ok") == "ok" and r.get("n_shot") == 5 \
                and r.get("prompt_format") in g:
            g[r["prompt_format"]].append(r["score"])
    return [g[f] for f in FORMATS]


# benchmark -> (result files, what the replicates of a format are). A benchmark is added
# to the analysis by adding it here.
SEED_FILES = ("generalization_hf.jsonl", "generalization_multiseed.jsonl")
MODEL_FILES = ("mmlu_gpqa_8models.jsonl",)
DESIGNS = {
    "ARC-Challenge": (SEED_FILES, "seeds"), "WinoGrande": (SEED_FILES, "seeds"), "OpenBookQA": (SEED_FILES, "seeds"),
    "MMLU": (MODEL_FILES, "models"), "GPQA": (MODEL_FILES, "models"),
}


def main():
    print(f"{'benchmark':16}{'design':10}{'n/format':10}{'F':>8}{'p':>10}{'eta^2':>8}")
    print("-" * 62)
    for bench, (files, design) in DESIGNS.items():
        rows = [r for name in files for r in load(name)]
        res = oneway_anova(groups_for(rows, bench, design))
        if res:
            print(f"{bench:16}{design:10}{'/'.join(map(str, res['sizes'])):10}"
                  f"{res['F']:8.2f}{res['p']:10.4f}{100 * res['eta2']:7.1f}%")
        else:
            print(f"{bench:16}{design:10}{'(no data yet)':>30}")
    print("\nReference: GSM8K (generation, vLLM grid) F=13.0, p<0.001, eta^2~27%.")


if __name__ == "__main__":
    main()
