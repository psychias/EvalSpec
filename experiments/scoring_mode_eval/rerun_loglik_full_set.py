"""Exp2 (scoring mode on MMLU): full-set log-likelihood for the three smaller models, so all
four rows of the table are ll@full vs gen@full (the 14B is in rerun_missing_cells.py, in this folder).

Motivation: the original ll values used limit=500/subject, which carries subset-
composition noise. For the 14B this mattered (ll@500=81.72 vs ll@full=79.97); for the
smaller models it did not (Mistral 61.92->61.85, Qwen-7B 74.26->74.25), but rerunning
them on the full set makes every row an exact same-sample comparison to generation@full.

Results (ll@full / gen@full / |Delta|):
  Mistral-7B-Instruct-v0.3   61.85 / 61.64 / 0.21
  Qwen2.5-7B-Instruct        74.25 / 74.43 / 0.18
  Llama-3.1-8B-Instruct      68.19 / 68.16 / 0.03

Gating: Mistral-v0.3 is gated -> the prefetch subprocess authenticates with HF_TOKEN
(set it in the environment before launching; the offline eval needs no token).
meta-llama/Llama-3.1-8B-Instruct requires a separate Meta-license approval, so this
uses the ungated faithful re-upload NousResearch/Meta-Llama-3.1-8B-Instruct (identical
weights). Same prefetch-then-offline pattern; batch_size=8; results print incrementally.

    python rerun_loglik_full_set.py                          # the three models of the table
    python rerun_loglik_full_set.py --model ORG/NAME@8       # another model; may be given several times
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common import lm_eval_runs as runs  # noqa: E402

# (repository to load, model id, batch size). The Llama repository is the ungated mirror.
MODELS = [
    ("mistralai/Mistral-7B-Instruct-v0.3", "mistralai/Mistral-7B-Instruct-v0.3", 8),
    ("Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-7B-Instruct", 8),
    ("NousResearch/Meta-Llama-3.1-8B-Instruct", "NousResearch/Meta-Llama-3.1-8B-Instruct", 8),
]
SEED = 42


def mmlu_loglik(lm, seed=SEED, limit=None):
    """MMLU 5-shot log-likelihood accuracy in percent (limit=None: the full 14,042 questions)."""
    r = runs.evaluate(lm, tasks=["mmlu"], num_fewshot=5, limit=limit, **runs.seeded(seed, fewshot=True))
    m = r["results"]["mmlu"]
    return round(100 * m.get("acc,none", m.get("acc")), 2)


def main(argv=None):
    args = runs.parse(runs.grid_parser(__doc__, MODELS, formats=None), argv)
    if args.dry_run:
        return runs.dry_run(dict(eval_id=e, batch_size=b, task="mmlu", n_shot=5, seed=SEED) for e, _, b in args.models)
    token = runs.offline_session()             # the operator's token, for the gated repository
    print("[setup] installing lm-eval==0.4.11 ...", flush=True)
    runs.pip_install("lm-eval==0.4.11", "accelerate")
    print("[prefetch] caching models + cais/mmlu (online subprocess) ...", flush=True)
    runs.prefetch_online(runs.snapshot_lines(e for e, _, _ in args.models) + runs.MMLU_LINES
                         + 'print("SNAP_OK mmlu", len(cfgs), "configs", flush=True)\n', token=token)
    print("[prefetch] done; running lm-eval OFFLINE", flush=True)
    for eval_id, _, batch in args.models:
        try:
            lm = runs.load_hf_model(pretrained=eval_id, dtype="bfloat16", batch_size=batch)
            acc = mmlu_loglik(lm)
            print(f"[Exp2] {eval_id} MMLU 5-shot log-likelihood (FULL 14042): {acc}", flush=True)
            runs.release(lm)
        except Exception as e:  # noqa: BLE001
            print(f"[Exp2-SKIP] {eval_id}: {str(e)[:120]}", flush=True)


if __name__ == "__main__":
    main()
