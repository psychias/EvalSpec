"""
Full-set vs limit=200 robustness check for ONE factorial-grid cell.

Cell: Qwen2.5-7B-Instruct x GSM8K x 5-shot, prompt format plain vs cot, temp 0.0.
The factorial grid (Appendix M.1) scored GSM8K on a 200-problem subset (limit=200)
for compute budget. This reruns the same cell on the FULL GSM8K test set (1319
questions) and prints the full-vs-limit=200 comparison, to confirm the subset is
representative and the plain>cot collapse is not a subset artefact.

Methodology matches the grid exactly: lm-evaluation-harness 0.4.11 + vLLM,
apply_chat_template=True, the plain/cot system prompts from prompt_templates.md,
num_fewshot=5, deterministic decoding (do_sample=False, temperature=0, seed=42),
GSM8K exact_match strict-match (the #### parser).

Run on a Colab GPU runtime (A100 / L4). Paste the body below into a Colab cell,
or: `python full_vs_limit200_qwen7b_gsm8k.py` on a GPU box with the deps installed.

Reference (paper, limit=200, 3 seeds): plain ~40.2, cot ~27.7.

    python full_vs_limit200_qwen7b_gsm8k.py                          # the cell of the paper
    python full_vs_limit200_qwen7b_gsm8k.py --model ORG/NAME --batch-size 16 --limit 100
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common import lm_eval_runs as runs  # noqa: E402

MODEL = "Qwen/Qwen2.5-7B-Instruct"
TASK  = "gsm8k"          # 5-shot, strict-match (#### parser) — identical to the grid
NSHOT = 5
GEN   = "do_sample=False"   # greedy = deterministic (hf generate() has no seed/temperature kwarg)
SYS = {
    "plain": None,       # model's own default system prompt
    "cot":   runs.FORMAT_TEMPLATES["cot"],
}
REF_LIMIT200 = {"plain": 40.2, "cot": 27.7}   # paper, mean over 3 seeds
LIMIT = 200
SEED = 42


def score(lm, fmt, limit, gen_kwargs, seed=SEED):
    """The GSM8K score of one prompt format on the first `limit` problems (None: the full test set)."""
    res = runs.evaluate(
        lm, tasks=[TASK], num_fewshot=NSHOT, gen_kwargs=gen_kwargs,
        system_instruction=SYS[fmt], apply_chat_template=True,
        limit=limit, random_seed=seed, fewshot_random_seed=seed,
    )
    m = res["results"][TASK]
    value = round(100 * m.get("exact_match,strict-match",
                              m.get("exact_match,flexible-extract")), 2)
    tag = "full" if limit is None else f"limit={limit}"
    print(f"  [done] {fmt} {tag}: {value}", flush=True)   # incremental: survives a timeout
    return value


def compare(lm, gen_kwargs, limit=LIMIT, reference=REF_LIMIT200, formats=("plain", "cot")):
    """Print, per prompt format, the score on the subset, on the full set, and their difference."""
    print(f"{'format':<8}{f'limit={limit}':>12}{'full(1319)':>13}{'delta':>9}{f'paper@{LIMIT}':>11}", flush=True)
    print("-" * 53, flush=True)
    for fmt in formats:
        subset = score(lm, fmt, limit, gen_kwargs)
        full = score(lm, fmt, None, gen_kwargs)        # None = full test set
        print(f"{fmt:<8}{subset:>12.2f}{full:>13.2f}{full - subset:>+9.2f}{reference[fmt]:>11.1f}", flush=True)


def options(description, default_model=MODEL):
    import argparse
    ap = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=default_model)
    ap.add_argument("--limit", type=int, default=LIMIT, help=f"size of the subset (default: {LIMIT})")
    return ap


def main(argv=None):
    ap = options(__doc__)
    ap.add_argument("--batch-size", type=int, default=48)
    args = ap.parse_args(argv)
    # Self-install on a fresh Colab VM. We use lm-eval's Hugging Face (transformers)
    # backend rather than vLLM: the current vLLM wheel is built against CUDA 13
    # (libcudart.so.13), which Colab's CUDA-12 image cannot load, whereas
    # transformers uses the VM's own torch/CUDA and is reliable. The hf backend is
    # the same one the paper's harness-version experiment (Exp3) used, and the
    # limit=200-vs-full comparison is backend-independent (both sides use hf here).
    print("[setup] installing lm-eval==0.4.11 (hf backend) ...", flush=True)
    runs.pip_install("lm-eval==0.4.11", "accelerate")
    lm = runs.load_hf_model(pretrained=args.model, dtype="bfloat16", batch_size=args.batch_size)
    compare(lm, GEN, args.limit)
    print("\nplain>cot gap @200 vs @full, and full-vs-200 deltas: if the deltas are small")
    print("(<~2 pp) and the gap is preserved, the 200-problem subset is representative.")


if __name__ == "__main__":
    main()
